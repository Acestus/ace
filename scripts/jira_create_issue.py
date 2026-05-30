#!/usr/bin/env python3
"""
jira_create_issue.py — Create a new Jira issue (story/task/bug) with labels, epic, and score.

Usage:
    python3 scripts/jira_create_issue.py \
        --project INFRA \
        --type Story \
        --summary "Short title of the work" \
        --description "Full description of the work to be done." \
        --epic <PROJECT>-100 \
        --label urgency:3 --label impact:3 --label effort:2 \
        --label flow:queue \
        --label "phoenix:manual"

    # Dry run — show what would be created
    python3 scripts/jira_create_issue.py \
        --summary "Test issue" --dry-run

Prints the created issue key on stdout (e.g. <PROJECT>-412).

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


def adf_paragraph(text: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def resolve_epic_id(epic_key: str, auth: str) -> str:
    url = f"{JIRA_BASE}/rest/api/3/issue/{epic_key}?fields=summary"
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            return data["id"]
    except urllib.error.HTTPError as e:
        print(f"WARN: could not resolve epic {epic_key}: {e.code}", file=sys.stderr)
        return epic_key


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Create a Jira issue")
    parser.add_argument("--project", default="INFRA", help="Jira project key (default: INFRA)")
    parser.add_argument("--type", dest="issue_type", default="Story",
                        choices=["Story", "Task", "Bug", "Epic", "Subtask"],
                        help="Issue type (default: Story)")
    parser.add_argument("--summary", required=True, help="Issue summary / title")
    parser.add_argument("--description", help="Issue description (plain text)")
    parser.add_argument("--epic", help="Parent epic key, e.g. <PROJECT>-100")
    parser.add_argument("--label", action="append", dest="labels", metavar="LABEL",
                        help="Label to add (repeat for multiple)")
    parser.add_argument("--assignee", help="Assignee account ID (optional)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be created without making API calls")
    args = parser.parse_args()

    auth = auth_header()

    fields: dict = {
        "project": {"key": args.project},
        "issuetype": {"name": args.issue_type},
        "summary": args.summary,
    }

    if args.description:
        fields["description"] = adf_paragraph(args.description)

    if args.labels:
        fields["labels"] = args.labels

    if args.epic:
        fields["parent"] = {"key": args.epic}

    if args.assignee:
        fields["assignee"] = {"id": args.assignee}

    if args.dry_run:
        preview = {
            "dry_run": True,
            "project": args.project,
            "type": args.issue_type,
            "summary": args.summary,
            "description": args.description or "(none)",
            "labels": args.labels or [],
            "epic": args.epic or "(none)",
            "assignee": args.assignee or "(unassigned)",
        }
        print(json.dumps(preview, indent=2))
        print(f"[DRY RUN] Would create {args.issue_type} in {args.project}: {args.summary}", file=sys.stderr)
        return

    payload = json.dumps({"fields": fields}).encode()
    req = urllib.request.Request(
        f"{JIRA_BASE}/rest/api/3/issue",
        data=payload,
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="Jira", operation="POST /rest/api/3/issue",
                  common_causes=JIRA_COMMON_CAUSES)

    key = result["key"]
    print(key)
    print(f"✓ Created {key}: {args.summary}", file=sys.stderr)
    print(f"  https://<YOUR_ATLASSIAN>.atlassian.net/browse/{key}", file=sys.stderr)


if __name__ == "__main__":
    main()
