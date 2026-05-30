#!/usr/bin/env python3
"""
jira_context_bundle.py — Fetch comprehensive context for a Jira ticket in one call.

Replaces 3-5 serial script invocations with a single composite fetch.
Used by rounds, ticket-investigator, and start-my-day skills.

Modes:
    work   — Full context: issue + all comments + changelog + related issues
    review — Approval-ready: issue + recent comments + status history
    brief  — Summary only: issue metadata + label state

Usage:
    python3 scripts/jira_context_bundle.py --key <PROJECT>-366
    python3 scripts/jira_context_bundle.py --key <PROJECT>-366 --mode review
    python3 scripts/jira_context_bundle.py --key <PROJECT>-366 --mode brief
    python3 scripts/jira_context_bundle.py --key <PROJECT>-366 --json
    python3 scripts/jira_context_bundle.py --key <PROJECT>-366 --related

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
ISSUE_FIELDS = (
    "summary,status,assignee,labels,description,comment,"
    "customfield_10246,customfield_10280,duedate,priority,parent,issuelinks"
)


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


def jira_get(path: str, auth: str) -> dict | None:
    req = urllib.request.Request(
        f"{JIRA_BASE}{path}",
        headers={"Authorization": auth, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"WARN: GET {path} → {e.code}: {body[:200]}", file=sys.stderr)
        return None


def extract_adf_text(node: dict | None) -> str:
    if not node:
        return ""
    parts = []
    for block in node.get("content", []):
        for item in block.get("content", []):
            if item.get("type") == "text":
                parts.append(item["text"])
        parts.append("\n")
    return "".join(parts).strip()


def fetch_issue(key: str, auth: str) -> dict | None:
    return jira_get(f"/rest/api/3/issue/{key}?fields={ISSUE_FIELDS}", auth)


def fetch_changelog(key: str, auth: str) -> list:
    data = jira_get(f"/rest/api/3/issue/{key}/changelog?maxResults=50", auth)
    if not data:
        return []
    return data.get("values", [])


def fetch_related_issues(key: str, project: str, summary: str, auth: str) -> list:
    """Find sibling tickets by summary keyword overlap."""
    words = [w for w in summary.split() if len(w) >= 4 and w.lower() not in {
        "with", "from", "this", "that", "have", "been", "will",
        "should", "could", "would", "into", "they", "their", "there",
    }]
    keywords = words[:4]
    if not keywords:
        return []

    keyword_clause = " OR ".join(f'summary ~ "{w}"' for w in keywords)
    jql = f'project = {project} AND key != {key} AND ({keyword_clause}) ORDER BY updated DESC'

    data = jira_get(
        f"/rest/api/3/search?jql={urllib.request.quote(jql)}&maxResults=5&fields=summary,status,labels,updated",
        auth,
    )
    if not data:
        return []
    return data.get("issues", [])


def format_flow_state(labels: list) -> str:
    flow = next((l for l in labels if l.startswith("flow:")), None)
    phoenix = next((l for l in labels if l.startswith("phoenix:")), None)
    lane = next((l for l in labels if l.startswith("lane:")), None)
    return f"{flow or 'no-flow'} | {lane or phoenix or 'no-lane'}"


def format_changelog_entry(entry: dict) -> dict:
    return {
        "date": entry.get("created", "")[:10],
        "author": (entry.get("author") or {}).get("displayName", "?"),
        "changes": [
            {
                "field": item.get("field", "?"),
                "from": item.get("fromString") or item.get("from") or "",
                "to": item.get("toString") or item.get("to") or "",
            }
            for item in entry.get("items", [])
        ],
    }


def format_comment(comment: dict) -> dict:
    return {
        "date": comment.get("created", "")[:10],
        "author": (comment.get("author") or {}).get("displayName", "?"),
        "body": extract_adf_text(comment.get("body")),
    }


def format_link(link: dict) -> dict:
    if "outwardIssue" in link:
        target = link["outwardIssue"]
        direction = link.get("type", {}).get("outward", "relates to")
    elif "inwardIssue" in link:
        target = link["inwardIssue"]
        direction = link.get("type", {}).get("inward", "related from")
    else:
        return {"direction": "unknown", "key": "?", "summary": "?"}

    return {
        "direction": direction,
        "key": target.get("key", "?"),
        "summary": target.get("fields", {}).get("summary", "?"),
        "status": target.get("fields", {}).get("status", {}).get("name", "?"),
    }


def build_bundle(key: str, mode: str, include_related: bool, auth: str) -> dict:
    issue_data = fetch_issue(key, auth)
    if not issue_data:
        fail(
            f"Could not fetch Jira issue {key}",
            causes=[
                f"Issue key is wrong or deleted",
                "Account does not have Browse permission on this project",
            ],
            try_=[
                f"python3 scripts/jira_search.py --jql 'key = {key}'",
                f"Verify in browser: https://<YOUR_ATLASSIAN>.atlassian.net/browse/{key}",
            ],
        )

    f = issue_data["fields"]
    project = key.split("-")[0]

    bundle = {
        "key": key,
        "summary": f.get("summary", ""),
        "status": f["status"]["name"],
        "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
        "priority": (f.get("priority") or {}).get("name", ""),
        "due_date": f.get("duedate", ""),
        "labels": f.get("labels", []),
        "flow_state": format_flow_state(f.get("labels", [])),
        "parent": None,
    }

    parent = f.get("parent")
    if parent:
        bundle["parent"] = {
            "key": parent["key"],
            "summary": parent["fields"].get("summary", ""),
        }

    # Description (all modes)
    bundle["description"] = extract_adf_text(f.get("description"))

    # Notes and next steps
    bundle["notes"] = extract_adf_text(f.get("customfield_10246"))
    bundle["next_steps"] = f.get("customfield_10280") or ""

    # Issue links (all modes)
    raw_links = f.get("issuelinks", [])
    bundle["links"] = [format_link(lk) for lk in raw_links]

    # Comments
    all_comments = (f.get("comment") or {}).get("comments", [])
    if mode == "brief":
        bundle["comment_count"] = len(all_comments)
        bundle["comments"] = []
    elif mode == "review":
        bundle["comment_count"] = len(all_comments)
        bundle["comments"] = [format_comment(c) for c in all_comments[-5:]]
    else:  # work
        bundle["comment_count"] = len(all_comments)
        bundle["comments"] = [format_comment(c) for c in all_comments]

    # Changelog
    if mode in ("work", "review"):
        changelog = fetch_changelog(key, auth)
        if mode == "review":
            # Only status/label changes for review mode
            changelog = [
                h for h in changelog
                if any(
                    item.get("field", "").lower() in ("status", "labels")
                    for item in h.get("items", [])
                )
            ]
        bundle["changelog"] = [format_changelog_entry(h) for h in changelog[-20:]]
    else:
        bundle["changelog"] = []

    # Related issues
    if include_related and mode == "work":
        bundle["related"] = [
            {
                "key": i["key"],
                "summary": i["fields"].get("summary", ""),
                "status": i["fields"].get("status", {}).get("name", ""),
                "labels": i["fields"].get("labels", []),
            }
            for i in fetch_related_issues(key, project, bundle["summary"], auth)
        ]
    else:
        bundle["related"] = []

    return bundle


def print_human_readable(bundle: dict):
    print(f"{'═'*70}")
    print(f"  {bundle['key']}: {bundle['summary']}")
    print(f"{'═'*70}")
    print(f"  Status   : {bundle['status']}")
    print(f"  Assignee : {bundle['assignee']}")
    print(f"  Priority : {bundle['priority']}")
    print(f"  Due      : {bundle['due_date'] or '—'}")
    print(f"  Flow     : {bundle['flow_state']}")
    print(f"  Labels   : {' '.join(bundle['labels'])}")

    if bundle.get("parent"):
        print(f"  Parent   : {bundle['parent']['key']} — {bundle['parent']['summary']}")

    if bundle["description"]:
        print(f"\n{'─'*70}")
        print(f"  DESCRIPTION")
        print(f"{'─'*70}")
        print(f"  {bundle['description'][:1200]}")

    if bundle["notes"]:
        print(f"\n{'─'*70}")
        print(f"  NOTES")
        print(f"{'─'*70}")
        print(f"  {bundle['notes']}")

    if bundle["next_steps"]:
        print(f"\n{'─'*70}")
        print(f"  NEXT STEPS")
        print(f"{'─'*70}")
        print(f"  {bundle['next_steps']}")

    if bundle["links"]:
        print(f"\n{'─'*70}")
        print(f"  LINKS ({len(bundle['links'])})")
        print(f"{'─'*70}")
        for lk in bundle["links"]:
            print(f"  {lk['direction']} → {lk['key']}: {lk['summary']} [{lk['status']}]")

    if bundle["comments"]:
        print(f"\n{'─'*70}")
        print(f"  COMMENTS ({bundle['comment_count']} total, showing {len(bundle['comments'])})")
        print(f"{'─'*70}")
        for c in bundle["comments"]:
            body_preview = c["body"][:300].replace("\n", "\n    ")
            print(f"  [{c['date']}] {c['author']}:")
            print(f"    {body_preview}")
            print()

    if bundle["changelog"]:
        print(f"{'─'*70}")
        print(f"  CHANGELOG (recent {len(bundle['changelog'])} entries)")
        print(f"{'─'*70}")
        for entry in bundle["changelog"][-10:]:
            print(f"  [{entry['date']}] {entry['author']}")
            for ch in entry["changes"]:
                print(f"    {ch['field']}: {ch['from']!r} → {ch['to']!r}")

    if bundle["related"]:
        print(f"\n{'─'*70}")
        print(f"  RELATED ISSUES ({len(bundle['related'])})")
        print(f"{'─'*70}")
        for r in bundle["related"]:
            flow = format_flow_state(r.get("labels", []))
            print(f"  {r['key']}: {r['summary']} [{r['status']}] ({flow})")

    print(f"\n{'═'*70}")


def main():
    load_env_file()

    parser = argparse.ArgumentParser(
        description="Fetch comprehensive Jira ticket context in one call"
    )
    parser.add_argument("--key", required=True, help="Jira issue key, e.g. <PROJECT>-366")
    parser.add_argument("--mode", default="work", choices=["work", "review", "brief"],
                        help="Context depth: work (full), review (approval-ready), brief (metadata only)")
    parser.add_argument("--json", action="store_true", dest="raw_json",
                        help="Output as structured JSON")
    parser.add_argument("--related", action="store_true",
                        help="Include related/sibling ticket discovery")
    args = parser.parse_args()

    auth = auth_header()
    bundle = build_bundle(args.key, args.mode, args.related, auth)

    if args.raw_json:
        print(json.dumps(bundle, indent=2))
    else:
        print_human_readable(bundle)


if __name__ == "__main__":
    main()
