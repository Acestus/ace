#!/usr/bin/env python3
"""
gh_pr_daily.py — Daily pull request summary for standup.

Fetches yesterday's merged and opened PRs across all repos in the
<GITHUB_ORG> GitHub org and produces a standup-friendly summary.
Optionally publishes the summary to a rolling Notion page (prepended at top).

Usage:
    python3 scripts/gh_pr_daily.py --report
    python3 scripts/gh_pr_daily.py --report --date 2026-05-24
    python3 scripts/gh_pr_daily.py --publish --page-id PAGE_ID
    python3 scripts/gh_pr_daily.py --publish --page-id PAGE_ID --date 2026-05-24

Flags:
    --report             Print the summary to stdout (default if no action specified).
    --publish            Publish the summary to Notion (prepend to rolling page).
    --page-id ID         Notion page ID for --publish.
    --date YYYY-MM-DD    Override the target date (default: yesterday).
    --org ORG            GitHub org (default: <GITHUB_ORG>).

Environment:
    CONFLUENCE_EMAIL
    WWEEKS_CONFLUENCE_API_TOKEN
    CONFLUENCE_BASE_URL  (default: https://<YOUR_ATLASSIAN>.atlassian.net/wiki)
    GH_PR_DAILY_PAGE_ID  (default page ID for --publish, overridden by --page-id)
"""

import argparse
import base64
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, require_tool, http_fail, CONFLUENCE_COMMON_CAUSES


DEFAULT_ORG = "<GITHUB_ORG>"


def load_env_file():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def run_gh_command(args):
    command = ["gh"] + args
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"gh command failed: {detail}")
    return json.loads(result.stdout) if result.stdout.strip() else []


def fetch_all_prs(org, target_date):
    merged = run_gh_command([
        "search", "prs",
        "--owner", org,
        "--merged-at", target_date,
        "--json", "number,title,author,repository,url,createdAt,closedAt,state",
        "--limit", "200",
    ])

    opened = run_gh_command([
        "search", "prs",
        "--owner", org,
        "--created", target_date,
        "--state", "open",
        "--json", "number,title,author,repository,url,createdAt,closedAt,state",
        "--limit", "200",
    ])

    return merged, opened


def format_repo_name(full_name):
    return full_name.get("name", "") if isinstance(full_name, dict) else str(full_name).split("/")[-1]


def format_author(author):
    if isinstance(author, dict):
        return author.get("login", "unknown")
    return str(author) if author else "unknown"


def build_summary(merged_prs, opened_prs, target_date):
    lines = []
    date_str = target_date.strftime("%A, %B %d, %Y")
    lines.append(f"## PR Summary — {date_str}")
    lines.append("")

    if not merged_prs and not opened_prs:
        lines.append("*No pull requests merged or opened on this date.*")
        return "\n".join(lines)

    if merged_prs:
        lines.append(f"### ✅ Merged ({len(merged_prs)})")
        lines.append("")
        lines.append("| Repo | PR | Author | Title |")
        lines.append("|------|-----|--------|-------|")
        for pr in sorted(merged_prs, key=lambda p: p.get("closedAt", ""), reverse=True):
            repo = format_repo_name(pr.get("repository", {}))
            number = pr.get("number", "")
            author = format_author(pr.get("author"))
            title = pr.get("title", "—")
            url = pr.get("url", "")
            lines.append(f"| {repo} | [#{number}]({url}) | {author} | {title} |")
        lines.append("")

    if opened_prs:
        lines.append(f"### 🆕 Opened ({len(opened_prs)})")
        lines.append("")
        lines.append("| Repo | PR | Author | Title |")
        lines.append("|------|-----|--------|-------|")
        for pr in sorted(opened_prs, key=lambda p: p.get("createdAt", ""), reverse=True):
            repo = format_repo_name(pr.get("repository", {}))
            number = pr.get("number", "")
            author = format_author(pr.get("author"))
            title = pr.get("title", "—")
            url = pr.get("url", "")
            lines.append(f"| {repo} | [#{number}]({url}) | {author} | {title} |")
        lines.append("")

    total = len(merged_prs) + len(opened_prs)
    lines.append(f"**Total activity:** {len(merged_prs)} merged, {len(opened_prs)} opened across the org.")
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def print_report(merged_prs, opened_prs, target_date):
    summary = build_summary(merged_prs, opened_prs, target_date)
    print(summary)
    total = len(merged_prs) + len(opened_prs)
    print(f"✓ {total} PR(s) summarized for {target_date.isoformat()}")
    return 0


