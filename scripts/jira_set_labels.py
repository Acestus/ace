#!/usr/bin/env python3
"""
jira_set_labels.py — Add and/or remove arbitrary labels on a Jira ticket.

For flow label changes, prefer jira_set_flow.py (it also handles Jira status transitions).
Use this script for scoring labels: urgency, importance, agentic, constraint, way.

Usage:
    # Change urgency score
    python3 scripts/jira_set_labels.py --key <PROJECT>-366 --remove "urgency:3" --add "urgency:1"

    # Change multiple scores at once (stakeholder escalation)
    python3 scripts/jira_set_labels.py --key <PROJECT>-366 \
        --remove "urgency:3" --add "urgency:1" \
        --remove "importance:3" --add "importance:1"

    # Add a label without removing anything
    python3 scripts/jira_set_labels.py --key <PROJECT>-366 --add "way:flow"

    # Show current labels without changing anything
    python3 scripts/jira_set_labels.py --key <PROJECT>-366

    # Dry run — show what would change
    python3 scripts/jira_set_labels.py --key <PROJECT>-366 --remove "urgency:3" --add "urgency:1" --dry-run

    # JSON output
    python3 scripts/jira_set_labels.py --key <PROJECT>-366 --remove "urgency:3" --add "urgency:1" --json

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


def jira_get(path: str, auth: str) -> dict:
    req = urllib.request.Request(
        f"{JIRA_BASE}{path}",
        headers={"Authorization": auth, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


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


def print_labels(labels: list[str], key: str) -> None:
    flow = [l for l in labels if l.startswith("flow:")]
    scores = [l for l in labels if any(l.startswith(p) for p in ("urgency:", "importance:", "agentic:"))]
    other = [l for l in labels if l not in flow and l not in scores]
    print(f"  {key} labels:")
    if flow:
        print(f"    flow   : {' '.join(flow)}")
    if scores:
        print(f"    scores : {' '.join(scores)}")
    if other:
        print(f"    other  : {' '.join(other)}")


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Add/remove Jira labels")
    parser.add_argument("--key", required=True, help="Jira issue key, e.g. <PROJECT>-366")
    parser.add_argument("--add", action="append", dest="add_labels", metavar="LABEL",
                        help="Label to add (repeat for multiple)")
    parser.add_argument("--remove", action="append", dest="remove_labels", metavar="LABEL",
                        help="Label to remove (repeat for multiple)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without making API calls")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="Output result as JSON to stdout")
    args = parser.parse_args()

    auth = auth_header()

    issue = jira_get(f"/rest/api/3/issue/{args.key}?fields=labels,summary", auth)
    summary = issue["fields"].get("summary", "")
    current = list(issue["fields"].get("labels", []))

    if not args.add_labels and not args.remove_labels:
        if args.json_output:
            print(json.dumps({"key": args.key, "summary": summary, "labels": current}, indent=2))
        else:
            print(f"\n  {args.key}: {summary}")
            print_labels(current, args.key)
        return

    to_remove = set(args.remove_labels or [])
    to_add = list(args.add_labels or [])

    new_labels = [l for l in current if l not in to_remove] + [l for l in to_add if l not in current]

    removed = [l for l in to_remove if l in current]
    missing = [l for l in to_remove if l not in current]
    added = [l for l in to_add if l not in current]
    already = [l for l in to_add if l in current]

    result = {
        "key": args.key,
        "removed": removed,
        "added": added,
        "missing": missing,
        "already_present": already,
        "changed": current != new_labels,
        "dry_run": args.dry_run,
        "labels_before": current,
        "labels_after": new_labels,
    }

    if missing:
        print(f"  WARN: {args.key} — labels not found (skipped): {' '.join(missing)}", file=sys.stderr)

    if current == new_labels:
        result["message"] = f"{args.key}: no change — labels already match target"
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"  {result['message']}")
        return

    if args.dry_run:
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            if removed:
                print(f"  [DRY RUN] {args.key}: would remove {' '.join(removed)}")
            if added:
                print(f"  [DRY RUN] {args.key}: would add   {' '.join(added)}")
        return

    jira_put(f"/rest/api/3/issue/{args.key}", {"fields": {"labels": new_labels}}, auth)

    if args.json_output:
        result["message"] = "Labels updated"
        print(json.dumps(result, indent=2))
    else:
        if removed:
            print(f"  ✓ {args.key}: removed {' '.join(removed)}")
        if added:
            print(f"  ✓ {args.key}: added   {' '.join(added)}")
        if already:
            print(f"  (already had: {' '.join(already)})")


if __name__ == "__main__":
    main()
