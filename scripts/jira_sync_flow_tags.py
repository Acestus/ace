#!/usr/bin/env python3
"""
jira_sync_flow_tags.py — Reconcile flow: labels with Jira status.

Detects drift where someone changed the Jira status externally (e.g.,
reviewer kicks a ticket back from Code Review to TO-DO) but the flow:
label was not updated.

Applies the canonical mapping:
    TO-DO        → flow:queue
    In Progress  → flow:active
    Code Review  → flow:waiting
    Done         → flow:done

Usage:
    python3 scripts/jira_sync_flow_tags.py              # dry-run
    python3 scripts/jira_sync_flow_tags.py --apply      # actually fix labels
    python3 scripts/jira_sync_flow_tags.py --json       # JSON output

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

# Canonical: Jira status → expected flow label
# IMPORTANT: flow:active is NEVER set by this script — it's only set by
# rounds/dispatch when the operator explicitly claims a WIP slot.
# "In Progress" stays at whatever flow state it already has.
STATUS_TO_FLOW = {
    "TO-DO": "flow:queue",
    "To Do": "flow:queue",
    # "In Progress" deliberately omitted — flow:active is operator-claimed only
    "Code Review": "flow:waiting",
    "Done": "flow:done",
    "Cancelled": "flow:done",
}

FLOW_LABELS = {"flow:queue", "flow:active", "flow:waiting", "flow:done"}


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


def jira_search(jql: str, fields: list[str], auth: str) -> list[dict]:
    payload = json.dumps({"jql": jql, "fields": fields, "maxResults": 100}).encode()
    req = urllib.request.Request(
        f"{JIRA_BASE}/rest/api/3/search/jql",
        data=payload,
        headers={"Authorization": auth, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read()).get("issues", [])


def update_labels(key: str, remove: list[str], add: list[str], auth: str) -> None:
    body = {"update": {"labels": []}}
    for r in remove:
        body["update"]["labels"].append({"remove": r})
    for a in add:
        body["update"]["labels"].append({"add": a})
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{JIRA_BASE}/rest/api/3/issue/{key}",
        data=payload,
        headers={"Authorization": auth, "Content-Type": "application/json"},
        method="PUT",
    )
    urllib.request.urlopen(req)


def main():
    parser = argparse.ArgumentParser(description="Sync flow labels with Jira status")
    parser.add_argument("--apply", action="store_true", help="Actually update labels (default is dry-run)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    load_env_file()
    auth = auth_header()

    issues = jira_search(
        'project = INFRA AND assignee = currentUser() AND status not in (Done, Cancelled) '
        'ORDER BY updated DESC',
        ["summary", "status", "labels"],
        auth,
    )

    drift = []
    for issue in issues:
        key = issue["key"]
        status = issue["fields"]["status"]["name"]
        labels = issue["fields"].get("labels", [])
        current_flow = [l for l in labels if l in FLOW_LABELS]
        expected_flow = STATUS_TO_FLOW.get(status)

        if not expected_flow:
            continue

        current = current_flow[0] if current_flow else None
        if current == expected_flow:
            continue

        drift.append({
            "key": key,
            "summary": issue["fields"]["summary"][:60],
            "status": status,
            "current_flow": current,
            "expected_flow": expected_flow,
        })

    if args.json:
        print(json.dumps(drift, indent=2))
        return

    if not drift:
        print("  ✓ All flow tags are consistent with Jira status — no drift detected.")
        return

    print(f"  ⚠ Found {len(drift)} ticket(s) with flow tag drift:\n")
    print(f"  {'KEY':12s} {'STATUS':16s} {'CURRENT':16s} → {'EXPECTED':16s} SUMMARY")
    print(f"  {'-'*100}")
    for d in drift:
        current = d['current_flow'] or '(none)'
        print(f"  {d['key']:12s} {d['status']:16s} {current:16s} → {d['expected_flow']:16s} {d['summary']}")

    if not args.apply:
        print(f"\n  Dry run — use --apply to fix these labels.")
        return

    print()
    fixed = 0
    for d in drift:
        remove = [d["current_flow"]] if d["current_flow"] else []
        add = [d["expected_flow"]]
        try:
            update_labels(d["key"], remove, add, auth)
            print(f"  ✓ {d['key']}: {d['current_flow'] or '(none)'} → {d['expected_flow']}")
            fixed += 1
        except urllib.error.HTTPError as e:
            print(f"  ❌ {d['key']}: failed ({e.code}) — {e.read().decode()[:100]}")

    print(f"\n  ✓ Fixed {fixed}/{len(drift)} flow tags.")


if __name__ == "__main__":
    main()
