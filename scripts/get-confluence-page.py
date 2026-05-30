#!/usr/bin/env python3
"""
Download a Confluence page and save as markdown to the confluence/ directory.

Usage:
    python3 get-confluence-page.py <page_id>
    python3 get-confluence-page.py <page_id> --format storage
    python3 get-confluence-page.py <page_id> --output custom-path.md

Reads CONFLUENCE_EMAIL and WWEEKS_CONFLUENCE_API_TOKEN from ../.env or .env
"""

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, CONFLUENCE_COMMON_CAUSES

BASE_URL = "https://<YOUR_ATLASSIAN>.atlassian.net/wiki/rest/api"


def load_env():
    """Load credentials from .env file."""
    for env_path in [Path(__file__).parent / "../.env", Path(__file__).parent / ".env"]:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
            break


def api_request(method, path):
    """Make an authenticated Confluence API request."""
    require_env(
        "CONFLUENCE_EMAIL", "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="Add them to .env at the repo root",
        env_file=str(Path(__file__).parent.parent / ".env"),
    )
    email = os.environ["CONFLUENCE_EMAIL"]
    token = os.environ["WWEEKS_CONFLUENCE_API_TOKEN"]
    credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
    url = f"{BASE_URL}/{path}"
    headers = {
        "Authorization": f"Basic {credentials}",
        "Accept": "application/json",
    }

    req = Request(url, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        http_fail(e, api_name="Confluence", key=path, operation=f"{method} {path}",
                  common_causes=CONFLUENCE_COMMON_CAUSES)


# ── Storage HTML → Markdown ─────────────────────────────────────────────────────


def convert_storage_to_markdown(html):
    """Convert Confluence storage format HTML to markdown."""

    # Decode HTML entities
    entities = {
        "&ndash;": "–", "&mdash;": "—", "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&nbsp;": " ", "&rarr;": "→", "&harr;": "↔", "&times;": "×",
        "&#39;": "'", "&quot;": '"',
    }
    for entity, char in entities.items():
        html = html.replace(entity, char)

    # Horizontal rules
    html = re.sub(r"<hr[^>]*/?>", "\n\n---\n\n", html)

    # Code blocks — with language parameter
    html = re.sub(
        r'<ac:structured-macro[^>]*ac:name="code"[^>]*>.*?'
        r'<ac:parameter ac:name="language">([^<]*)</ac:parameter>.*?'
        r"<ac:plain-text-body><!\[CDATA\[(.*?)\]\]></ac:plain-text-body>.*?"
        r"</ac:structured-macro>",
        lambda m: f"\n```{m.group(1)}\n{m.group(2)}\n```\n",
        html,
        flags=re.DOTALL,
    )
    # Code blocks — without language
    html = re.sub(
        r'<ac:structured-macro[^>]*ac:name="code"[^>]*>.*?'
        r"<ac:plain-text-body><!\[CDATA\[(.*?)\]\]></ac:plain-text-body>.*?"
        r"</ac:structured-macro>",
        lambda m: f"\n```\n{m.group(1)}\n```\n",
        html,
        flags=re.DOTALL,
    )

    # Strip remaining Confluence macros
    html = re.sub(r"<ac:structured-macro[^>]*>.*?</ac:structured-macro>", "", html, flags=re.DOTALL)

    # Tables
    def convert_table(m):
        table_html = m.group(0)
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL)
        md_rows = []
        header_done = False

        for row in rows:
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.DOTALL)
            cell_texts = []
            for cell in cells:
                cell_clean = re.sub(r"<[^>]+>", "", cell).strip()
                cell_clean = cell_clean.replace("\n", " ").replace("|", "\\|")
                cell_texts.append(cell_clean)
            if cell_texts:
                md_rows.append("| " + " | ".join(cell_texts) + " |")
                if not header_done:
                    md_rows.append("| " + " | ".join(["---"] * len(cell_texts)) + " |")
                    header_done = True
        return "\n" + "\n".join(md_rows) + "\n"

    html = re.sub(r"<table[^>]*>.*?</table>", convert_table, html, flags=re.DOTALL)

    # Headings (process largest first to avoid conflicts)
    for level in range(6, 0, -1):
        prefix = "#" * level
        html = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, p=prefix: f"\n{p} {re.sub(r'<[^>]+>', '', m.group(1)).strip()}\n",
            html,
            flags=re.DOTALL,
        )

    # List items → bullet points, then strip wrappers
    html = re.sub(
        r"<li[^>]*>(.*?)</li>",
        lambda m: f"\n- {re.sub(r'<[^>]+>', '', m.group(1)).strip()}",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(r"</?[ou]l[^>]*>", "", html)

    # Inline formatting
    html = re.sub(r"<strong>(.*?)</strong>", r"**\1**", html, flags=re.DOTALL)
    html = re.sub(r"<b>(.*?)</b>", r"**\1**", html, flags=re.DOTALL)
    html = re.sub(r"<em>(.*?)</em>", r"*\1*", html, flags=re.DOTALL)
    html = re.sub(r"<i>(.*?)</i>", r"*\1*", html, flags=re.DOTALL)
    html = re.sub(r"<code>(.*?)</code>", r"`\1`", html, flags=re.DOTALL)

    # Links
    html = re.sub(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", html, flags=re.DOTALL)

    # Paragraphs → text with blank lines
    html = re.sub(
        r"<p[^>]*>(.*?)</p>",
        lambda m: f"\n{m.group(1).strip()}\n",
        html,
        flags=re.DOTALL,
    )

    # Strip remaining HTML tags
    html = re.sub(r"<[^>]+>", "", html)

    # Clean up excessive blank lines
    html = re.sub(r"(\r?\n){4,}", "\n\n\n", html)
    html = re.sub(r"(?m)^[ \t]+$", "", html)

    return html.strip()


def sanitize_title(title):
    """Convert page title to a safe filename component."""
    safe = title.replace("—", "-").replace("/", "-")
    safe = re.sub(r"[^\w\s-]", "", safe)
    safe = re.sub(r"\s+", "-", safe.strip())
    safe = re.sub(r"-+", "-", safe)
    return safe


# ── Main ────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Download Confluence page as markdown")
    parser.add_argument("page_id", help="Confluence page ID")
    parser.add_argument("--format", default="markdown", choices=["markdown", "storage", "json"],
                        help="Output format (default: markdown)")
    parser.add_argument("--output", help="Override output file path")
    args = parser.parse_args()

    load_env()

    # Fetch page with storage body
    expand = "body.storage,version,space,ancestors"
    print(f"🔍 Fetching page {args.page_id}...")
    page = api_request("GET", f"content/{args.page_id}?expand={expand}")

    title = page["title"]
    version = page["version"]["number"]
    space = page.get("space", {}).get("name", "")
    storage_html = page.get("body", {}).get("storage", {}).get("value", "")

    print(f"   Title: {title}")
    print(f"   Version: {version}")
    print(f"   Space: {space}")
    print(f"   Storage HTML: {len(storage_html)} chars")

    if not storage_html:
        fail(
            "No storage content returned for this page",
            causes=["The page may use a different body format (ADF, fabric, etc.)",
                    "The page_id may point to a blog post, not a page"],
            try_=["Try --format json to see the raw page structure",
                  "Confirm the page ID in the Confluence URL"],
        )

    if args.format == "json":
        out_path = Path(args.output) if args.output else Path(f"confluence-page-{args.page_id}.json")
        out_path.write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ JSON saved to: {out_path}")
        return

    if args.format == "storage":
        out_path = Path(args.output) if args.output else Path(f"confluence-page-{args.page_id}.html")
        out_path.write_text(storage_html, encoding="utf-8")
        print(f"✅ Storage HTML saved to: {out_path}")
        return

    # ── Markdown format ─────────────────────────────────────────────────────
    markdown_body = convert_storage_to_markdown(storage_html)

    # Build frontmatter
    frontmatter = f"---\nversion: {version}\ntags:\n  - infrastructure\n---\n"

    full_content = f"{frontmatter}\n{markdown_body}\n"

    # Determine output path
    if args.output:
        out_path = Path(args.output)
    else:
        confluence_dir = Path(__file__).parent / "../confluence"
        confluence_dir.mkdir(exist_ok=True)
        safe_title = sanitize_title(title)
        out_path = confluence_dir / f"{args.page_id}-{safe_title}.md"

    out_path.write_text(full_content, encoding="utf-8")
    print(f"✅ Markdown saved to: {out_path}")
    print(f"   Content: {len(markdown_body)} chars, {markdown_body.count(chr(10))} lines")
    print()
    print("⚠️  Review the file for ADF artifacts that need cleanup:")
    print("   - Orphaned metric numbers, collapsed TOC links, badge text")
    print("   - Add/update tags in frontmatter before uploading")


if __name__ == "__main__":
    main()
