#!/usr/bin/env python3
"""
weekly_summary.py — Generate a weekly status report or brag doc.

Usage:
    python3 scripts/weekly_summary.py --report
    python3 scripts/weekly_summary.py --markdown
    python3 scripts/weekly_summary.py --week 2026-05-19
    python3 scripts/weekly_summary.py --markdown --output weekly-status.md

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
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, warn, require_env, http_fail, JIRA_COMMON_CAUSES

JIRA_BASE = "https://<YOUR_ATLASSIAN>.atlassian.net"
PROJECTS = Path(__file__).parent.parent
PLANNER = PROJECTS / "planner"
ISSUES = PROJECTS / "issues"

LANE_LABELS = {
    "urgent": "🔴 Urgent",
    "manual": "🔵 Manual",
    "background": "🟢 Background",
}
LANE_ORDER = ["urgent", "manual", "background"]


def load_env_file():
    env_path = PROJECTS / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def auth_header():
    require_env(
        "CONFLUENCE_EMAIL", "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="Add them to .env at the repo root",
        env_file=str(PROJECTS / ".env"),
    )
    email = os.environ["CONFLUENCE_EMAIL"]
    token = os.environ["WWEEKS_CONFLUENCE_API_TOKEN"]
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()


def print_table(headers: list[str], rows: list[list[str]]):
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    header_line = " | ".join(headers[index].ljust(widths[index]) for index in range(len(headers)))
    divider = "-+-".join("-" * widths[index] for index in range(len(headers)))
    print(header_line)
    print(divider)
    for row in rows:
        print(" | ".join(row[index].ljust(widths[index]) for index in range(len(headers))))


def success(message: str):
    print(f"✓ {message}")


def jira_search(jql: str, fields: list[str], auth: str, max_results: int = 100) -> list[dict]:
    payload = json.dumps({"jql": jql, "fields": fields, "maxResults": max_results}).encode()
    request = urllib.request.Request(
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
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read()).get("issues", [])
    except urllib.error.HTTPError as exc:
        http_fail(exc, api_name="Jira", key="search/jql", operation="POST search/jql",
                  common_causes=JIRA_COMMON_CAUSES)
    except urllib.error.URLError as exc:
        fail(f"Jira search failed: {exc}",
             causes=["Network is unreachable or Jira is down"],
             try_=["curl -s https://<YOUR_ATLASSIAN>.atlassian.net/rest/api/3/serverInfo"])
    return []


def jira_changelog(key: str, auth: str, max_results: int = 100) -> list[dict]:
    request = urllib.request.Request(
        f"{JIRA_BASE}/rest/api/3/issue/{key}/changelog?maxResults={max_results}",
        headers={"Authorization": auth, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read()).get("values", [])
    except urllib.error.HTTPError as exc:
        http_fail(exc, api_name="Jira", key=f"{key}/changelog", operation=f"GET {key}/changelog",
                  common_causes=JIRA_COMMON_CAUSES)
    except urllib.error.URLError as exc:
        fail(f"Jira changelog failed for {key}: {exc}",
             causes=["Network is unreachable or Jira is down"],
             try_=["curl -s https://<YOUR_ATLASSIAN>.atlassian.net/rest/api/3/serverInfo"])
    return []


def parse_date_arg(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError("--week must be YYYY-MM-DD")


def monday_for(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_window(selected_day: date | None) -> tuple[date, date, date]:
    anchor = selected_day or date.today()
    start = monday_for(anchor)
    friday = start + timedelta(days=4)
    today = date.today()
    end = friday
    if start == monday_for(today):
        end = min(today, friday)
    return start, end, start + timedelta(days=7)


def week_dates(start: date, end: date) -> list[date]:
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def format_date_range(start: date, end: date) -> str:
    if start.year == end.year and start.month == end.month:
        return f"{start.strftime('%B')} {start.day}–{end.day}, {start.year}"
    if start.year == end.year:
        return f"{start.strftime('%B')} {start.day}–{end.strftime('%B')} {end.day}, {start.year}"
    return f"{start.strftime('%B')} {start.day}, {start.year}–{end.strftime('%B')} {end.day}, {end.year}"


def format_hours(value: float) -> str:
    text = f"{value:.2f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    if "." not in text:
        text += ".0"
    return f"{text}h"


def format_percent(value: float, total: float) -> str:
    if total <= 0:
        return ""
    return f"{round((value / total) * 100):.0f}%"


def label_score(labels: list[str], prefix: str) -> int:
    for label in labels:
        if label.startswith(f"{prefix}:"):
            try:
                return int(label.split(":", 1)[1])
            except ValueError:
                return 99
    return 99


def classify_lane(labels: list[str]) -> str:
    urgency = label_score(labels, "urgency")
    importance = label_score(labels, "importance")
    agentic = label_score(labels, "agentic")
    if urgency <= 2:
        return "urgent"
    if agentic >= 4 and importance <= 3:
        return "manual"
    if agentic <= 2:
        return "background"
    return "manual"


def compact_summary(summary: str) -> str:
    return re.sub(r"\s+", " ", summary or "").strip()


def parse_worklog_hours(text: str) -> float:
    cleaned = text.strip().lower().lstrip("~")
    if not cleaned:
        return 0.0
    total = 0.0
    for value, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([hm])", cleaned):
        amount = float(value)
        total += amount if unit == "h" else amount / 60.0
    if total > 0:
        return total
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_time_log_table(path: Path) -> dict[str, dict[str, str | float]]:
    rows: dict[str, dict[str, str | float]] = {}
    in_time_log = False
    table_started = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line.startswith("* Time Log"):
            in_time_log = True
            continue
        if in_time_log and line.startswith("*") and not line.startswith("* Time Log"):
            break
        if not in_time_log:
            continue
        if not line.startswith("|"):
            if table_started and line.strip():
                break
            continue
        table_started = True
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 6:
            continue
        if len(parts) > 6:
            parts = [parts[0], parts[1], parts[2], "|".join(parts[3:-2]).strip(), parts[-2], parts[-1]]
        if parts[0].lower() == "start" or set(parts[0]) == {"-"}:
            continue
        key = parts[2].strip()
        if not key:
            continue
        hours = parse_worklog_hours(parts[5])
        summary = compact_summary(parts[3])
        item = rows.setdefault(key, {"hours": 0.0, "summary": summary})
        item["hours"] = float(item["hours"]) + hours
        if summary and not item.get("summary"):
            item["summary"] = summary
    return rows


def collect_planner_hours(start: date, end: date) -> tuple[dict[str, dict[str, str | float]], list[Path], list[str]]:
    combined: dict[str, dict[str, str | float]] = {}
    found_files: list[Path] = []
    missing_files: list[str] = []
    for day in week_dates(start, end):
        path = PLANNER / f"{day:%m-%d}.org"
        if not path.exists():
            missing_files.append(path.name)
            continue
        found_files.append(path)
        for key, data in parse_time_log_table(path).items():
            item = combined.setdefault(key, {"hours": 0.0, "summary": data.get("summary", "")})
            item["hours"] = float(item["hours"]) + float(data.get("hours", 0.0))
            if not item.get("summary") and data.get("summary"):
                item["summary"] = data["summary"]
    return combined, found_files, missing_files


def find_issue_markdown(key: str) -> Path | None:
    if not ISSUES.exists():
        return None
    for entry in ISSUES.iterdir():
        if entry.name == "archive" or not entry.is_dir():
            continue
        if not entry.name.startswith(key):
            continue
        markdown_files = sorted(entry.glob("*.md"))
        if markdown_files:
            return markdown_files[0]
    return None


def clean_waiting_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"^(pending|waiting on|waiting for)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip("-—:;,.()[]{} ")
    return cleaned or "—"


def extract_waiting_on(key: str) -> str:
    issue_path = find_issue_markdown(key)
    if not issue_path:
        return "—"
    text = issue_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for line in lines:
        match = re.search(r"Status:.*flow:waiting\s*[—-]\s*(.+)$", line, flags=re.IGNORECASE)
        if match:
            return clean_waiting_text(match.group(1))
        match = re.search(r"\*\*Status:\*\*.*?\(pending\s+(.+?)\)", line, flags=re.IGNORECASE)
        if match:
            return clean_waiting_text(match.group(1))
    for line in reversed(lines):
        if line.lstrip().startswith("|"):
            continue
        match = re.search(r"\bwaiting on\b\s+(.+?)(?:[.;)]|$)", line, flags=re.IGNORECASE)
        if match:
            return clean_waiting_text(match.group(1))
        match = re.search(r"\bpending\b\s+(.+?)(?:[.;)]|$)", line, flags=re.IGNORECASE)
        if match:
            return clean_waiting_text(match.group(1))
        match = re.search(r"\bwaiting for\b\s+(.+?)(?:[.;)]|$)", line, flags=re.IGNORECASE)
        if match:
            return clean_waiting_text(match.group(1))
    return "—"


def build_issue_map(issues: list[dict], hours_by_key: dict[str, dict[str, str | float]]) -> dict[str, dict]:
    issue_map: dict[str, dict] = {}
    for issue in issues:
        fields = issue.get("fields", {})
        key = issue["key"]
        summary = compact_summary(fields.get("summary") or str(hours_by_key.get(key, {}).get("summary", "")))
        labels = fields.get("labels", []) or []
        issue_map[key] = {
            "key": key,
            "summary": summary,
            "labels": labels,
            "lane": classify_lane(labels),
            "hours": float(hours_by_key.get(key, {}).get("hours", 0.0)),
            "resolved": fields.get("resolutiondate", ""),
            "updated": fields.get("updated", ""),
        }
    for key, data in hours_by_key.items():
        if key in issue_map:
            continue
        summary = compact_summary(str(data.get("summary", "")))
        issue_map[key] = {
            "key": key,
            "summary": summary,
            "labels": [],
            "lane": "manual",
            "hours": float(data.get("hours", 0.0)),
            "resolved": "",
            "updated": "",
        }
    return issue_map


def fetch_issue_details(keys: set[str], auth: str, hours_by_key: dict[str, dict[str, str | float]]) -> dict[str, dict]:
    if not keys:
        return {}
    collected: list[dict] = []
    key_list = sorted(keys)
    for index in range(0, len(key_list), 50):
        chunk = key_list[index:index + 50]
        quoted = ", ".join(chunk)
        jql = f"key in ({quoted}) ORDER BY key ASC"
        collected.extend(jira_search(jql, ["summary", "labels", "resolutiondate", "updated"], auth, max_results=100))
    return build_issue_map(collected, hours_by_key)


def build_done_jql(start: date, next_week: date) -> str:
    return (
        'project = INFRA AND labels = "flow:done" '
        f'AND status changed to Done AFTER "{start:%Y-%m-%d}" '
        f'AND status changed to Done BEFORE "{next_week:%Y-%m-%d}" '
        'ORDER BY resolved ASC'
    )


def build_waiting_jql(start: date, next_week: date) -> str:
    return (
        'project = INFRA AND labels = "flow:waiting" '
        f'AND updated >= "{start:%Y-%m-%d}" '
        f'AND updated < "{next_week:%Y-%m-%d}" '
        'ORDER BY updated ASC'
    )


def parse_jira_timestamp(value: str) -> date:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def changed_this_week(key: str, auth: str, start: date, next_week: date) -> bool:
    for history in jira_changelog(key, auth):
        changed_on = parse_jira_timestamp(history.get("created", ""))
        if not (start <= changed_on < next_week):
            continue
        for item in history.get("items", []):
            field_name = (item.get("field") or "").lower()
            to_value = (item.get("toString") or item.get("to") or "").strip()
            if field_name == "labels" and "flow:waiting" in to_value:
                return True
            if field_name == "status" and to_value == "Code Review":
                return True
    return False


def collect_waiting_issues(start: date, next_week: date, auth: str) -> list[dict]:
    candidates = jira_search(build_waiting_jql(start, next_week), ["summary", "labels", "updated"], auth)
    waiting_issues = []
    for issue in candidates:
        if changed_this_week(issue["key"], auth, start, next_week):
            waiting_issues.append(issue)
    return waiting_issues


def markdown_cell(text: str) -> str:
    return (text or "—").replace("|", "\\|")


def highlight_line(issue: dict) -> str:
    return f"- {issue['key']} — Closed {issue['summary']}. Logged {format_hours(issue['hours'])} in {LANE_LABELS[issue['lane']]} work."


def build_markdown_report(start: date, end: date, done_items: list[dict], waiting_items: list[dict], lane_totals: dict[str, float], total_hours: float) -> str:
    lines = [f"# Weekly Status — {format_date_range(start, end)}", ""]
    lines += ["## Completed (flow:done)", "", "| Key | Summary | Lane | Hours |", "|-----|---------|------|-------|"]
    if done_items:
        for item in done_items:
            lines.append(f"| {item['key']} | {markdown_cell(item['summary'])} | {LANE_LABELS[item['lane']]} | {format_hours(item['hours'])} |")
    else:
        lines.append("| — | No completed tickets found | — | 0.0h |")

    lines += ["", "## Shipped to Review (flow:waiting)", "", "| Key | Summary | Waiting On |", "|-----|---------|------------|"]
    if waiting_items:
        for item in waiting_items:
            lines.append(f"| {item['key']} | {markdown_cell(item['summary'])} | {markdown_cell(item['waiting_on'])} |")
    else:
        lines.append("| — | No waiting tickets found | — |")

    lines += ["", "## Time by Swimlane", "", "| Lane | Hours | % |", "|------|-------|---|"]
    for lane in LANE_ORDER:
        lines.append(f"| {LANE_LABELS[lane]} | {format_hours(lane_totals[lane])} | {format_percent(lane_totals[lane], total_hours)} |")
    lines.append(f"| **Total** | **{format_hours(total_hours)}** | |")

    lines += ["", "## Highlights", ""]
    if done_items:
        lines.extend(highlight_line(item) for item in done_items)
    else:
        lines.append("- No completed tickets this week.")
    return "\n".join(lines) + "\n"


def print_report(start: date, end: date, done_items: list[dict], waiting_items: list[dict], lane_totals: dict[str, float], total_hours: float, planner_files: list[Path], missing_files: list[str]):
    print(f"Weekly Status — {format_date_range(start, end)}")
    print()
    success(f"Loaded {len(planner_files)} planner file(s)")
    if missing_files:
        warn(f"Missing planner files: {', '.join(missing_files)}")
    success(f"Found {len(done_items)} completed ticket(s)")
    success(f"Found {len(waiting_items)} waiting ticket(s)")
    print()

    print("Completed (flow:done)")
    done_rows = [
        [item["key"], item["summary"], LANE_LABELS[item["lane"]], format_hours(item["hours"]), (item.get("resolved") or "")[:10] or "—"]
        for item in done_items
    ]
    if not done_rows:
        done_rows = [["—", "No completed tickets found", "—", "0.0h", "—"]]
    print_table(["KEY", "SUMMARY", "LANE", "HOURS", "RESOLVED"], done_rows)
    print()

    print("Shipped to Review (flow:waiting)")
    waiting_rows = [[item["key"], item["summary"], item["waiting_on"]] for item in waiting_items]
    if not waiting_rows:
        waiting_rows = [["—", "No waiting tickets found", "—"]]
    print_table(["KEY", "SUMMARY", "WAITING ON"], waiting_rows)
    print()

    print("Time by Swimlane")
    lane_rows = [
        [LANE_LABELS[lane], format_hours(lane_totals[lane]), format_percent(lane_totals[lane], total_hours)]
        for lane in LANE_ORDER
    ]
    lane_rows.append(["Total", format_hours(total_hours), ""])
    print_table(["LANE", "HOURS", "%"], lane_rows)


def write_output(path_text: str, content: str):
    output_path = Path(path_text)
    output_path.write_text(content, encoding="utf-8")
    success(f"Wrote {output_path}")


def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Generate a weekly status report or brag doc")
    parser.add_argument("--week", type=parse_date_arg, help="Any date in the target week (YYYY-MM-DD)")
    parser.add_argument("--report", action="store_true", help="Print the weekly report (default)")
    parser.add_argument("--markdown", action="store_true", help="Generate markdown output")
    parser.add_argument("--output", help="Write output to a file")
    args = parser.parse_args()

    if args.report and args.markdown:
        fail("Choose one mode: --report or --markdown")

    mode = "markdown" if args.markdown else "report"
    week_start, week_end, next_week = week_window(args.week)
    auth = auth_header()

    done_issues = jira_search(build_done_jql(week_start, next_week), ["summary", "labels", "resolutiondate"], auth)
    waiting_issues = collect_waiting_issues(week_start, next_week, auth)
    hours_by_key, planner_files, missing_files = collect_planner_hours(week_start, week_end)

    all_keys = {issue["key"] for issue in done_issues + waiting_issues} | set(hours_by_key.keys())
    issue_map = fetch_issue_details(all_keys, auth, hours_by_key)

    done_items = [issue_map.get(issue["key"], {"key": issue["key"], "summary": compact_summary(issue.get("fields", {}).get("summary", "")), "lane": "manual", "hours": 0.0, "resolved": issue.get("fields", {}).get("resolutiondate", "")}) for issue in done_issues]
    waiting_items = []
    for issue in waiting_issues:
        item = issue_map.get(issue["key"], {"key": issue["key"], "summary": compact_summary(issue.get("fields", {}).get("summary", "")), "lane": "manual", "hours": 0.0, "updated": issue.get("fields", {}).get("updated", "")})
        waiting_items.append({**item, "waiting_on": extract_waiting_on(issue["key"])})

    lane_totals = {lane: 0.0 for lane in LANE_ORDER}
    total_hours = 0.0
    for item in issue_map.values():
        hours = float(item.get("hours", 0.0))
        lane = item.get("lane", "manual")
        lane_totals[lane] = lane_totals.get(lane, 0.0) + hours
        total_hours += hours

    if mode == "markdown":
        content = build_markdown_report(week_start, week_end, done_items, waiting_items, lane_totals, total_hours)
        if args.output:
            write_output(args.output, content)
        else:
            print(content, end="")
        return

    if args.output:
        from io import StringIO
        from contextlib import redirect_stdout

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_report(week_start, week_end, done_items, waiting_items, lane_totals, total_hours, planner_files, missing_files)
        content = buffer.getvalue()
        print(content, end="")
        write_output(args.output, content)
        return

    print_report(week_start, week_end, done_items, waiting_items, lane_totals, total_hours, planner_files, missing_files)


if __name__ == "__main__":
    main()
