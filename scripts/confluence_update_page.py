#!/usr/bin/env python3
"""
confluence_update_page.py — Update or append content to an existing Confluence page.

Usage:
    python3 scripts/confluence_update_page.py --page-id ID --show
    python3 scripts/confluence_update_page.py --page-id ID --append "markdown text"
    python3 scripts/confluence_update_page.py --page-id ID --replace-section "Heading Title" "new markdown content"
    python3 scripts/confluence_update_page.py --page-id ID --set-title "New Page Title"
    python3 scripts/confluence_update_page.py --search "search terms" [--space SPACE_KEY]

Flags:
    --page-id ID                     Target Confluence page ID.
    --show                           Show page details and content excerpt.
    --append TEXT                    Append markdown text as paragraph blocks.
    --replace-section HEADING TEXT   Replace a section under an h2 or h3 heading.
    --set-title TITLE                Update the page title.
    --search TERMS                   Search for pages by text.
    --space SPACE_KEY                Restrict search results to a space.

Environment:
    CONFLUENCE_EMAIL
    WWEEKS_CONFLUENCE_API_TOKEN
    CONFLUENCE_BASE_URL  (default: https://<YOUR_ATLASSIAN>.atlassian.net/wiki)
"""

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, CONFLUENCE_COMMON_CAUSES


DEFAULT_BASE_URL = "https://<YOUR_ATLASSIAN>.atlassian.net/wiki"
ENTITY_MAP = {
    "&lt;": "<",
    "&gt;": ">",
    "&amp;": "&",
    "&#39;": "'",
    "&quot;": '"',
    "&nbsp;": " ",
}



def load_env_file():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())



def base_url():
    return os.environ.get("CONFLUENCE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")



def auth_header():
    email = require_env("CONFLUENCE_EMAIL",
                        hint="cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)")
    token = require_env("WWEEKS_CONFLUENCE_API_TOKEN",
                        hint="cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)")
    raw = f"{email}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("utf-8")



def request_json(method, url, payload=None):
    headers = {"Authorization": auth_header(), "Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        http_fail(exc, api_name="Confluence", operation=f"{method} {url}",
                  common_causes=CONFLUENCE_COMMON_CAUSES)
    except URLError as exc:
        fail(f"Confluence request failed: {exc.reason}",
             causes=["Network error or DNS resolution failure",
                     "CONFLUENCE_BASE_URL is wrong"],
             try_=["curl -I https://<YOUR_ATLASSIAN>.atlassian.net/wiki",
                   "ping <YOUR_ATLASSIAN>.atlassian.net"])



def page_url(page_id):
    return f"{base_url()}/api/v2/pages/{page_id}?body-format=storage"



def fetch_page(page_id):
    page = request_json("GET", page_url(page_id))
    title = page.get("title", "")
    version = page.get("version") or {}
    body = page.get("body") or {}
    storage = body.get("storage") or {}
    return {
        "id": str(page.get("id") or page_id),
        "title": title,
        "space": (page.get("space") or {}).get("key") or page.get("spaceKey") or page.get("spaceId") or "—",
        "version": int(version.get("number") or 1),
        "updated": version.get("createdAt") or page.get("updatedAt") or "—",
        "body": storage.get("value") or "",
    }



def decode_entities(text):
    for source, target in ENTITY_MAP.items():
        text = text.replace(source, target)
    return text



