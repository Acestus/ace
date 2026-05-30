#!/usr/bin/env python3
"""
notion_search.py — Search Notion pages by title text.

Usage:
    python3 scripts/notion_search.py --query "Infrastructure runbook"
    python3 scripts/notion_search.py --query "INFRA" --type page
    python3 scripts/notion_search.py --query "Cost" --json

Environment (reads from .env):
    NOTION_API_KEY
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from notion_lib import load_env_file, post, page_title


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Search Notion pages")
    parser.add_argument("--query", required=True, help="Search text")
    parser.add_argument("--type", choices=["page", "database"], default="page")
    parser.add_argument("--max", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    body = {
        "query": args.query,
        "filter": {"value": args.type, "property": "object"},
        "page_size": args.max,
    }
    data = post("search", body)
    results = data.get("results", [])

    if args.json:
        print(json.dumps(results, indent=2))
        return

    if not results:
        print("No results found.")
        return

    print(f"\n{'ID':<36}  {'Title'}")
    print("-" * 80)
    for p in results:
        pid = p.get("id", "?")
        title = page_title(p) or "(untitled)"
        url = p.get("url", "")
        print(f"{pid}  {title}")
        if url:
            print(f"{'':36}  {url}")
    print(f"\n{len(results)} result(s)")


if __name__ == "__main__":
    main()
