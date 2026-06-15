#!/usr/bin/env python3
"""linear_dispatch_next.py — Pick the next unclaimed Linear ticket.

The script keeps the dispatch policy in Python:
1. Resume an unclaimed In Progress ticket first.
2. Otherwise pull the next unclaimed queue ticket by Linear priority.
3. Optionally activate the ticket and create the local issue stub.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from linear_lib import graphql, load_env_file, PRIORITY_LABELS, flow_to_state_name

PROJECTS_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECTS_DIR / "scripts"
CLAIMS_FILE = Path("/tmp/rounds-claims.json")

ISSUE_QUERY = """
query DispatchIssues($filter: IssueFilter!, $first: Int!) {
  issues(filter: $filter, first: $first, orderBy: updatedAt) {
    nodes {
      id
      identifier
      title
      priority
      state { name }
      labels { nodes { name } }
      updatedAt
      team { key name }
    }
  }
}
"""


def load_claimed_keys() -> set[str]:
    if not CLAIMS_FILE.exists():
        return set()
    try:
        raw = json.loads(CLAIMS_FILE.read_text())
    except json.JSONDecodeError:
        return set()
    claimed = set()
    for entry in raw.values():
        key = (entry or {}).get("key")
        if key:
            claimed.add(str(key).upper())
    return claimed


def issue_number(identifier: str) -> int:
    try:
        return int(identifier.split("-", 1)[1])
    except (IndexError, ValueError):
        return 10**9


def issue_rank(issue: dict) -> tuple[int, int]:
    return (int(issue.get("priority", 0) or 0), issue_number(issue.get("identifier", "")))


def fetch_issues(filter_obj: dict, first: int) -> list[dict]:
    data = graphql(ISSUE_QUERY, {"filter": filter_obj, "first": first})
    return data.get("issues", {}).get("nodes", [])


def build_filter(state_name: str | None = None, label: str | None = None) -> dict:
    result: dict = {}
    if state_name:
        result["state"] = {"name": {"eq": state_name}}
    if label:
        result["labels"] = {"name": {"eq": label}}
    return result


def pick_next(claimed_keys: set[str]) -> tuple[str, dict] | tuple[None, None]:
    active = [
        issue for issue in fetch_issues(build_filter(state_name=flow_to_state_name("active")), 100)
        if issue.get("identifier", "").upper() not in claimed_keys
    ]
    if active:
        chosen = sorted(active, key=issue_rank)[0]
        return "active", chosen

    queued = [
        issue for issue in fetch_issues(
            {**build_filter(state_name=flow_to_state_name("queue")), **build_filter(label="flow:queue")},
            100,
        )
        if issue.get("identifier", "").upper() not in claimed_keys
    ]
    if queued:
        chosen = sorted(queued, key=issue_rank)[0]
        return "queue", chosen

    return None, None


def activate_issue(key: str, quiet: bool = False) -> None:
    common_kwargs = {
        "check": True,
        "cwd": str(PROJECTS_DIR),
        "text": True,
    }
    if quiet:
        common_kwargs["capture_output"] = True

    subprocess.run(
        ["python3", str(SCRIPTS_DIR / "linear_set_flow.py"), "--key", key, "--flow", "active"],
        **common_kwargs,
    )
    subprocess.run(
        ["python3", str(SCRIPTS_DIR / "linear_create_stub.py"), "--key", key],
        **common_kwargs,
    )


def main() -> None:
    load_env_file()
    parser = argparse.ArgumentParser(description="Pick the next unclaimed Linear ticket")
    parser.add_argument("--activate", action="store_true", help="Mark the chosen ticket active and create its stub")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args()

    source, issue = pick_next(load_claimed_keys())
    if not issue:
        if args.json:
            print(json.dumps({"found": False}))
        else:
            print("No unclaimed Linear tickets found.")
        return

    key = issue["identifier"]
    payload = {
        "found": True,
        "source": source,
        "key": key,
        "title": issue.get("title", ""),
        "priority": issue.get("priority", 0),
        "priority_label": PRIORITY_LABELS.get(issue.get("priority", 0), "Unknown"),
        "state": (issue.get("state") or {}).get("name", ""),
        "team": (issue.get("team") or {}).get("key", ""),
    }

    if args.activate:
        activate_issue(key, quiet=args.json)
        payload["activated"] = True
    else:
        payload["activated"] = False

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print(f"✓ Next Linear ticket: {key} — {issue.get('title', '')}")
    print(f"  Source: {source} | Priority: {payload['priority_label']} | State: {payload['state']}")
    if args.activate:
        print("  Activated and stubbed.")


if __name__ == "__main__":
    main()
