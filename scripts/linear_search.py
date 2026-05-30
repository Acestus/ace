#!/usr/bin/env python3
"""
linear_search.py — Search Linear issues with filters.

Usage:
    python3 scripts/linear_search.py --state "In Progress"
    python3 scripts/linear_search.py --label flow:active
    python3 scripts/linear_search.py --label flow:queue --priority 1
    python3 scripts/linear_search.py --team ENG --state Backlog --max 25
    python3 scripts/linear_search.py --label flow:queue --json

Environment (reads from .env):
    LINEAR_API_KEY
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from linear_lib import graphql, load_env_file, PRIORITY_LABELS

SEARCH_QUERY = """
query SearchIssues($filter: IssueFilter!, $first: Int!) {
  issues(filter: $filter, first: $first, orderBy: updatedAt) {
    nodes {
      identifier
      title
      priority
      state { name }
      assignee { name }
      labels { nodes { name } }
      dueDate
      updatedAt
      team { key name }
    }
  }
}
"""


def build_filter(args) -> dict:
    f: dict = {}
    if args.state:
        f["state"] = {"name": {"eq": args.state}}
    if args.team:
        f["team"] = {"key": {"eq": args.team.upper()}}
    if args.priority is not None:
        f["priority"] = {"eq": args.priority}
    if args.label:
        f["labels"] = {"name": {"eq": args.label}}
    return f


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Search Linear issues")
    parser.add_argument("--state", help="Workflow state name, e.g. 'In Progress'")
    parser.add_argument("--team", help="Team key, e.g. ENG")
    parser.add_argument("--priority", type=int, choices=[0, 1, 2, 3, 4],
                        help="0=No Priority 1=Urgent 2=High 3=Medium 4=Low")
    parser.add_argument("--label", help="Label name, e.g. flow:active")
    parser.add_argument("--max", type=int, default=25, help="Max results")
    parser.add_argument("--json", action="store_true", help="Raw JSON output")
    args = parser.parse_args()

    f = build_filter(args)
    if not f:
        sys.exit("Provide at least one filter (--state, --team, --priority, --label)")

    data = graphql(SEARCH_QUERY, {"filter": f, "first": args.max})
    issues = data.get("issues", {}).get("nodes", [])

    if args.json:
        print(json.dumps(issues, indent=2))
        return

    if not issues:
        print("No issues found.")
        return

    print(f"\n{'ID':<12} {'State':<18} {'Pri':<12} {'Title'}")
    print("-" * 80)
    for i in issues:
        ident = i.get("identifier", "?")
        state = (i.get("state") or {}).get("name", "?")
        pri = PRIORITY_LABELS.get(i.get("priority", 0), "?")
        title = i.get("title", "")[:48]
        labels = [n["name"] for n in (i.get("labels") or {}).get("nodes", [])]
        label_str = f"  [{', '.join(labels)}]" if labels else ""
        print(f"{ident:<12} {state:<18} {pri:<12} {title}{label_str}")
    print(f"\n{len(issues)} result(s)")


if __name__ == "__main__":
    main()
