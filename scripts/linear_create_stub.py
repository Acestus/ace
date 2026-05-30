#!/usr/bin/env python3
"""
linear_create_stub.py — Create a local issue markdown stub for a Linear issue.

Usage:
    python3 scripts/linear_create_stub.py --key ENG-123
    python3 scripts/linear_create_stub.py --key ENG-123 --projects-dir /home/wweeks/git/projects

Creates: issues/{identifier} - {title}/{identifier} - {title}.md

Environment (reads from .env):
    LINEAR_API_KEY
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from linear_lib import graphql, load_env_file, PRIORITY_LABELS, priority_to_urgency

ISSUE_QUERY = """
query FetchIssue($identifier: String!) {
  issues(filter: { identifier: { eq: $identifier } }) {
    nodes {
      id identifier title description priority
      state { name }
      assignee { name }
      labels { nodes { name } }
      dueDate
      team { name key }
    }
  }
}
"""


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Create local stub for a Linear issue")
    parser.add_argument("--key", required=True, help="Issue identifier, e.g. ENG-123")
    parser.add_argument("--projects-dir",
                        default="/home/wweeks/git/projects",
                        help="Path to projects repo")
    args = parser.parse_args()

    data = graphql(ISSUE_QUERY, {"identifier": args.key.upper()})
    nodes = data.get("issues", {}).get("nodes", [])
    if not nodes:
        sys.exit(f"Issue {args.key} not found.")
    issue = nodes[0]

    title = issue["title"]
    identifier = issue["identifier"]
    labels = [n["name"] for n in (issue.get("labels") or {}).get("nodes", [])]
    state = (issue.get("state") or {}).get("name", "Backlog")
    priority = issue.get("priority", 0)
    urgency = priority_to_urgency(priority)
    team = (issue.get("team") or {}).get("name", "")
    due = issue.get("dueDate", "")
    today = date.today().isoformat()

    folder_name = f"{identifier} - {slugify(title)}"
    projects_dir = Path(args.projects_dir)
    folder = projects_dir / "issues" / folder_name
    if folder.exists():
        print(f"⚠ Stub already exists: {folder}")
        return

    folder.mkdir(parents=True, exist_ok=True)
    stub_file = folder / f"{folder_name}.md"

    flow = "queue"
    for lbl in labels:
        if lbl.startswith("flow:"):
            flow = lbl.split(":", 1)[1]

    content = f"""---
LINEAR: {identifier}
title: {title}
team: {team}
state: {state}
flow: {flow}
urgency: {urgency}
due: {due}
created: {today}
---

## Description

{issue.get("description") or "*(no description)*"}

## Actions

### {today}

WORKLOG: Stub created from Linear {identifier}

## Follow-up

Status: {state}
TODO:
- [ ] Review and scope work
"""

    stub_file.write_text(content)
    print(f"✓ Stub created: issues/{folder_name}/{folder_name}.md")


if __name__ == "__main__":
    main()
