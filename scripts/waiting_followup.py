#!/usr/bin/env python3
"""
waiting_followup.py — Report stale Jira waiting tickets by stakeholder.

Usage:
    python3 scripts/waiting_followup.py --report
    python3 scripts/waiting_followup.py --draft
    python3 scripts/waiting_followup.py --stale-days 5
    python3 scripts/waiting_followup.py --stakeholder "<USER_C> Bonney"

Environment (reads from .env if not already set):
    CONFLUENCE_EMAIL
    WWEEKS_CONFLUENCE_API_TOKEN
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, JIRA_COMMON_CAUSES

JIRA_BASE = "https://<YOUR_ATLASSIAN>.atlassian.net"
WAITING_JQL = 'project = INFRA AND labels = "flow:waiting" ORDER BY updated ASC'
ISSUES_ROOT = Path(__file__).parent.parent / "issues"

NAME_LINE_PATTERN = re.compile(
    r"^\s*-\s*\[\s\]\s*(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*(?:[:\-—–]|\s+—\s+|\s+-\s+)(?P<action>.+)$"
)
TRIGGER_PATTERNS = [
    re.compile(r"(?:waiting on|waiting for|pending|blocked by|awaiting)\s+(?P<target>[^.;,\n)]+)", re.IGNORECASE),
    re.compile(r"(?P<target>[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,3})\s+(?:confirmation|review|approval|sign-off|response|reply|test|testing|validation)\b", re.IGNORECASE),
]
GROUP_PATTERNS = [
    re.compile(r"\beach developer\b", re.IGNORECASE),
    re.compile(r"\bdevelopers\b", re.IGNORECASE),
    re.compile(r"\bAppDev team\b", re.IGNORECASE),
    re.compile(r"\bnetworking team\b", re.IGNORECASE),
    re.compile(r"\bMicrosoft support\b", re.IGNORECASE),
    re.compile(r"\bGlobal Admin\b", re.IGNORECASE),
    re.compile(r"\bvendor\b", re.IGNORECASE),
]


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
        "CONFLUENCE_EMAIL", "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="Add them to .env at the repo root",
        env_file=str(Path(__file__).parent.parent / ".env"),
    )
    email = os.environ["CONFLUENCE_EMAIL"]
    token = os.environ["WWEEKS_CONFLUENCE_API_TOKEN"]
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()



def print_table(headers: list[str], rows: list[list[str]]):
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))



def truncate(text: str, limit: int) -> str:
    text = str(text or "—")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"



def run_jql(jql: str, auth: str) -> list[dict]:
    issues = []
    next_page_token = None
    while True:
        payload = {
            "jql": jql,
            "fields": ["summary", "labels", "updated", "duedate"],
            "maxResults": 100,
        }
        if next_page_token:
            payload["nextPageToken"] = next_page_token
        req = urllib.request.Request(
            f"{JIRA_BASE}/rest/api/3/search/jql",
            data=json.dumps(payload).encode(),
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
        except urllib.error.HTTPError as error:
            http_fail(error, api_name="Jira", key="search/jql", operation="POST search/jql",
                      common_causes=JIRA_COMMON_CAUSES)
        batch = result.get("issues", [])
        issues.extend(batch)
        next_page_token = result.get("nextPageToken")
        if result.get("isLast") or not next_page_token or not batch:
            return issues



def parse_updated(updated: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(updated, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported updated format: {updated}")



def stale_days(updated: str) -> int:
    last_updated = parse_updated(updated)
    elapsed = datetime.now(timezone.utc) - last_updated.astimezone(timezone.utc)
    return max(0, int(elapsed.total_seconds() // 86400))



def find_issue_file(key: str) -> Path | None:
    direct_matches = []
    for path in sorted(ISSUES_ROOT.glob(f"{key}*/*.md")):
        if path.name.startswith(key) and "archive" not in path.parts:
            direct_matches.append(path)
    if direct_matches:
        return direct_matches[0]
    for path in sorted(ISSUES_ROOT.glob(f"**/{key}*.md")):
        if path.name.startswith(key) and "archive" not in path.parts:
            return path
    return None



def extract_section(content: str, heading: str) -> str:
    pattern = re.compile(rf"^{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)", re.MULTILINE)
    match = pattern.search(content)
    return match.group(1).strip() if match else ""



def clean_name(raw: str) -> str:
    text = raw.strip(" -—–:;,.()")
    for pattern in GROUP_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    name_match = re.match(r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,3})", text)
    if name_match:
        return name_match.group(1)
    return text.split()[0] if text else "Unknown"



def clean_action(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^TODO:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^Status:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^flow:waiting\s*[—-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:pending|waiting on|waiting for|blocked by|awaiting)\s+", "", text, flags=re.IGNORECASE)
    return text.strip(" -—–:;,.") or "Reply on the ticket"



def extract_named_todos(section: str) -> list[dict]:
    matches = []
    for line in section.splitlines():
        todo_match = NAME_LINE_PATTERN.match(line)
        if not todo_match:
            continue
        matches.append(
            {
                "stakeholder": clean_name(todo_match.group("name")),
                "action": clean_action(todo_match.group("action")),
                "source": line.strip(),
            }
        )
    return matches



def extract_general_action(section: str) -> str:
    for line in section.splitlines():
        if not re.match(r"^\s*-\s*\[\s\]\s+", line):
            continue
        text = re.sub(r"^\s*-\s*\[\s\]\s+", "", line).strip()
        todo_match = NAME_LINE_PATTERN.match(line)
        if todo_match:
            continue
        return clean_action(text)
    status_match = re.search(r"^Status:\s*(.+)$", section, re.MULTILINE | re.IGNORECASE)
    if status_match:
        return clean_action(status_match.group(1))
    return "Reply on the ticket"



def extract_from_text(text: str) -> tuple[str, str] | None:
    for line in text.splitlines():
        for pattern in TRIGGER_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            raw_target = match.group("target")
            stakeholder = clean_name(raw_target)
            remainder = raw_target[len(stakeholder):].strip(" -—–:;,.") if raw_target.startswith(stakeholder) else ""
            action = remainder or clean_action(line)
            return stakeholder, action
    return None



def parse_issue_context(key: str) -> dict:
    issue_file = find_issue_file(key)
    if not issue_file:
        return {"file": None, "stakeholders": [], "general_action": "Reply on the ticket"}

    content = issue_file.read_text(errors="replace")
    follow_up = extract_section(content, "## Follow-up")
    notes = extract_section(content, "## Notes")
    search_blocks = [block for block in (follow_up, notes) if block]

    named = []
    for block in search_blocks:
        named.extend(extract_named_todos(block))
    if named:
        return {"file": issue_file, "stakeholders": named, "general_action": extract_general_action(follow_up or notes)}

    for block in search_blocks:
        extracted = extract_from_text(block)
        if extracted:
            stakeholder, extracted_action = extracted
            general_action = extract_general_action(block)
            action = general_action
            if general_action in {"Reply on the ticket", "flow:waiting", "flow:active"}:
                action = extracted_action
            if "flow:active" in block.lower() and extracted_action:
                action = extracted_action
            return {
                "file": issue_file,
                "stakeholders": [{"stakeholder": stakeholder, "action": action, "source": block}],
                "general_action": action,
            }

    return {
        "file": issue_file,
        "stakeholders": [{"stakeholder": "Unknown", "action": extract_general_action(follow_up or notes), "source": "missing stakeholder"}],
        "general_action": extract_general_action(follow_up or notes),
    }



def label_value(labels: list[str], prefix: str) -> str:
    for label in labels:
        if label.startswith(f"{prefix}:"):
            return label.split(":", 1)[1]
    return "—"



def _get_approval_stakeholders(key: str) -> list[dict]:
    """Check JSM approvals and Approvers field for pending approver names."""
    auth = auth_header()
    stakeholders = []

    # JSM approval endpoint
    url = f"{JIRA_BASE}/rest/servicedeskapi/request/{key}/approval"
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        for approval in data.get("values", []):
            for entry in approval.get("approvers", []):
                if entry.get("approverDecision", "pending").lower() == "pending":
                    name = entry.get("approver", {}).get("displayName", "Unknown Approver")
                    stakeholders.append({"stakeholder": name, "action": f"Pending approval on {key}"})
    except Exception:
        pass

    if stakeholders:
        return stakeholders

    # Fallback: customfield_10003 (Approvers)
    url = f"{JIRA_BASE}/rest/api/3/issue/{key}?fields=customfield_10003"
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        approvers = data.get("fields", {}).get("customfield_10003") or []
        for a in approvers:
            if isinstance(a, dict):
                name = a.get("displayName", a.get("name", "Unknown"))
                stakeholders.append({"stakeholder": name, "action": f"Pending approval on {key}"})
    except Exception:
        pass

    return stakeholders



def build_entries(issues: list[dict]) -> tuple[list[dict], list[str]]:
    entries = []
    warnings = []
    for issue in issues:
        fields = issue.get("fields", {})
        context = parse_issue_context(issue["key"])
        issue_file = context.get("file")
        if not issue_file:
            warnings.append(f"⚠ Missing issue file for {issue['key']}")

        # Check for JSM approvers as additional stakeholders
        approval_stakeholders = _get_approval_stakeholders(issue["key"])

        stakeholders = context.get("stakeholders", []) or [{"stakeholder": "Unknown", "action": context.get("general_action", "Reply on the ticket")}]
        # Merge approval stakeholders if they aren't already named
        existing_names = {s.get("stakeholder", "").lower() for s in stakeholders}
        for approver in approval_stakeholders:
            if approver["stakeholder"].lower() not in existing_names:
                stakeholders.append(approver)

        for stakeholder_info in stakeholders:
            entries.append(
                {
                    "key": issue["key"],
                    "summary": fields.get("summary", ""),
                    "labels": fields.get("labels", []),
                    "updated": fields.get("updated", ""),
                    "due": fields.get("duedate") or "—",
                    "stale_days": stale_days(fields.get("updated", "")),
                    "stakeholder": stakeholder_info.get("stakeholder", "Unknown"),
                    "action": stakeholder_info.get("action") or context.get("general_action", "Reply on the ticket"),
                    "issue_file": str(issue_file.relative_to(Path(__file__).parent.parent)) if issue_file else "—",
                }
            )
    return entries, warnings



def score_string(labels: list[str]) -> str:
    urgency = label_value(labels, "urgency")
    importance = label_value(labels, "importance")
    agentic = label_value(labels, "agentic")
    return f"U{urgency}/I{importance}/A{agentic}".replace("U—", "U?").replace("I—", "I?").replace("A—", "A?")



def apply_filters(entries: list[dict], stakeholder_filter: str | None, min_stale_days: int) -> list[dict]:
    filtered = []
    needle = stakeholder_filter.lower() if stakeholder_filter else ""
    for entry in entries:
        if entry["stale_days"] <= min_stale_days:
            continue
        if needle and needle not in entry["stakeholder"].lower():
            continue
        filtered.append(entry)
    return filtered



def grouped_entries(entries: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for entry in sorted(entries, key=lambda item: (item["stakeholder"].lower(), -item["stale_days"], item["key"])):
        grouped[entry["stakeholder"]].append(entry)
    return dict(grouped)



def print_report(entries: list[dict], warnings: list[str]):
    if not entries:
        print("✓ No waiting tickets matched the filter.")
        return
    grouped = grouped_entries(entries)
    print(f"✓ {len(entries)} waiting ticket follow-up items across {len(grouped)} stakeholder groups")
    for warning in warnings:
        print(warning)
    print()
    for stakeholder, items in grouped.items():
        print(f"{stakeholder}")
        rows = []
        for item in items:
            rows.append(
                [
                    item["key"],
                    f"{item['stale_days']}d",
                    item["due"],
                    score_string(item["labels"]),
                    truncate(item["summary"], 52),
                ]
            )
        print_table(["KEY", "STALE", "DUE", "SCORES", "SUMMARY"], rows)
        for item in items:
            print(f"  → {item['key']}: {item['action']}")
        print()



def print_drafts(entries: list[dict], warnings: list[str]):
    if not entries:
        print("✓ No waiting tickets matched the filter.")
        return
    grouped = grouped_entries(entries)
    print(f"✓ Drafted follow-ups for {len(grouped)} stakeholder groups")
    for warning in warnings:
        print(warning)
    print()
    first = True
    for stakeholder, items in grouped.items():
        if not first:
            print("-" * 80)
            print()
        first = False
        print(f"Hey {stakeholder} —")
        print()
        print("Quick follow-up on a few tickets waiting on your side:")
        print()
        for item in items:
            print(f"• {item['key']} — {item['summary']} (waiting {item['stale_days']} days)")
            print(f"  → {item['action']}")
            print()
        print("Let me know if anything's blocked or if priorities shifted.")
        print()
        print("— <YOUR_NAME>")



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report Jira waiting tickets by stakeholder")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--report", action="store_true", help="Print grouped report (default)")
    mode.add_argument("--draft", action="store_true", help="Draft follow-up messages by stakeholder")
    parser.add_argument("--stale-days", type=int, default=-1, help="Only include tickets stale more than this many days")
    parser.add_argument("--stakeholder", help="Filter to a stakeholder name (case-insensitive substring match)")
    return parser.parse_args()



def main():
    load_env_file()
    args = parse_args()
    auth = auth_header()
    issues = run_jql(WAITING_JQL, auth)
    entries, warnings = build_entries(issues)
    filtered = apply_filters(entries, args.stakeholder, args.stale_days)
    if args.draft:
        print_drafts(filtered, warnings)
        return
    print_report(filtered, warnings)



if __name__ == "__main__":
    main()
