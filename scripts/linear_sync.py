#!/usr/bin/env python3
"""
linear_sync.py — Sync issues/*.md stubs back to Linear.

Reads frontmatter and content from each stub file and pushes updates
to the corresponding Linear issue (title, description, priority, state, labels).

Frontmatter fields used:
    LINEAR:    ACE-5          # issue identifier (required)
    title:     My Issue       # synced to Linear title
    flow:      queue          # maps to Linear state via flow_to_state_name()
    urgency:   3              # maps to Linear priority
    importance: 3             # used to set importance:N label
    due:       2024-03-01     # synced to Linear dueDate (YYYY-MM-DD or blank)

Description: content under the "## Description" heading is synced to Linear.

Usage:
    python3 scripts/linear_sync.py                                      # sync all
    python3 scripts/linear_sync.py --file "issues/ACE-5 - Foo/ACE-5 - Foo.md"
    python3 scripts/linear_sync.py --dry-run                            # preview

Environment:
    LINEAR_API_KEY
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from linear_lib import (
    graphql, load_env_file, flow_to_state_name,
    urgency_to_priority, PRIORITY_LABELS,
)

# ---------------------------------------------------------------------------
# GraphQL
# ---------------------------------------------------------------------------

FETCH_ISSUE = """
query FetchIssue($id: String!) {
  issue(id: $id) {
    id identifier title
    team { id key labels { nodes { id name } } }
    state { id name }
    labels { nodes { id name } }
  }
}
"""

FETCH_STATES = """
query FetchStates($teamId: ID!) {
  workflowStates(filter: { team: { id: { eq: $teamId } } }) {
    nodes { id name }
  }
}
"""

UPDATE_ISSUE = """
mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(id: $id, input: $input) {
    success
    issue { identifier title state { name } priority }
  }
}
"""

# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    fm = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, body


def extract_description(body: str) -> str:
    """Return the text between ## Description and the next ## heading."""
    match = re.search(r"## Description\s*\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------

def sync_file(path: Path, dry_run: bool) -> str:
    text = path.read_text()
    fm, body = parse_frontmatter(text)

    identifier = fm.get("LINEAR", "").strip().upper()
    if not identifier:
        return f"⚠ SKIP  {path.name} — no LINEAR: field in frontmatter"

    title = fm.get("title", "").strip()
    flow = fm.get("flow", "queue").strip()
    urgency = int(fm.get("urgency", 5))
    importance = int(fm.get("importance", 5))
    due = fm.get("due", "").strip()
    if due.lower() in ("none", "null", ""):
        due = ""
    description = extract_description(body)
    priority = urgency_to_priority(urgency)
    target_state_name = flow_to_state_name(flow)

    if dry_run:
        return (
            f"[dry-run] would UPDATE {identifier}\n"
            f"  title:       {title}\n"
            f"  state:       {target_state_name}\n"
            f"  priority:    {PRIORITY_LABELS[priority]}\n"
            f"  urgency lbl: urgency:{urgency}\n"
            f"  importance:  importance:{importance}\n"
            f"  due:         {due or '(none)'}"
        )

    issue_data = graphql(FETCH_ISSUE, {"id": identifier}).get("issue")
    if not issue_data:
        return f"✗ NOT FOUND {identifier}"

    issue_uuid = issue_data["id"]
    team = issue_data["team"]
    team_id = team["id"]
    team_labels = {l["name"]: l["id"] for l in team["labels"]["nodes"]}

    states_data = graphql(FETCH_STATES, {"teamId": team_id})
    state_map = {s["name"]: s["id"] for s in states_data["workflowStates"]["nodes"]}
    state_id = state_map.get(target_state_name)

    desired_label_names = {f"urgency:{urgency}", f"importance:{importance}", f"flow:{flow}"}
    label_ids = [team_labels[n] for n in desired_label_names if n in team_labels]
    missing = desired_label_names - set(team_labels.keys())
    if missing:
        print(f"  ⚠ Labels not found (skipped): {', '.join(sorted(missing))}")

    update_input = {"priority": priority, "labelIds": label_ids}
    if title:
        update_input["title"] = title
    if description:
        update_input["description"] = description
    if state_id:
        update_input["stateId"] = state_id
    if due:
        update_input["dueDate"] = due

    result = graphql(UPDATE_ISSUE, {"id": issue_uuid, "input": update_input})
    updated = result["issueUpdate"]["issue"]
    return (
        f"✓ UPDATED  {updated['identifier']} — {updated['title']}\n"
        f"  state:    {updated['state']['name']}\n"
        f"  priority: {PRIORITY_LABELS[updated['priority']]}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Sync issue stubs to Linear")
    parser.add_argument("--file", help="Sync a single stub file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]

    if args.file:
        files = [Path(args.file)]
    else:
        files = sorted((repo_root / "issues").rglob("*.md"))

    if not files:
        print("No stub files found.")
        return

    errors = []
    for f in files:
        try:
            print(sync_file(f, args.dry_run))
        except Exception as e:
            msg = f"✗ FAILED   {f.name}: {e}"
            print(msg)
            errors.append(msg)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