def readable_text(storage_value):
    text = decode_entities(storage_value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</h[1-6]>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()



def escape_xml(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )



def markdown_to_storage_paragraphs(text):
    lines = [line.rstrip() for line in text.splitlines()]
    paragraphs = [f"<p>{escape_xml(line)}</p>" for line in lines if line.strip()]
    if paragraphs:
        return "\n".join(paragraphs)
    return "<p></p>"



def inject_before_body_close(storage_value, fragment):
    if re.search(r"</body>\s*$", storage_value, flags=re.IGNORECASE):
        return re.sub(r"</body>\s*$", fragment + "\n</body>", storage_value, count=1, flags=re.IGNORECASE)
    return storage_value.rstrip() + "\n" + fragment



def heading_matches(raw_heading, heading_title):
    text = readable_text(raw_heading)
    return re.sub(r"\s+", " ", text).strip().lower() == heading_title.strip().lower()



def replace_section(storage_value, heading_title, new_content):
    headings = list(re.finditer(r"<h([23])[^>]*>(.*?)</h\1>", storage_value, flags=re.IGNORECASE | re.DOTALL))
    for index, heading in enumerate(headings):
        if not heading_matches(heading.group(2), heading_title):
            continue
        level = int(heading.group(1))
        start = heading.end()
        end = len(storage_value)
        for next_heading in headings[index + 1 :]:
            next_level = int(next_heading.group(1))
            if next_level <= level:
                end = next_heading.start()
                break
        replacement = "\n" + markdown_to_storage_paragraphs(new_content) + "\n"
        return storage_value[:start] + replacement + storage_value[end:]
    raise RuntimeError(f"Section not found: {heading_title}")



def update_page(page_id, title, version, storage_value):
    payload = {
        "id": str(page_id),
        "status": "current",
        "title": title,
        "version": {"number": version + 1},
        "body": {"storage": {"value": storage_value, "representation": "storage"}},
    }
    url = f"{base_url()}/api/v2/pages/{page_id}"
    return request_json("PUT", url, payload)



def show_page(page_id):
    page = fetch_page(page_id)
    excerpt = readable_text(page["body"])[:2000] or "—"
    print(f"Title        : {page['title'] or '—'}")
    print(f"Space        : {page['space']}")
    print(f"Version      : {page['version']}")
    print(f"Last updated : {page['updated']}")
    print("Content:")
    print(excerpt)
    print("✓ Page loaded")
    return 0



def append_content(page_id, text):
    page = fetch_page(page_id)
    fragment = markdown_to_storage_paragraphs(text)
    updated_body = inject_before_body_close(page["body"], fragment)
    update_page(page_id, page["title"], page["version"], updated_body)
    print(f"✓ Appended content to page {page_id}")
    return 0



def replace_page_section(page_id, heading_title, new_content):
    page = fetch_page(page_id)
    updated_body = replace_section(page["body"], heading_title, new_content)
    update_page(page_id, page["title"], page["version"], updated_body)
    print(f"✓ Replaced section '{heading_title}' on page {page_id}")
    return 0



def set_page_title(page_id, new_title):
    page = fetch_page(page_id)
    update_page(page_id, new_title, page["version"], page["body"])
    print(f"✓ Updated title for page {page_id}")
    return 0



def search_pages(terms, space_key):
    escaped_terms = terms.replace('"', '\\"')
    cql = f'text~"{escaped_terms}"'
    if space_key:
        cql += f' AND space="{space_key}"'
    url = f"{base_url()}/rest/api/content/search?cql={quote(cql)}&limit=10"
    results = request_json("GET", url)
    rows = results.get("results") or []
    if not rows:
        print("⚠ No matching pages found")
        return 0
    print("PAGE_ID      SPACE    TITLE")
    print("-----------  -------  -----------------------------------------------")
    for item in rows:
        page_id = str(item.get("id") or "—")
        title = item.get("title") or "—"
        space = ((item.get("space") or {}).get("key") or "—")
        webui = ((item.get("_links") or {}).get("webui") or f"/pages/{page_id}")
        print(f"{page_id:<11}  {space:<7}  {title}")
        print(f"  {base_url()}{webui}")
    print(f"✓ Found {len(rows)} page(s)")
    return 0



def build_parser():
    parser = argparse.ArgumentParser(description="Update or append content on an existing Confluence page")
    parser.add_argument("--page-id", help="Confluence page ID")
    parser.add_argument("--space", help="Confluence space key for --search")
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument("--show", action="store_true", help="Show page details")
    action_group.add_argument("--append", metavar="TEXT", help="Append markdown text")
    action_group.add_argument(
        "--replace-section",
        nargs=2,
        metavar=("HEADING_TITLE", "NEW_CONTENT"),
        help="Replace the content under a section heading",
    )
    action_group.add_argument("--set-title", metavar="NEW_PAGE_TITLE", help="Set a new page title")
    action_group.add_argument("--search", metavar="TERMS", help="Search page content")
    return parser



def validate_args(args, parser):
    if args.search:
        return
    if args.page_id:
        return
    parser.error("--page-id is required unless --search is used")



def main():
    load_env_file()
    parser = build_parser()
    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help()
        return 1
    try:
        validate_args(args, parser)
        if args.show:
            return show_page(args.page_id)
        if args.append is not None:
            return append_content(args.page_id, args.append)
        if args.replace_section is not None:
            heading_title, new_content = args.replace_section
            return replace_page_section(args.page_id, heading_title, new_content)
        if args.set_title is not None:
            return set_page_title(args.page_id, args.set_title)
        if args.search is not None:
            return search_pages(args.search, args.space)
        parser.print_help()
        return 1
    except Exception as exc:
        fail(str(exc))


if __name__ == "__main__":
    sys.exit(main())
