#!/usr/bin/env python3
"""
notion_create_page.py — Create a new Notion page under a parent.

Usage:
    python3 scripts/notion_create_page.py --parent PAGE_ID --title "My Runbook" --file content.md
    python3 scripts/notion_create_page.py --parent PAGE_ID --title "Quick note" --body "Some text"

Environment (reads from .env):
    NOTION_API_KEY
    NOTION_ROOT_PAGE_ID   (used as parent if --parent not specified)
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from notion_lib import load_env_file, post, markdown_to_blocks, get_root_page_id


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Create a Notion page")
    parser.add_argument("--parent", help="Parent page ID (overrides NOTION_ROOT_PAGE_ID)")
    parser.add_argument("--title", required=True, help="Page title")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--body", help="Page content as plain text/markdown")
    group.add_argument("--file", help="Path to markdown file for content")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    parent_id = args.parent or get_root_page_id()

    text = ""
    if args.file:
        text = Path(args.file).read_text()
    elif args.body:
        text = args.body

    children = markdown_to_blocks(text) if text else []

    payload = {
        "parent": {"page_id": parent_id},
        "properties": {
            "title": {"title": [{"type": "text", "text": {"content": args.title}}]}
        },
        "children": children,
    }

    result = post("pages", payload)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    page_id = result.get("id", "?")
    url = result.get("url", "")
    print(f"✓ Created page: {args.title}")
    print(f"  ID:  {page_id}")
    print(f"  URL: {url}")


if __name__ == "__main__":
    main()
