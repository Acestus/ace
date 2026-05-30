#!/usr/bin/env python3
"""
linear_set_flow.py — Set a Linear issue's workflow state by flow label name.

Usage:
    python3 scripts/linear_set_flow.py --key ENG-123 --flow active
    python3 scripts/linear_set_flow.py --key ENG-123 --flow done
    python3 scripts/linear_set_flow.py --key ENG-123 --state "In Review"

Flow→State mapping (override in .env):
    queue   → Backlog
    active  → In Progress
    waiting → In Review
    done    → Done

Environment (reads from .env):
    LINEAR_API_KEY
    LINEAR_STATE_QUEUE, LINEAR_STATE_ACTIVE, LINEAR_STATE_WAITING, LINEAR_STATE_DONE
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from linear_lib import graphql, load_env_file, flow_to_state_name

TEAM_STATES_QUERY = """
query TeamStates($issueId: String!) {
  issues(filter: { identifier: { eq: $issueId } }) {
    nodes {
      id
      team {
        states { nodes { id name type } }
      }
    }
  }
}
"""

UPDATE_STATE_MUTATION = """
mutation UpdateIssueState($id: String!, $stateId: String!) {
  issueUpdate(id: $id, input: { stateId: $stateId }) {
    success
    issue { identifier state { name } }
  }
}
"""

ADD_LABEL_MUTATION = """
mutation AddLabel($id: String!, $labelId: String!) {
  issueUpdate(id: $id, input: { labelIds: [$labelId] }) {
    success
  }
}
"""


def find_state(states: list, name: str) -> dict | None:
    name_lower = name.lower()
    return next(
        (s for s in states if s["name"].lower() == name_lower),
        None
    )


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Set Linear issue state")
    parser.add_argument("--key", required=True, help="Issue identifier, e.g. ENG-123")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--flow", choices=["queue", "active", "waiting", "done"],
                       help="Flow label (maps to Linear state name)")
    group.add_argument("--state", help="Exact Linear state name")
    args = parser.parse_args()

    target_state_name = args.state if args.state else flow_to_state_name(args.flow)

    data = graphql(TEAM_STATES_QUERY, {"issueId": args.key.upper()})
    nodes = data.get("issues", {}).get("nodes", [])
    if not nodes:
        sys.exit(f"Issue {args.key} not found.")

    issue = nodes[0]
    issue_id = issue["id"]
    states = issue["team"]["states"]["nodes"]

    target = find_state(states, target_state_name)
    if not target:
        available = [s["name"] for s in states]
        sys.exit(
            f"State '{target_state_name}' not found in team.\n"
            f"Available: {', '.join(available)}"
        )

    result = graphql(UPDATE_STATE_MUTATION, {"id": issue_id, "stateId": target["id"]})
    update = result.get("issueUpdate", {})
    if update.get("success"):
        new_state = update.get("issue", {}).get("state", {}).get("name", "?")
        print(f"✓ {args.key} → {new_state}")
    else:
        sys.exit(f"Failed to update {args.key}")


if __name__ == "__main__":
    main()
