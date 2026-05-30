#!/usr/bin/env python3
"""
notion_sync.py — Sync notion/*.md files to Notion as live pages.

Frontmatter convention (YAML between --- delimiters):
    ---
    notion_id: abc123def456   # written back after first publish; leave blank to create
    title: My Page Title
    parent: optional-parent-page-id   # defaults to NOTION_ROOT_PAGE_ID
    ---

Behaviour:
    - No notion_id  → create new page, write notion_id back into the file
    - Has notion_id → replace page content (clear existing blocks, push current markdown)

Usage:
    python3 scripts/notion_sync.py                         # sync all notion/*.md
    python3 scripts/notion_sync.py --file notion/foo.md   # sync one file
    python3 scripts/notion_sync.py --dry-run              # preview without writing

Environment:
    NOTION_API_KEY
    NOTION_ROOT_PAGE_ID
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from notion_lib import load_env_file, get, post, patch, markdown_to_blocks, get_root_page_id


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) from a markdown file with --- delimiters."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    fm = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, body


def write_frontmatter(path: Path, fm: dict, body: str) -> None:
    """Rewrite a file with updated frontmatter."""
    fm_lines = "\n".join(f"{k}: {v}" for k, v in fm.items())
    path.write_text(f"---\n{fm_lines}\n---\n\n{body}")


# ---------------------------------------------------------------------------
# Notion block replacement
# ---------------------------------------------------------------------------

def clear_page_blocks(page_id: str) -> None:
    """Delete all top-level blocks from a Notion page."""
    clean_id = page_id.replace("-", "")
    resp = get(f"blocks/{clean_id}/children")
    block_ids = [b["id"] for b in resp.get("results", [])]
    for bid in block_ids:
        import urllib.request
        import os
        import json
        url = f"https://api.notion.com/v1/blocks/{bid}"
        req = urllib.request.Request(url, method="DELETE")
        req.add_header("Authorization", f"Bearer {os.environ['NOTION_API_KEY']}")
        req.add_header("Notion-Version", "2022-06-28")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30):
            pass


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------

def sync_file(path: Path, dry_run: bool) -> str:
    """Sync one markdown file to Notion. Returns status string."""
    text = path.read_text()
    fm, body = parse_frontmatter(text)

    title = fm.get("title") or path.stem
    parent_id = fm.get("parent") or get_root_page_id()
    notion_id = fm.get("notion_id", "").strip()

    blocks = markdown_to_blocks(body)

    if not notion_id:
        if dry_run:
            return f"[dry-run] would CREATE: {title}"

        result = post("pages", {
            "parent": {"page_id": parent_id},
            "properties": {
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            },
            "children": blocks,
        })
        new_id = result["id"]
        url = result.get("url", "")
        fm["notion_id"] = new_id
        write_frontmatter(path, fm, body)
        return f"✓ CREATED  {title}\n  id:  {new_id}\n  url: {url}"

    else:
        if dry_run:
            return f"[dry-run] would UPDATE: {title} ({notion_id})"

        patch(f"pages/{notion_id}", {
            "properties": {
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            }
        })
        clear_page_blocks(notion_id)
        patch(f"blocks/{notion_id}/children", {"children": blocks})
        return f"✓ UPDATED  {title}\n  id:  {notion_id}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Sync notion/*.md to Notion pages")
    parser.add_argument("--file", help="Sync a single file instead of all notion/*.md")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]

    if args.file:
        files = [Path(args.file)]
    else:
        files = sorted((repo_root / "notion").glob("*.md"))

    if not files:
        print("No markdown files found.")
        return

    errors = []
    for f in files:
        try:
            print(sync_file(f, args.dry_run))
        except Exception as e:
            msg = f"✗ FAILED   {f.name}: {e}"
            print(msg)
            errors.append(msg)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
