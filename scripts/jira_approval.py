#!/usr/bin/env python3
"""
jira_approval.py — Check JSM approval status for Jira tickets.

Usage:
    python3 scripts/jira_approval.py --key <PROJECT>-358
    python3 scripts/jira_approval.py --key <PROJECT>-358 --json
    python3 scripts/jira_approval.py --keys <PROJECT>-358,<PROJECT>-357,<PROJECT>-390

Returns approval status per ticket. Exit code 0 = all approved or no approvals.
Exit code 1 = at least one ticket has pending approvals.

Environment (reads from .env if not already set):
    CONFLUENCE_EMAIL
    WWEEKS_CONFLUENCE_API_TOKEN
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
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


def get_approvals(key: str, auth: str) -> list[dict]:
    """Fetch approvals from JSM Service Desk API."""
    url = f"{JIRA_BASE}/rest/servicedeskapi/request/{key}/approval"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": auth,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        return data.get("values", [])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        print(f"⚠   {key}: approval check failed (HTTP {e.code})", file=sys.stderr)
        return []


def get_approvers_field(key: str, auth: str) -> list[str]:
    """Fetch customfield_10003 (Approvers) as a fallback."""
    url = f"{JIRA_BASE}/rest/api/3/issue/{key}?fields=customfield_10003"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": auth,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        approvers = data.get("fields", {}).get("customfield_10003") or []
        return [a.get("displayName", a.get("name", "?")) for a in approvers if isinstance(a, dict)]
    except Exception:
        return []


def check_ticket(key: str, auth: str) -> dict:
    """Return approval status for a single ticket."""
    result = {
        "key": key,
        "has_approvals": False,
        "status": "none",
        "approvers": [],
        "pending": [],
        "approved": [],
        "declined": [],
    }

    # Try JSM approval API first
    approvals = get_approvals(key, auth)
    if approvals:
        result["has_approvals"] = True
        for approval in approvals:
            status = approval.get("status", "pending").lower()
            if status == "pending":
                result["status"] = "pending"
            for approver_entry in approval.get("approvers", []):
                name = approver_entry.get("approver", {}).get("displayName", "?")
                decision = approver_entry.get("approverDecision", "pending").lower()
                entry = {"name": name, "decision": decision}
                result["approvers"].append(entry)
                if decision == "pending":
                    result["pending"].append(name)
                elif decision == "approved":
                    result["approved"].append(name)
                elif decision == "declined":
                    result["declined"].append(name)
        if not result["pending"] and not result["declined"]:
            result["status"] = "approved"
        elif result["declined"]:
            result["status"] = "declined"
        return result

    # Fallback: check the Approvers custom field
    approver_names = get_approvers_field(key, auth)
    if approver_names:
        result["has_approvals"] = True
        result["status"] = "pending"
        result["pending"] = approver_names
        result["approvers"] = [{"name": n, "decision": "pending"} for n in approver_names]

    return result


def display_result(result: dict):
    key = result["key"]
    if not result["has_approvals"]:
        print(f"  {key}: No approvals configured")
        return

    status_emoji = {"approved": "✅", "pending": "🔏", "declined": "❌", "none": "—"}
    emoji = status_emoji.get(result["status"], "?")
    print(f"  {key}: {emoji} {result['status'].upper()}")

    if result["pending"]:
        print(f"    Pending: {', '.join(result['pending'])}")
    if result["approved"]:
        print(f"    Approved: {', '.join(result['approved'])}")
    if result["declined"]:
        print(f"    Declined: {', '.join(result['declined'])}")


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Check Jira ticket approval status")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--key", help="Single Jira key (e.g. <PROJECT>-358)")
    group.add_argument("--keys", help="Comma-separated Jira keys (e.g. <PROJECT>-358,<PROJECT>-357)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    keys = [args.key] if args.key else [k.strip() for k in args.keys.split(",")]
    auth = auth_header()

    results = [check_ticket(key, auth) for key in keys]
    has_pending = any(r["status"] == "pending" for r in results)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"\n🔏  Approval status — {len(keys)} ticket(s):")
        for r in results:
            display_result(r)
        print()

    sys.exit(1 if has_pending else 0)


if __name__ == "__main__":
    main()
