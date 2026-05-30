#!/usr/bin/env python3
"""
linear_fetch_issue.py — Fetch and display a Linear issue cleanly.

Usage:
    python3 scripts/linear_fetch_issue.py --key ENG-123
    python3 scripts/linear_fetch_issue.py --key ENG-123 --json

Environment (reads from .env):
    LINEAR_API_KEY
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from linear_lib import graphql, load_env_file, format_issue_header, PRIORITY_LABELS

ISSUE_QUERY = """
query FetchIssue($id: String!) {
  issue(id: $id) {
    id
    identifier
    title
    description
    priority
    state { name type }
    assignee { name email }
    labels { nodes { name } }
    dueDate
    createdAt
    updatedAt
    team { name key }
    comments(orderBy: createdAt) {
      nodes {
        createdAt
        user { name }
        body
      }
    }
    parent { identifier title }
    children { nodes { identifier title state { name } } }
  }
}
"""


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Fetch a Linear issue")
    parser.add_argument("--key", required=True, help="Issue identifier, e.g. ENG-123")
    parser.add_argument("--json", action="store_true", help="Raw JSON output")
    args = parser.parse_args()

    data = graphql(ISSUE_QUERY, {"id": args.key.upper()})
    issue = data.get("issue")
    if not issue:
        sys.exit(f"Issue {args.key} not found.")

    if args.json:
        print(json.dumps(issue, indent=2))
        return

    labels = [n["name"] for n in (issue.get("labels") or {}).get("nodes", [])]
    comments = (issue.get("comments") or {}).get("nodes", [])
    children = (issue.get("children") or {}).get("nodes", [])
    state = (issue.get("state") or {})
    assignee = (issue.get("assignee") or {})
    team = (issue.get("team") or {})
    parent = issue.get("parent")

    print(f"\n{'='*60}")
    print(f"  {issue['identifier']} — {issue['title']}")
    print(f"{'='*60}")
    print(f"  Team:      {team.get('name', '?')} ({team.get('key', '?')})")
    print(f"  State:     {state.get('name', '?')}")
    print(f"  Priority:  {PRIORITY_LABELS.get(issue.get('priority', 0), '?')}")
    print(f"  Assignee:  {assignee.get('name', 'Unassigned')}")
    print(f"  Due:       {issue.get('dueDate', 'None')}")
    print(f"  Labels:    {', '.join(labels) if labels else 'None'}")
    if parent:
        print(f"  Parent:    {parent['identifier']} — {parent['title']}")
    print()

    desc = (issue.get("description") or "").strip()
    if desc:
        print("--- Description ---")
        print(desc)
        print()

    if children:
        print("--- Sub-issues ---")
        for c in children:
            print(f"  {c['identifier']} [{c['state']['name']}] — {c['title']}")
        print()

    if comments:
        print(f"--- Comments ({len(comments)}) ---")
        for c in comments:
            who = (c.get("user") or {}).get("name", "?")
            when = c.get("createdAt", "")[:10]
            print(f"\n  [{when}] {who}")
            print("  " + c.get("body", "").replace("\n", "\n  "))
        print()


if __name__ == "__main__":
    main()
