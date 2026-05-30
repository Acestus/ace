#!/usr/bin/env python3
"""
Create a new Confluence Live Doc page from a Markdown file.

Usage:
    python3 create-confluence-page.py <markdown_file> --space-key IPM --title "My Page"
    python3 create-confluence-page.py <markdown_file> --parent-id <PAGE_ID>

After creation the script:
  - Prints the new page ID and URL
  - Renames the markdown file to {pageId}-{Sanitized-Title}.md in the confluence/ directory
  - Writes the page version into the frontmatter
  - Syncs frontmatter tags as Confluence labels

Reads CONFLUENCE_EMAIL and WWEEKS_CONFLUENCE_API_TOKEN from ../.env or .env
"""

import argparse
import base64
import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, CONFLUENCE_COMMON_CAUSES

BASE_URL = "https://<YOUR_ATLASSIAN>.atlassian.net/wiki/rest/api"


# ── Environment & API ───────────────────────────────────────────────────────────


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


def api_request(method, path, data=None):
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
        "Content-Type": "application/json",
    }

    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        http_fail(e, api_name="Confluence", key=path, operation=f"{method} {path}",
                  common_causes=CONFLUENCE_COMMON_CAUSES)


# ── Markdown → ADF conversion ──────────────────────────────────────────────────


def text_node(text, marks=None):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


_VIDEO_URL_RE = re.compile(
    r'^https?://(?:www\.)?(?:'
    r'youtube\.com/watch\?v=[\w-]+'
    r'|youtu\.be/[\w-]+'
    r'|loom\.com/share/[\w-]+'
    r')(?:\S*)$'
)


def widget_extension(url):
    """Create an ADF extension node for the Confluence widget macro (embeds video)."""
    return {
        "type": "extension",
        "attrs": {
            "extensionType": "com.atlassian.confluence.macro.core",
            "extensionKey": "widget",
            "parameters": {
                "macroParams": {
                    "url": {"value": url}
                }
            },
            "layout": "default",
        },
    }


def embed_card(url):
    """Create an ADF embedCard node (full interactive embed — video player, preview)."""
    return {
        "type": "embedCard",
        "attrs": {
            "url": url,
            "layout": "wide",
        },
    }


def block_card(url):
    """Create an ADF blockCard node (rich preview card — title, description, thumbnail)."""
    return {
        "type": "blockCard",
        "attrs": {
            "url": url,
        },
    }


def _parse_embed_directive(line):
    """Parse !embed[label](url) or !embed url directives. Returns (type, url) or None."""
    stripped = line.strip()
    # !embed[label](url)
    m = re.match(r'^!embed\[([^\]]*)\]\(([^)]+)\)$', stripped)
    if m:
        return ("embed", m.group(2))
    # !embed url
    m = re.match(r'^!embed\s+(https?://\S+)$', stripped)
    if m:
        return ("embed", m.group(1))
    # !card[label](url)
    m = re.match(r'^!card\[([^\]]*)\]\(([^)]+)\)$', stripped)
    if m:
        return ("card", m.group(2))
    # !card url
    m = re.match(r'^!card\s+(https?://\S+)$', stripped)
    if m:
        return ("card", m.group(1))
    return None


def _extract_video_url(line):
    """If the line is solely a video URL (bare or as [text](url)), return the URL; else None."""
    stripped = line.strip()
    if _VIDEO_URL_RE.match(stripped):
        return stripped
    m = re.match(r'^\[([^\]]*)\]\(([^)]+)\)$', stripped)
    if m and _VIDEO_URL_RE.match(m.group(2)):
        return m.group(2)
    return None


def parse_inline(text):
    """Parse inline markdown (bold, italic, code, links) into ADF text nodes."""
    nodes = []
    pattern = re.compile(
        r'(\[([^\]]+)\]\(([^)]+)\))'   # [text](url)
        r'|(\*\*(.+?)\*\*)'            # **bold**
        r'|(\*(.+?)\*)'                # *italic*
        r'|(`(.+?)`)'                  # `code`
    )

    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            nodes.append(text_node(text[pos:m.start()]))

        if m.group(2) is not None:  # link
            nodes.append(text_node(m.group(2), [{"type": "link", "attrs": {"href": m.group(3)}}]))
        elif m.group(5) is not None:  # bold
            nodes.append(text_node(m.group(5), [{"type": "strong"}]))
        elif m.group(7) is not None:  # italic
            nodes.append(text_node(m.group(7), [{"type": "em"}]))
        elif m.group(9) is not None:  # code
            nodes.append(text_node(m.group(9), [{"type": "code"}]))

        pos = m.end()

    if pos < len(text):
        nodes.append(text_node(text[pos:]))

    return nodes if nodes else [text_node(text)]