# --- Notion integration ---


def notion_base_url():
    return os.environ.get("CONFLUENCE_BASE_URL", "https://<YOUR_ATLASSIAN>.atlassian.net/wiki").rstrip("/")


def notion_auth_header():
    email = os.environ.get("CONFLUENCE_EMAIL", "").strip()
    token = os.environ.get("WWEEKS_CONFLUENCE_API_TOKEN", "").strip()
    if not email or not token:
        raise RuntimeError("Set CONFLUENCE_EMAIL and WWEEKS_CONFLUENCE_API_TOKEN in .env or environment")
    raw = f"{email}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("utf-8")


def notion_request(method, url, payload=None):
    headers = {"Authorization": notion_auth_header(), "Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:400]}")
    except URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}")


def fetch_notion_page(page_id):
    url = f"{notion_base_url()}/api/v2/pages/{page_id}?body-format=storage"
    page = notion_request("GET", url)
    version = page.get("version") or {}
    body = page.get("body") or {}
    storage = body.get("storage") or {}
    return {
        "id": str(page.get("id") or page_id),
        "title": page.get("title", ""),
        "version": int(version.get("number") or 1),
        "body": storage.get("value") or "",
    }


def markdown_to_paragraphs(text):
    """Convert markdown lines to simple Notion storage paragraphs."""
    lines = [line.rstrip() for line in text.splitlines()]
    paragraphs = []
    for line in lines:
        if not line.strip():
            continue
        escaped = escape_xml(line)
        paragraphs.append(f"<p>{escaped}</p>")
    return "\n".join(paragraphs) if paragraphs else "<p></p>"


def escape_xml(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def prepend_to_notion_page(page_id, markdown_content):
    page = fetch_notion_page(page_id)
    new_html = markdown_to_paragraphs(markdown_content)
    updated_body = new_html + "\n<hr />\n" + page["body"]

    payload = {
        "id": str(page_id),
        "status": "current",
        "title": page["title"],
        "version": {"number": page["version"] + 1},
        "body": {"storage": {"value": updated_body, "representation": "storage"}},
    }
    url = f"{notion_base_url()}/api/v2/pages/{page_id}"
    notion_request("PUT", url, payload)
    print(f"✓ Published to Notion page {page_id}")
    print(f"  https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/{page_id}")
    return 0


def publish_report(merged_prs, opened_prs, target_date, page_id):
    summary = build_summary(merged_prs, opened_prs, target_date)
    return prepend_to_notion_page(page_id, summary)


# --- CLI ---


def build_parser():
    parser = argparse.ArgumentParser(description="Daily PR summary for standup")
    parser.add_argument("--report", action="store_true", help="Print summary to stdout")
    parser.add_argument("--publish", action="store_true", help="Publish summary to Notion")
    parser.add_argument("--page-id", help="Notion page ID for --publish")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--org", default=DEFAULT_ORG, help="GitHub org (default: <GITHUB_ORG>)")
    return parser


def resolve_target_date(date_str):
    if date_str:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    return date.today() - timedelta(days=1)


def resolve_page_id(args):
    if args.page_id:
        return args.page_id
    env_page_id = os.environ.get("GH_PR_DAILY_PAGE_ID", "").strip()
    if env_page_id:
        return env_page_id
    raise RuntimeError("--page-id required or set GH_PR_DAILY_PAGE_ID in .env")


def main():
    load_env_file()
    parser = build_parser()
    args = parser.parse_args()

    if len(sys.argv) == 1:
        args.report = True

    try:
        target_date = resolve_target_date(args.date)
        print(f"📋 Fetching PRs for {target_date.isoformat()} from {args.org}...")

        merged_prs, opened_prs = fetch_all_prs(args.org, target_date.isoformat())
        print(f"  Found {len(merged_prs)} merged, {len(opened_prs)} opened")

        if args.publish:
            page_id = resolve_page_id(args)
            return publish_report(merged_prs, opened_prs, target_date, page_id)

        return print_report(merged_prs, opened_prs, target_date)

    except Exception as exc:
        fail(str(exc),
             causes=["gh command not found or returned non-zero",
                     "GitHub token not set or expired",
                     "Notion credentials missing or request failed"],
             try_=["gh auth status", "gh auth login",
                   "export $(grep -v '^#' .env | xargs)"])


if __name__ == "__main__":
    sys.exit(main())
