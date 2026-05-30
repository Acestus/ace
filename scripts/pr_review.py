#!/usr/bin/env python3
"""
pr_review.py — Automated GitHub pull request review helper.

Usage:
    python3 scripts/pr_review.py --pr NUMBER [--repo OWNER/REPO]
    python3 scripts/pr_review.py --pr NUMBER --checklist
    python3 scripts/pr_review.py --pr NUMBER --to-issue <PROJECT>-KEY
    python3 scripts/pr_review.py --my-prs
    python3 scripts/pr_review.py --stale

Environment:
    GH_REPO  — default repo (e.g. <GITHUB_ORG>/projects); overridden by --repo
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_tool


ORG_NAME = "<GITHUB_ORG>"
SEPARATOR = "─" * 65
PASS_STATES = {"SUCCESS", "SUCCESSFUL", "NEUTRAL", "SKIPPED", "PASS", "PASSED"}
FAIL_STATES = {"FAILURE", "FAILED", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
PENDING_STATES = {"EXPECTED", "PENDING", "IN_PROGRESS", "QUEUED", "REQUESTED", "WAITING"}
JIRA_KEY_RE = re.compile(r"\bINFRA-\d+\b", re.IGNORECASE)
SECRET_PATTERNS = [
    ("connection string", re.compile(r"(?i)(defaultendpointsprotocol=.+;accountkey=|connection\s*string\s*[:=]\s*['\"]?[A-Za-z0-9;/+=._-]{12,})")),
    ("password", re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^'\"\s]{8,}")),
    ("token", re.compile(r"(?i)(token|bearer)\s*[:=]\s*['\"]?[A-Za-z0-9._-]{16,}")),
    ("api key", re.compile(r"(?i)(api[_-]?key|client[_-]?secret|secret)\s*[:=]\s*['\"]?[A-Za-z0-9/+=._-]{12,}")),
    ("private key", re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA|PRIVATE) KEY-----")),
]


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


def run_command(command, capture_output=True):
    try:
        return subprocess.run(command, capture_output=capture_output, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {command[0]}")


def run_json_command(command, allow_nonzero=False):
    result = run_command(command)
    if result.returncode != 0 and not (allow_nonzero and (result.stdout or "").strip()):
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail or "Command failed")
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse JSON output: {exc}")


def parse_repo_from_remote(remote_url):
    patterns = [r"github\.com[:/](?P<repo>[^/]+/[^/.]+)(?:\.git)?$", r"^(?P<repo>[^/]+/[^/]+)$"]
    for pattern in patterns:
        match = re.search(pattern, remote_url.strip())
        if match:
            return match.group("repo")
    return ""


def resolve_repo(cli_repo):
    if cli_repo:
        return cli_repo
    env_repo = os.environ.get("GH_REPO", "").strip()
    if env_repo:
        return env_repo
    result = run_command(["git", "remote", "get-url", "origin"])
    if result.returncode != 0:
        raise RuntimeError("Unable to determine repo. Set GH_REPO or pass --repo.")
    repo = parse_repo_from_remote(result.stdout)
    if repo:
        return repo
    raise RuntimeError("Unable to parse owner/repo from git remote.")


def iso_to_datetime(value):
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(cleaned)


def extract_login(value):
    if isinstance(value, dict):
        return value.get("login") or value.get("name") or "—"
    return str(value or "—")


def extract_repo_name(value):
    if isinstance(value, dict):
        return value.get("nameWithOwner") or value.get("fullName") or value.get("name") or "—"
    return str(value or "—")


def format_age(value):
    dt_value = iso_to_datetime(value)
    if not dt_value:
        return "—"
    delta = datetime.now(timezone.utc) - dt_value.astimezone(timezone.utc)
    days = max(delta.days, 0)
    if days == 0:
        return "today"
    if days == 1:
        return "1d"
    return f"{days}d"


def normalize_check_state(value):
    state = str(value or "PENDING").upper()
    if state == "SUCCESS":
        return "SUCCESS"
    if state in PASS_STATES:
        return "SUCCESS"
    if state in FAIL_STATES:
        return "FAILURE"
    return "PENDING"


def summarize_checks(checks):
    summary = {"passed": 0, "failed": 0, "pending": 0}
    for item in checks or []:
        state = normalize_check_state(item.get("state") or item.get("conclusion") or item.get("status"))
        if state == "SUCCESS":
            summary["passed"] += 1
        elif state == "FAILURE":
            summary["failed"] += 1
        else:
            summary["pending"] += 1
    return summary


def format_ci_header(summary):
    parts = []
    if summary["passed"]:
        parts.append(f"✓ {summary['passed']} passed")
    if summary["failed"]:
        parts.append(f"❌ {summary['failed']} failed")
    if summary["pending"]:
        parts.append(f"⚠ {summary['pending']} pending")
    return "  ".join(parts) or "—"


def print_table(headers, rows):
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def get_pr_details(repo, number):
    return run_json_command([
        "gh", "pr", "view", str(number), "--repo", repo,
        "--json", "number,title,body,state,author,headRefName,files,additions,deletions,url,createdAt",
    ])


def get_pr_checks(repo, number):
    return run_json_command([
        "gh", "pr", "checks", str(number), "--repo", repo,
        "--json", "name,state,workflow,link",
    ], allow_nonzero=True)


def get_pr_diff(repo, number):
    result = run_command(["gh", "pr", "diff", str(number), "--repo", repo])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail or "Failed to pull PR diff")
    return result.stdout


def path_from_file_item(item):
    return item.get("path") or item.get("name") or item.get("filename") or ""


def parse_diff_files(diff_text):
    files = []
    current = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if current:
                files.append(current)
            match = re.match(r"^diff --git a/(.+) b/(.+)$", line)
            old_path = match.group(1) if match else ""
            new_path = match.group(2) if match else old_path
            current = {"path": new_path, "status": "M", "additions": 0, "deletions": 0, "old_path": old_path}
            continue
        if not current:
            continue
        if line.startswith("new file mode"):
            current["status"] = "+"
        elif line.startswith("deleted file mode"):
            current["status"] = "D"
            current["path"] = current.get("old_path") or current.get("path")
        elif line.startswith("rename from "):
            current["status"] = "R"
            current["old_path"] = line.removeprefix("rename from ")
        elif line.startswith("rename to "):
            current["path"] = line.removeprefix("rename to ")
        elif line.startswith("+") and not line.startswith("+++"):
            current["additions"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            current["deletions"] += 1
    if current:
        files.append(current)
    return files


def merge_changed_files(pr_files, diff_files):
    merged = []
    seen = set()
    diff_map = {item["path"]: item for item in diff_files}
    for item in diff_files:
        merged.append(item)
        seen.add(item["path"])
    for item in pr_files or []:
        path = path_from_file_item(item)
        if not path or path in seen:
            if path in diff_map:
                diff_map[path]["additions"] = diff_map[path].get("additions") or int(item.get("additions") or 0)
                diff_map[path]["deletions"] = diff_map[path].get("deletions") or int(item.get("deletions") or 0)
            continue
        merged.append({
            "path": path,
            "status": "M",
            "additions": int(item.get("additions") or 0),
            "deletions": int(item.get("deletions") or 0),
        })
        seen.add(path)
    return merged


def scan_secret_lines(diff_text):
    hits = []
    seen = set()
    current_path = ""
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            match = re.match(r"^diff --git a/(.+) b/(.+)$", line)
            current_path = match.group(2) if match else ""
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        content = line[1:]
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(content):
                key = (current_path or "diff", label)
                if key not in seen:
                    seen.add(key)
                    hits.append({"path": current_path or "diff", "label": label})
    return hits


def is_sensitive_path(path):
    lower = path.lower()
    return lower == ".env" or "/.env" in lower or lower.startswith("scripts/") or lower.startswith(".github/workflows/")


def is_docs_reference(path):
    lower = path.lower()
    return lower == "readme.md" or lower.endswith("/readme.md") or lower.startswith("docs/")


def is_code_path(path):
    lower = path.lower()
    doc_suffixes = (".md", ".rst", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".svg")
    return not is_docs_reference(path) and not lower.endswith(doc_suffixes)


def build_recommendation(review):
    notes = []
    if review["checks"]["failed"]:
        return "Not ready. Fix failing CI first."
    if review["secret_hits"]:
        return "Not ready. Possible secrets detected in the diff."
    if review["checks"]["pending"]:
        notes.append("Wait for CI to finish.")
    if review["workflow_changed"]:
        notes.append("Workflow files changed — review permissions and OIDC closely.")
    if review["is_large"]:
        notes.append("Large PR — review in chunks.")
    if review["needs_docs"]:
        notes.append("Update README or docs.")
    if not review["has_jira_key"]:
        notes.append("Add Jira key to PR description.")
    if not notes:
        return "Ready for review."
    if review["checks"]["pending"]:
        return "Not ready to merge. " + " ".join(notes)
    return "Ready for review. " + " ".join(notes)


def build_review(repo, number):
    pr = get_pr_details(repo, number)
    checks = get_pr_checks(repo, number)
    diff_text = get_pr_diff(repo, number)
    diff_files = parse_diff_files(diff_text)
    files = merge_changed_files(pr.get("files") or [], diff_files)
    additions = int(pr.get("additions") or sum(item.get("additions", 0) for item in files))
    deletions = int(pr.get("deletions") or sum(item.get("deletions", 0) for item in files))
    changed_paths = [item["path"] for item in files]
    sensitive_paths = [path for path in changed_paths if is_sensitive_path(path)]
    workflow_changed = any(path.startswith(".github/workflows/") for path in changed_paths)
    has_jira_key = bool(JIRA_KEY_RE.search(pr.get("body") or ""))
    code_changed = any(is_code_path(path) for path in changed_paths)
    docs_updated = any(is_docs_reference(path) for path in changed_paths)
    secret_hits = scan_secret_lines(diff_text)
    review = {
        "repo": repo,
        "number": pr.get("number", number),
        "title": pr.get("title", "—"),
        "author": extract_login(pr.get("author")),
        "branch": pr.get("headRefName") or "—",
        "state": str(pr.get("state") or "—").lower(),
        "url": pr.get("url") or "",
        "created_at": pr.get("createdAt") or "",
        "checks": summarize_checks(checks),
        "files": files,
        "additions": additions,
        "deletions": deletions,
        "total_lines": additions + deletions,
        "sensitive_paths": sensitive_paths,
        "workflow_changed": workflow_changed,
        "has_jira_key": has_jira_key,
        "code_changed": code_changed,
        "docs_updated": docs_updated,
        "needs_docs": code_changed and not docs_updated,
        "secret_hits": secret_hits,
        "is_large": additions + deletions > 500,
    }
    review["recommendation"] = build_recommendation(review)
    return review


def checklist_entries(review):
    checks = review["checks"]
    if checks["failed"]:
        ci_icon = "❌"
        ci_text = f"CI checks failing ({checks['failed']} failed)"
    elif checks["pending"]:
        ci_icon = "⚠"
        ci_text = f"CI checks mostly green ({checks['passed']} passed, {checks['pending']} pending)"
    else:
        ci_icon = "✓"
        ci_text = f"CI checks passing ({checks['passed']} green)"

    if review["secret_hits"]:
        secret_icon = "❌"
        labels = ", ".join(sorted({hit['label'] for hit in review['secret_hits']}))
        secret_text = f"Possible secrets in diff ({labels})"
    else:
        secret_icon = "✓"
        secret_text = "No secrets detected in diff"

    if review["is_large"]:
        size_icon = "⚠"
        size_text = f"Large PR ({review['total_lines']} lines changed)"
    else:
        size_icon = "✓"
        size_text = f"PR size OK ({review['total_lines']} lines changed)"

    if review["has_jira_key"]:
        jira_icon = "✓"
        jira_text = "Jira key present in PR body"
    else:
        jira_icon = "⚠"
        jira_text = "No Jira key in PR body"

    if review["workflow_changed"]:
        workflow_icon = "⚠"
        workflow_text = "Workflow files changed"
    else:
        workflow_icon = "✓"
        workflow_text = "No workflow files changed"

    if review["needs_docs"]:
        docs_icon = "⚠"
        docs_text = "Code changed without README/docs update"
    else:
        docs_icon = "✓"
        docs_text = "Documentation check OK"

    return [
        (ci_icon, ci_text),
        (secret_icon, secret_text),
        (size_icon, size_text),
        (jira_icon, jira_text),
        (workflow_icon, workflow_text),
        (docs_icon, docs_text),
    ]


def print_review(review, checklist_only=False):
    print(SEPARATOR)
    print(f"  PR #{review['number']} — {review['title']}")
    print(f"  Author: {review['author']}  |  Branch: {review['branch']}  |  State: {review['state']}")
    print(f"  CI: {format_ci_header(review['checks'])}")
    print(SEPARATOR)
    print()
    print("  Checklist:")
    for icon, text in checklist_entries(review):
        print(f"    {icon}  {text}")
    if checklist_only:
        print()
        print(f"  Recommendation: {review['recommendation']}")
        print(SEPARATOR)
        return
    print()
    print(f"  Changed files ({len(review['files'])}):")
    for item in review["files"]:
        print(f"    {item['status']} {item['path']}")
    print()
    if review["sensitive_paths"]:
        print("  Sensitive paths:")
        for path in review["sensitive_paths"]:
            print(f"    - {path}")
    else:
        print("  Sensitive paths: none")
    print()
    print(f"  Recommendation: {review['recommendation']}")
    print(SEPARATOR)


def find_issue_file(issue_key):
    issues_dir = Path(__file__).parent.parent / "issues"
    matches = sorted(path for path in issues_dir.rglob(f"{issue_key}*.md") if path.is_file())
    if not matches:
        raise RuntimeError(f"Issue file not found for {issue_key}")
    if len(matches) > 1:
        raise RuntimeError(f"Multiple issue files found for {issue_key}: {', '.join(str(path) for path in matches)}")
    return matches[0]


def build_issue_entry(issue_key, review):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    ci_bits = []
    if review["checks"]["failed"]:
        ci_bits.append(f"{review['checks']['failed']} failed")
    if review["checks"]["pending"]:
        ci_bits.append(f"{review['checks']['pending']} pending")
    if review["checks"]["passed"]:
        ci_bits.append(f"{review['checks']['passed']} passing")
    ci_text = ", ".join(ci_bits) or "no checks reported"
    secret_text = "Possible secret patterns detected" if review["secret_hits"] else "No secrets detected"
    workflow_text = "Workflow files changed" if review["workflow_changed"] else "No workflow changes"
    return (
        f"### {timestamp} — PR Review\n\n"
        f"Reviewed PR #{review['number']} ({review['title']}):\n"
        f"- CI: {ci_text}\n"
        f"- {secret_text}, {workflow_text.lower()}\n"
        f"- {review['total_lines']} lines changed\n"
        f"- {review['recommendation']}\n\n"
        f"- WORKLOG 0.25h: Reviewed PR #{review['number']} for {issue_key}.\n"
    )


def insert_issue_entry(text, entry):
    pattern = re.compile(r"(## Actions\s*\n\s*-+\s*\n(?:\s*\n)*)", re.MULTILINE)
    match = pattern.search(text)
    if match:
        return text[:match.end()] + entry + "\n" + text[match.end():]
    actions_match = re.search(r"^## Actions\s*$", text, flags=re.MULTILINE)
    if not actions_match:
        raise RuntimeError("Issue file is missing ## Actions section")
    insert_at = actions_match.end()
    return text[:insert_at] + "\n\n" + entry + "\n" + text[insert_at:]


def append_to_issue(issue_key, review):
    issue_file = find_issue_file(issue_key)
    original = issue_file.read_text(encoding="utf-8")
    updated = insert_issue_entry(original, build_issue_entry(issue_key, review))
    issue_file.write_text(updated, encoding="utf-8")
    print(f"✓ Appended findings to {issue_file}")
    return 0


def list_my_prs():
    data = run_json_command([
        "gh", "search", "prs",
        "--owner", ORG_NAME,
        "--author", "@me",
        "--state", "open",
        "--limit", "200",
        "--json", "number,title,repository,updatedAt,url",
    ])
    rows = []
    for item in data:
        rows.append([
            extract_repo_name(item.get("repository")),
            f"#{item.get('number', '')}",
            (item.get("updatedAt") or "")[:10] or "—",
            item.get("title") or "—",
        ])
    if not rows:
        print("⚠ No open PRs found for @me")
        return 0
    print_table(["REPO", "PR", "UPDATED", "TITLE"], rows)
    print(f"✓ Listed {len(rows)} open PR(s)")
    return 0


def has_submitted_reviews(repo, number):
    data = run_json_command([
        "gh", "pr", "view", str(number), "--repo", repo,
        "--json", "reviews",
    ])
    reviews = data.get("reviews") or []
    return any(review.get("submittedAt") for review in reviews)


def list_stale_prs():
    threshold = datetime.now(timezone.utc) - timedelta(days=7)
    data = run_json_command([
        "gh", "search", "prs",
        "--owner", ORG_NAME,
        "--state", "open",
        "--limit", "200",
        "--json", "number,title,author,repository,createdAt,updatedAt,url",
    ])
    rows = []
    for item in data:
        created_at = iso_to_datetime(item.get("createdAt"))
        if not created_at or created_at.astimezone(timezone.utc) > threshold:
            continue
        repo = extract_repo_name(item.get("repository"))
        number = int(item.get("number", 0))
        if has_submitted_reviews(repo, number):
            continue
        rows.append([
            repo,
            f"#{number}",
            format_age(item.get("createdAt")),
            extract_login(item.get("author")),
            item.get("title") or "—",
        ])
    if not rows:
        print("✓ No stale PRs found")
        return 0
    print_table(["REPO", "PR", "AGE", "AUTHOR", "TITLE"], rows)
    print(f"⚠ Found {len(rows)} stale PR(s) older than 7 days with no submitted reviews")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Automated GitHub PR review helper")
    parser.add_argument("--repo", help="Target repository in OWNER/REPO form")
    parser.add_argument("--pr", type=int, metavar="NUMBER", help="Pull request number to review")
    parser.add_argument("--checklist", action="store_true", help="Show checklist only for a PR review")
    parser.add_argument("--to-issue", metavar="<PROJECT>-KEY", help="Append review findings to an issue file")
    parser.add_argument("--my-prs", action="store_true", help="List open PRs authored by @me across <GITHUB_ORG>")
    parser.add_argument("--stale", action="store_true", help="List PRs older than 7 days with no submitted reviews")
    return parser


def main():
    load_env_file()
    parser = build_parser()
    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help()
        return 1
    try:
        actions = [bool(args.pr), args.my_prs, args.stale]
        if sum(actions) != 1:
            raise RuntimeError("Choose exactly one of --pr, --my-prs, or --stale")
        if args.checklist and not args.pr:
            raise RuntimeError("--checklist requires --pr")
        if args.to_issue and not args.pr:
            raise RuntimeError("--to-issue requires --pr")
        if args.my_prs:
            return list_my_prs()
        if args.stale:
            return list_stale_prs()
        repo = resolve_repo(args.repo)
        review = build_review(repo, args.pr)
        print_review(review, checklist_only=args.checklist)
        if args.to_issue:
            return append_to_issue(args.to_issue, review)
        return 0
    except Exception as exc:
        fail(str(exc),
             causes=["gh command not found or returned non-zero",
                     "GitHub token not set or expired"],
             try_=["gh auth status", "gh auth login"])


if __name__ == "__main__":
    sys.exit(main())