def paragraph(text):
    content = parse_inline(text)
    return {"type": "paragraph", "content": content}


def heading(level, text):
    content = parse_inline(text)
    return {"type": "heading", "attrs": {"level": level}, "content": content}


def parse_table(table_lines):
    """Parse markdown table lines into ADF table node."""
    rows = []
    for line in table_lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)

    if len(rows) > 1 and all(re.match(r'^-+$', c.strip()) for c in rows[1]):
        rows.pop(1)

    adf_rows = []
    for idx, row in enumerate(rows):
        cell_type = "tableHeader" if idx == 0 else "tableCell"
        adf_cells = []
        for cell_text in row:
            adf_cells.append({
                "type": cell_type,
                "content": [paragraph(cell_text)]
            })
        adf_rows.append({"type": "tableRow", "content": adf_cells})

    return {"type": "table", "content": adf_rows}


def md_to_adf(markdown_text):
    """Convert markdown text to ADF document structure."""
    lines = markdown_text.split("\n")
    doc_content = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            level = len(heading_match.group(1))
            doc_content.append(heading(level, heading_match.group(2).strip()))
            i += 1
            continue

        if re.match(r'^---+\s*$', line):
            doc_content.append({"type": "rule"})
            i += 1
            continue

        code_match = re.match(r'^```(\w*)$', line)
        if code_match:
            lang = code_match.group(1)
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            code_node = {"type": "codeBlock", "content": [text_node("\n".join(code_lines))]}
            if lang:
                code_node["attrs"] = {"language": lang}
            doc_content.append(code_node)
            continue

        if line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            doc_content.append(parse_table(table_lines))
            continue

        if re.match(r'^- ', line):
            items = []
            while i < len(lines) and re.match(r'^- ', lines[i]):
                item_text = lines[i][2:].strip()
                items.append({
                    "type": "listItem",
                    "content": [paragraph(item_text)]
                })
                i += 1
            doc_content.append({"type": "bulletList", "content": items})
            continue

        ol_match = re.match(r'^(\d+)\.\s+', line)
        if ol_match:
            items = []
            while i < len(lines) and re.match(r'^\d+\.\s+', lines[i]):
                item_text = re.sub(r'^\d+\.\s+', '', lines[i]).strip()
                items.append({
                    "type": "listItem",
                    "content": [paragraph(item_text)]
                })
                i += 1
            doc_content.append({"type": "orderedList", "attrs": {"order": 1}, "content": items})
            continue

        embed_result = _parse_embed_directive(line)
        if embed_result:
            etype, eurl = embed_result
            if etype == "card":
                doc_content.append(block_card(eurl))
            else:
                doc_content.append(embed_card(eurl))
            i += 1
            continue

        video_url = _extract_video_url(line)
        if video_url:
            doc_content.append(embed_card(video_url))
            i += 1
            continue

        doc_content.append(paragraph(line.strip()))
        i += 1

    return {"version": 1, "type": "doc", "content": doc_content}


# ── Frontmatter parsing ─────────────────────────────────────────────────────────


def parse_frontmatter(text):
    """Parse YAML frontmatter from markdown text. Returns (tags, version, body)."""
    m = re.match(r'^---\r?\n(.+?)\r?\n---\r?\n(.*)', text, re.DOTALL)
    if not m:
        return [], None, text

    frontmatter = m.group(1)
    body = m.group(2)
    tags = []
    version = None
    in_tags = False

    for line in frontmatter.splitlines():
        if re.match(r'^\s*tags:\s*$', line):
            in_tags = True
            continue
        if in_tags:
            tag_match = re.match(r'^\s*-\s+(.+)$', line)
            if tag_match:
                tags.append(tag_match.group(1).strip())
            else:
                in_tags = False
        version_match = re.match(r'^\s*version:\s*(\d+)\s*$', line)
        if version_match:
            version = int(version_match.group(1))

    return tags, version, body


def sync_labels(page_id, tags):
    """Sync frontmatter tags to Confluence page labels."""
    if not tags:
        return

    print(f"🏷️  Syncing {len(tags)} labels...")
    existing = api_request("GET", f"content/{page_id}/label")
    existing_names = [r["name"] for r in existing.get("results", [])]

    to_add = [t for t in tags if t not in existing_names]
    if to_add:
        label_data = [{"prefix": "global", "name": t} for t in to_add]
        api_request("POST", f"content/{page_id}/label", label_data)
        print(f"   Added: {', '.join(to_add)}")

    to_remove = [n for n in existing_names if n not in tags]
    for label in to_remove:
        api_request("DELETE", f"content/{page_id}/label/{label}")
        print(f"   Removed: {label}")

    if not to_add and not to_remove:
        print("   Labels already in sync")


# ── Helpers ──────────────────────────────────────────────────────────────────────


