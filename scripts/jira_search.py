#!/usr/bin/env python3
"""
jira_search.py — Run a JQL query and display results as a clean table.

Usage:
    python3 scripts/jira_search.py --jql 'project = INFRA AND labels = "flow:queue" ORDER BY priority ASC'
    python3 scripts/jira_search.py --jql 'project = INFRA AND labels = "flow:active"' --fields key,summary,labels,duedate
    python3 scripts/jira_search.py --jql '...' --max 25 --json

Common investigation queries:
    # Active tickets (board state)
    project = INFRA AND labels = "flow:active"

    # Queue for a lane (background)
    project = INFRA AND labels in ("flow:queue","flow:waiting") AND labels = "agentic:4" ORDER BY priority ASC

    # Related tickets (same epic)
    project = INFRA AND "Epic Link" = <PROJECT>-100

    # Recently updated in an area
    project = INFRA AND summary ~ "Fabric" ORDER BY updated DESC

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
DEFAULT_FIELDS = ["key", "summary", "status", "labels", "assignee", "duedate", "priority", "parent"]


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


def run_jql(jql: str, fields: list[str], max_results: int, auth: str) -> list[dict]:
    payload = json.dumps({"jql": jql, "fields": fields, "maxResults": max_results}).encode()
    req = urllib.request.Request(
        f"{JIRA_BASE}/rest/api/3/search/jql",
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
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="Jira", operation="POST /rest/api/3/search/jql",
                  common_causes=JIRA_COMMON_CAUSES)


def label_scores(labels: list[str]) -> str:
    scores = {p: "" for p in ("urgency", "importance", "agentic")}
    flow = ""
    for l in labels:
        for p in scores:
            if l.startswith(f"{p}:"):
                scores[p] = l.split(":")[1]
        if l.startswith("flow:"):
            flow = l
    parts = []
    if scores["urgency"]:
        parts.append(f"U{scores['urgency']}")
    if scores["importance"]:
        parts.append(f"I{scores['importance']}")
    if scores["agentic"]:
        parts.append(f"A{scores['agentic']}")
    score_str = "+".join(parts) if parts else ""
    return f"{flow}  {score_str}".strip()


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Run a Jira JQL query")
    parser.add_argument("--jql", required=True, help="JQL query string")
    parser.add_argument("--fields", default=",".join(DEFAULT_FIELDS),
                        help="Comma-separated field names")
    parser.add_argument("--max", type=int, default=20, help="Max results (default 20)")
    parser.add_argument("--json", action="store_true", dest="raw_json", help="Output raw JSON")
    args = parser.parse_args()

    auth = auth_header()
    fields = [f.strip() for f in args.fields.split(",")]
    result = run_jql(args.jql, fields, args.max, auth)

    if args.raw_json:
        print(json.dumps(result, indent=2))
        return

    issues = result.get("issues", [])
    total = result.get("total", 0)
    print(f"{'─'*80}")
    print(f"  {total} results  (showing {len(issues)})")
    print(f"{'─'*80}")

    for issue in issues:
        key = issue["key"]
        f = issue["fields"]
        summary = f.get("summary", "")[:60]
        status = (f.get("status") or {}).get("name", "")
        assignee = (f.get("assignee") or {}).get("displayName", "—")
        due = f.get("duedate", "") or ""
        labels = f.get("labels", [])
        score = label_scores(labels)
        parent = (f.get("parent") or {}).get("key", "")

        print(f"  {key:<12} {summary:<62}")
        print(f"             {status:<18} {score:<30} due:{due or '—'}")
        if parent:
            print(f"             ↳ {parent}")
        print()

    print(f"{'─'*80}")


if __name__ == "__main__":
    main()
