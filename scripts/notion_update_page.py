#!/usr/bin/env python3
"""
notion_update_page.py — Append content to an existing Notion page.

Usage:
    python3 scripts/notion_update_page.py --page PAGE_ID --file update.md
    python3 scripts/notion_update_page.py --page PAGE_ID --body "New section..."
    python3 scripts/notion_update_page.py --page PAGE_ID --title "New Title"

Environment (reads from .env):
    NOTION_API_KEY
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from notion_lib import load_env_file, patch, post, markdown_to_blocks


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Update a Notion page")
    parser.add_argument("--page", required=True, help="Page ID")
    parser.add_argument("--title", help="New page title")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--body", help="Content to append (markdown)")
    group.add_argument("--file", help="Markdown file to append")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.title:
        patch(f"pages/{args.page}", {
            "properties": {
                "title": {"title": [{"type": "text", "text": {"content": args.title}}]}
            }
        })
        print(f"✓ Title updated")

    text = ""
    if args.file:
        text = Path(args.file).read_text()
    elif args.body:
        text = args.body

    if text:
        blocks = markdown_to_blocks(text)
        result = patch(f"blocks/{args.page}/children", {"children": blocks})
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"✓ {len(blocks)} block(s) appended to page {args.page}")


if __name__ == "__main__":
    main()
