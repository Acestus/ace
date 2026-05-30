#!/usr/bin/env python3
"""
linear_create_issue.py — Create a new Linear issue.

Usage:
    python3 scripts/linear_create_issue.py --team ENG --title "Fix auth timeout" \
        --priority 2 --label "flow:queue" --label "urgency:2" --label "importance:2"
    python3 scripts/linear_create_issue.py --team ENG --title "..." --description "..."

Environment (reads from .env):
    LINEAR_API_KEY
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from linear_lib import graphql, load_env_file, urgency_to_priority

TEAM_QUERY = """
query GetTeam($key: String!) {
  teams(filter: { key: { eq: $key } }) {
    nodes {
      id
      key
      name
      states { nodes { id name } }
      labels { nodes { id name } }
    }
  }
}
"""

CREATE_MUTATION = """
mutation CreateIssue($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue {
      identifier
      title
      url
      state { name }
      priority
    }
  }
}
"""


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Create a Linear issue")
    parser.add_argument("--team", required=True, help="Team key, e.g. ENG")
    parser.add_argument("--title", required=True, help="Issue title")
    parser.add_argument("--description", default="", help="Issue description (markdown)")
    parser.add_argument("--priority", type=int, choices=[0, 1, 2, 3, 4], default=0,
                        help="0=No Priority 1=Urgent 2=High 3=Medium 4=Low")
    parser.add_argument("--label", action="append", default=[], help="Label name (repeatable)")
    parser.add_argument("--state", default="Backlog", help="Initial state name")
    parser.add_argument("--json", action="store_true", help="Raw JSON output")
    args = parser.parse_args()

    team_data = graphql(TEAM_QUERY, {"key": args.team.upper()})
    teams = team_data.get("teams", {}).get("nodes", [])
    if not teams:
        sys.exit(f"Team '{args.team}' not found.")
    team = teams[0]

    state_map = {s["name"].lower(): s["id"] for s in team["states"]["nodes"]}
    label_map = {l["name"].lower(): l["id"] for l in team["labels"]["nodes"]}

    state_id = state_map.get(args.state.lower())
    if not state_id:
        sys.exit(f"State '{args.state}' not found. Available: {list(state_map.keys())}")

    label_ids = []
    missing_labels = []
    for label_name in args.label:
        lid = label_map.get(label_name.lower())
        if lid:
            label_ids.append(lid)
        else:
            missing_labels.append(label_name)

    if missing_labels:
        print(f"⚠ Labels not found in team (will be skipped): {', '.join(missing_labels)}")
        print(f"  Available labels: {', '.join(label_map.keys())}")

    inp = {
        "teamId": team["id"],
        "title": args.title,
        "priority": args.priority,
        "stateId": state_id,
    }
    if args.description:
        inp["description"] = args.description
    if label_ids:
        inp["labelIds"] = label_ids

    result = graphql(CREATE_MUTATION, {"input": inp})
    issue_result = result.get("issueCreate", {})

    if args.json:
        print(json.dumps(issue_result, indent=2))
        return

    if issue_result.get("success"):
        issue = issue_result["issue"]
        print(f"✓ Created {issue['identifier']} — {issue['title']}")
        print(f"  URL: {issue.get('url', 'N/A')}")
        print(f"  State: {issue['state']['name']}")
    else:
        sys.exit("Failed to create issue.")


if __name__ == "__main__":
    main()
