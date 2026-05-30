#!/usr/bin/env python3
"""
jira_set_flow.py — Update the flow label on a Jira ticket.

Removes all existing flow:* labels and adds the new one.

Usage:
    python3 scripts/jira_set_flow.py --key <PROJECT>-366 --flow waiting
    python3 scripts/jira_set_flow.py --key <PROJECT>-366 --flow active
    python3 scripts/jira_set_flow.py --key <PROJECT>-366 --flow done --transition
    python3 scripts/jira_set_flow.py --key <PROJECT>-366 --flow queue
    python3 scripts/jira_set_flow.py --key <PROJECT>-366 --flow done --dry-run
    python3 scripts/jira_set_flow.py --key <PROJECT>-366 --flow done --json

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
FLOW_LABELS = {"flow:queue", "flow:active", "flow:waiting", "flow:done"}

# Jira status transition IDs for the INFRA project
TRANSITIONS = {
    "queue":   "101",  # → To Do
    "active":  "41",   # → In Progress
    "waiting": "61",   # → Code Review
    "done":    "31",   # → Done
}


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


def jira_get(path: str, auth: str) -> dict:
    req = urllib.request.Request(
        f"{JIRA_BASE}{path}",
        headers={"Authorization": auth, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="Jira", operation=f"GET {path}",
                  common_causes=JIRA_COMMON_CAUSES)


def jira_post(path: str, body: dict, auth: str) -> dict:
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{JIRA_BASE}{path}",
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
            body_bytes = resp.read()
            return json.loads(body_bytes) if body_bytes.strip() else {}
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="Jira", operation=f"POST {path}",
                  common_causes=JIRA_COMMON_CAUSES)


def jira_put(path: str, body: dict, auth: str) -> None:
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{JIRA_BASE}{path}",
        data=payload,
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        http_fail(e, api_name="Jira", operation=f"PUT {path}",
                  common_causes=JIRA_COMMON_CAUSES)


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Set Jira flow label")
    parser.add_argument("--key", required=True, help="Jira issue key, e.g. <PROJECT>-366")
    parser.add_argument("--flow", required=True, choices=["queue", "active", "waiting", "done"],
                        help="Target flow state")
    parser.add_argument("--transition", action="store_true",
                        help="Also transition the Jira status (In Progress / Done / etc.)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without making API calls")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="Output result as JSON to stdout")
    args = parser.parse_args()

    auth = auth_header()
    target = f"flow:{args.flow}"

    issue = jira_get(f"/rest/api/3/issue/{args.key}?fields=labels", auth)
    current_labels = issue["fields"].get("labels", [])

    other_labels = [l for l in current_labels if l not in FLOW_LABELS]
    new_labels = other_labels + [target]
    removed = [l for l in current_labels if l in FLOW_LABELS]

    result = {
        "key": args.key,
        "flow_from": removed[0] if removed else None,
        "flow_to": target,
        "transition_id": TRANSITIONS[args.flow] if args.transition else None,
        "changed": set(current_labels) != set(new_labels),
        "dry_run": args.dry_run,
    }

    if args.dry_run:
        if set(current_labels) == set(new_labels):
            result["message"] = f"{args.key} already has {target} — no change needed"
        else:
            result["message"] = f"Would change {args.key}: {' + '.join(removed) if removed else '(none)'} → {target}"
            if args.transition:
                result["message"] += f" + status transition (id={TRANSITIONS[args.flow]})"
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"[DRY RUN] {result['message']}")
        return

    if set(current_labels) == set(new_labels):
        result["message"] = f"{args.key} already has {target} — no change"
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"✓ {result['message']}")
        return

    jira_put(f"/rest/api/3/issue/{args.key}", {"fields": {"labels": new_labels}}, auth)
    result["message"] = f"{args.key}: {' + '.join(removed) if removed else '(none)'} → {target}"
    if not args.json_output:
        print(f"✓ {result['message']}")

    if args.transition:
        tid = TRANSITIONS[args.flow]
        jira_post(f"/rest/api/3/issue/{args.key}/transitions", {"transition": {"id": tid}}, auth)
        result["transitioned"] = True
        if not args.json_output:
            print(f"✓ {args.key}: status transitioned (id={tid})")

    if args.json_output:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