def sanitize_title(title):
    """Convert page title to a safe filename component."""
    safe = title.replace("—", "-").replace("/", "-")
    safe = re.sub(r"[^\w\s-]", "", safe)
    safe = re.sub(r"\s+", "-", safe.strip())
    safe = re.sub(r"-+", "-", safe)
    return safe


def extract_title_from_markdown(body_text):
    """Extract the first H1 heading from the markdown body."""
    m = re.search(r'^#\s+(.+)$', body_text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def write_frontmatter(md_path, version, tags):
    """Write frontmatter with version and tags into the file."""
    content = md_path.read_text(encoding="utf-8")

    # Strip existing frontmatter if present
    content = re.sub(r'^---\r?\n.*?\r?\n---\r?\n', '', content, count=1, flags=re.DOTALL)

    tag_lines = "\n".join(f"  - {t}" for t in tags) if tags else "  - infrastructure"
    frontmatter = f"---\nversion: {version}\ntags:\n{tag_lines}\n---\n"
    md_path.write_text(frontmatter + content, encoding="utf-8")


# ── Main ────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Create a new Confluence page from markdown")
    parser.add_argument("markdown_file", help="Path to the markdown file")
    parser.add_argument("--space-key", default="IPM", help="Confluence space key (default: IPM)")
    parser.add_argument("--title", help="Page title (default: first H1 in the markdown)")
    parser.add_argument("--parent-id", help="Parent page ID")
    parser.add_argument("--dry-run", action="store_true", help="Generate ADF JSON without creating the page")
    args = parser.parse_args()

    load_env()

    # Read markdown
    md_path = Path(args.markdown_file)
    if not md_path.exists():
        fail(
            f"Markdown file not found: {md_path}",
            causes=["Path was mistyped or the file was moved"],
            try_=[f"ls confluence/*.md", "Check the path argument"],
        )

    markdown_text = md_path.read_text(encoding="utf-8")
    print(f"📄 Read {len(markdown_text)} chars from {md_path.name}")

    # Parse frontmatter
    tags, _, body_text = parse_frontmatter(markdown_text)
    if tags:
        print(f"🏷️  Tags: {', '.join(tags)}")

    # Determine title
    title = args.title or extract_title_from_markdown(body_text)
    if not title:
        fail(
            "No page title found",
            causes=["No --title argument supplied and no H1 heading in the markdown"],
            try_=["Add a # Heading to the top of the markdown file",
                  "Or pass --title 'My Page Title'"],
        )
    print(f"📝 Title: {title}")

    # Convert body to ADF
    adf_doc = md_to_adf(body_text)
    adf_json = json.dumps(adf_doc, ensure_ascii=False)
    print(f"🔄 Converted to ADF: {len(adf_doc['content'])} top-level nodes")

    if args.dry_run:
        out_path = md_path.with_suffix(".adf-create.json")
        out_path.write_text(json.dumps(adf_doc, indent=2, ensure_ascii=False))
        print(f"💾 Dry run — saved ADF to {out_path}")
        return

    # Build create payload
    create_body = {
        "type": "page",
        "title": title,
        "space": {"key": args.space_key},
        "body": {
            "atlas_doc_format": {
                "value": adf_json,
                "representation": "atlas_doc_format",
            }
        },
    }

    if args.parent_id:
        create_body["ancestors"] = [{"id": args.parent_id}]

    # Create the page
    print(f"🚀 Creating page in space {args.space_key}...")
    result = api_request("POST", "content", create_body)

    page_id = result["id"]
    page_title = result["title"]
    page_version = result["version"]["number"]
    page_url = f"https://<YOUR_ATLASSIAN>.atlassian.net{result['_links']['webui']}"

    print(f"✅ Page created!")
    print(f"   Page ID: {page_id}")
    print(f"   Title:   {page_title}")
    print(f"   Version: {page_version}")
    print(f"   URL:     {page_url}")

    # Sync labels
    sync_labels(page_id, tags)

    # Rename file to confluence naming convention: {pageId}-{Sanitized-Title}.md
    safe_title = sanitize_title(page_title)
    confluence_dir = Path(__file__).parent / "../confluence"
    confluence_dir.mkdir(exist_ok=True)
    new_filename = f"{page_id}-{safe_title}.md"
    new_path = confluence_dir / new_filename

    if new_path.exists():
        print(f"⚠️  Target file already exists: {new_path}", file=sys.stderr)
        print(f"   Skipping rename. Update frontmatter in the original file.")
        write_frontmatter(md_path, page_version, tags)
    else:
        shutil.move(str(md_path), str(new_path))
        print(f"📁 Moved: {md_path.name} → confluence/{new_filename}")
        write_frontmatter(new_path, page_version, tags)

    print(f"📌 Frontmatter updated with version {page_version}")


if __name__ == "__main__":
    main()
