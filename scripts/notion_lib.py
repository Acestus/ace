#!/usr/bin/env python3
"""
notion_lib.py — Shared helpers for Notion API automation scripts.

Notion uses a REST API at https://api.notion.com/v1/
Auth: Authorization: Bearer {NOTION_API_KEY}
Notion version: 2022-06-28

Environment:
    NOTION_API_KEY       — Integration token from notion.com/my-integrations
    NOTION_ROOT_PAGE_ID  — Optional: default parent page for new pages
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def load_env_file():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() not in os.environ:
            os.environ[k.strip()] = v.strip()


def get_api_key() -> str:
    load_env_file()
    key = os.environ.get("NOTION_API_KEY", "")
    if not key:
        sys.exit(
            "NOTION_API_KEY not set.\n"
            "Add to your .env file:\n"
            "  NOTION_API_KEY=secret_xxxxxxxxxxxx\n"
            "Create an integration at: https://www.notion.so/my-integrations"
        )
    return key


def notion_request(method: str, path: str, body: dict | None = None) -> dict:
    """Make an authenticated request to the Notion API."""
    api_key = get_api_key()
    url = f"{NOTION_API_BASE}/{path.lstrip('/')}"
    payload = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=payload, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        sys.exit(f"Notion API HTTP {e.code}: {body_text}")


def get(path: str) -> dict:
    return notion_request("GET", path)


def post(path: str, body: dict) -> dict:
    return notion_request("POST", path, body)


def patch(path: str, body: dict) -> dict:
    return notion_request("PATCH", path, body)


def markdown_to_blocks(text: str) -> list:
    """Convert plain markdown text into Notion paragraph blocks (simplified)."""
    blocks = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            blocks.append({
                "object": "block", "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]}
            })
        elif stripped.startswith("## "):
            blocks.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": stripped[3:]}}]}
            })
        elif stripped.startswith("### "):
            blocks.append({
                "object": "block", "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": stripped[4:]}}]}
            })
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]}
            })
        elif stripped.startswith("- [ ] ") or stripped.startswith("* [ ] "):
            blocks.append({
                "object": "block", "type": "to_do",
                "to_do": {"rich_text": [{"type": "text", "text": {"content": stripped[6:]}}], "checked": False}
            })
        elif stripped.startswith("- [x] ") or stripped.startswith("* [x] "):
            blocks.append({
                "object": "block", "type": "to_do",
                "to_do": {"rich_text": [{"type": "text", "text": {"content": stripped[6:]}}], "checked": True}
            })
        elif stripped.startswith("```"):
            continue  # simplified — code blocks handled separately
        else:
            blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": stripped}}]}
            })
    return blocks


def page_title(page: dict) -> str:
    """Extract title from a Notion page object."""
    props = page.get("properties", {})
    title_prop = props.get("title") or props.get("Name") or {}
    title_items = title_prop.get("title", [])
    return "".join(t.get("plain_text", "") for t in title_items)
