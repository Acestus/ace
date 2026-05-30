#!/usr/bin/env python3
"""
jira_changelog.py — Show the change history for a Jira ticket.

Useful for investigations: see who changed labels, status, assignee, and when.

Usage:
    python3 scripts/jira_changelog.py --key <PROJECT>-366
    python3 scripts/jira_changelog.py --key <PROJECT>-366 --field labels
    python3 scripts/jira_changelog.py --key <PROJECT>-366 --field labels --field status

Environment (reads from .env if not already set):
    CONFLUENCE_EMAIL
    WWEEKS_CONFLUENCE_API_TOKEN
"""

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, JIRA_COMMON_CAUSES

JIRA_BASE = "https://<YOUR_ATLASSIAN>.atlassian.net"


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


def auth_header():
    require_env(
        "CONFLUENCE_EMAIL",
        "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)",
    )
    email = os.environ["CONFLUENCE_EMAIL"]
    token = os.environ["WWEEKS_CONFLUENCE_API_TOKEN"]
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Show Jira ticket change history")
    parser.add_argument("--key", required=True, help="Jira issue key, e.g. <PROJECT>-366")
    parser.add_argument("--field", action="append", dest="fields", metavar="FIELD",
                        help="Filter to specific field(s) — e.g. labels, status, assignee (repeat for multiple)")
    args = parser.parse_args()

    auth = auth_header()
    filter_fields = {f.lower() for f in args.fields} if args.fields else None

    url = f"{JIRA_BASE}/rest/api/3/issue/{args.key}/changelog?maxResults=100"
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="Jira", key=args.key,
                  operation=f"GET /rest/api/3/issue/{args.key}/changelog",
                  common_causes=JIRA_COMMON_CAUSES)

    histories = data.get("values", [])
    print(f"{'─'*70}")
    print(f"  {args.key} — changelog ({len(histories)} entries)")
    print(f"{'─'*70}")

    shown = 0
    for h in reversed(histories):
        date = h.get("created", "")[:10]
        author = (h.get("author") or {}).get("displayName", "?")
        items = h.get("items", [])

        relevant = [
            i for i in items
            if filter_fields is None or i.get("field", "").lower() in filter_fields
        ]
        if not relevant:
            continue

        shown += 1
        print(f"\n  [{date}] {author}")
        for item in relevant:
            field = item.get("field", "?")
            from_val = item.get("fromString") or item.get("from") or "—"
            to_val = item.get("toString") or item.get("to") or "—"
            print(f"    {field}: {from_val!r} → {to_val!r}")

    if shown == 0:
        if filter_fields:
            print(f"\n  No changes to {', '.join(filter_fields)} found.")
        else:
            print("\n  No change history found.")

    print(f"\n{'─'*70}")


if __name__ == "__main__":
    main()
