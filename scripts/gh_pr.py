#!/usr/bin/env python3
"""
gh_pr.py — GitHub Pull Request review helper.

Usage:
    python3 scripts/gh_pr.py --list [--repo OWNER/REPO]
    python3 scripts/gh_pr.py --view NUMBER [--repo OWNER/REPO]
    python3 scripts/gh_pr.py --checks NUMBER [--repo OWNER/REPO]
    python3 scripts/gh_pr.py --approve NUMBER [--body "LGTM"] [--repo OWNER/REPO]
    python3 scripts/gh_pr.py --request-changes NUMBER --body "feedback" [--repo OWNER/REPO]
    python3 scripts/gh_pr.py --comment NUMBER --body "text" [--repo OWNER/REPO]
    python3 scripts/gh_pr.py --diff NUMBER [--repo OWNER/REPO]
    python3 scripts/gh_pr.py --merge NUMBER [--squash] [--repo OWNER/REPO]

Flags:
    --list                 List pull requests.
    --view NUMBER          Show PR summary.
    --checks NUMBER        Show PR check output.
    --approve NUMBER       Approve a PR.
    --request-changes N    Request changes on a PR.
    --comment NUMBER       Leave a PR comment review.
    --diff NUMBER          Show PR diff.
    --merge NUMBER         Merge a PR.
    --body TEXT            Review body text.
    --repo OWNER/REPO      Override the target repository.
    --squash               Use squash merge with --merge.

Environment:
    GH_REPO  — default repo (e.g. <GITHUB_ORG>/projects); overridden by --repo
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_tool


REVIEW_MAP = {
    "APPROVED": "✓",
    "CHANGES_REQUESTED": "✗",
    "REVIEW_REQUIRED": "?",
    None: "—",
}
PASS_STATES = {"SUCCESS", "SUCCESSFUL", "NEUTRAL", "SKIPPED"}
FAIL_STATES = {"FAILURE", "FAILED", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
PENDING_STATES = {"EXPECTED", "PENDING", "IN_PROGRESS", "QUEUED", "REQUESTED", "WAITING"}


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



def run_json_command(command):
    result = run_command(command)
    if result.returncode != 0:
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



def summarize_checks(status_checks):
    if not status_checks:
        return "—"
    passed = 0
    failed = 0
    pending = 0
    for item in status_checks:
        state = str(item.get("conclusion") or item.get("state") or item.get("status") or "PENDING").upper()
        if state in PASS_STATES:
            passed += 1
        elif state in FAIL_STATES:
            failed += 1
        elif state in PENDING_STATES:
            pending += 1
        else:
            pending += 1
    return f"{passed}✓ {failed}✗ {pending}…"



def print_table(headers, rows):
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))



def truncate(text, limit):
    compact = re.sub(r"\s+", " ", (text or "").strip())
    if len(compact) <= limit:
        return compact or "—"
    return compact[: limit - 1] + "…"



def list_prs(repo):
    data = run_json_command([
        "gh", "pr", "list", "--repo", repo,
        "--json", "number,title,state,author,headRefName,reviewDecision,statusCheckRollup",
    ])
    rows = []
    for item in data:
        rows.append([
            str(item.get("number", "")),
            str(item.get("state", "—")),
            REVIEW_MAP.get(item.get("reviewDecision"), "—"),
            summarize_checks(item.get("statusCheckRollup")),
            truncate((item.get("author") or {}).get("login", "—"), 16),
            truncate(item.get("headRefName", "—"), 24),
            truncate(item.get("title", "—"), 70),
        ])
    if not rows:
        print("⚠ No pull requests found")
        return 0
    print_table(["NUMBER", "STATE", "REVIEW", "CI", "AUTHOR", "BRANCH", "TITLE"], rows)
    print(f"✓ Listed {len(rows)} pull request(s)")
    return 0



def view_pr(repo, number):
    item = run_json_command([
        "gh", "pr", "view", str(number), "--repo", repo,
        "--json", "number,title,body,state,author,commits,files,reviewDecision,statusCheckRollup,comments",
    ])
    author = (item.get("author") or {}).get("login", "—")
    body = truncate(item.get("body", ""), 500)
    print(f"Title           : {item.get('title', '—')}")
    print(f"State           : {item.get('state', '—')}")
    print(f"Author          : {author}")
    print(f"Review decision : {item.get('reviewDecision') or '—'} ({REVIEW_MAP.get(item.get('reviewDecision'), '—')})")
    print(f"CI status       : {summarize_checks(item.get('statusCheckRollup'))}")
    print(f"Changed files   : {len(item.get('files') or [])}")
    print(f"Body excerpt    : {body}")
    print("✓ PR details loaded")
    return 0



def run_passthrough(command, success_message):
    result = run_command(command, capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}")
    print(f"✓ {success_message}")
    return 0



def ensure_body(args, option_name):
    if args.body:
        return
    raise RuntimeError(f"{option_name} requires --body")



def build_parser():
    parser = argparse.ArgumentParser(description="GitHub Pull Request review helper")
    parser.add_argument("--repo", help="Target repository in OWNER/REPO form")
    parser.add_argument("--body", help="Review body text")
    parser.add_argument("--squash", action="store_true", help="Use squash merge with --merge")
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument("--list", action="store_true", help="List pull requests")
    action_group.add_argument("--view", type=int, metavar="NUMBER", help="View a pull request")
    action_group.add_argument("--checks", type=int, metavar="NUMBER", help="Show PR checks")
    action_group.add_argument("--approve", type=int, metavar="NUMBER", help="Approve a pull request")
    action_group.add_argument("--request-changes", type=int, metavar="NUMBER", help="Request changes on a pull request")
    action_group.add_argument("--comment", type=int, metavar="NUMBER", help="Comment on a pull request")
    action_group.add_argument("--diff", type=int, metavar="NUMBER", help="Show pull request diff")
    action_group.add_argument("--merge", type=int, metavar="NUMBER", help="Merge a pull request")
    return parser



def main():
    load_env_file()
    parser = build_parser()
    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help()
        return 1
    try:
        repo = resolve_repo(args.repo)
        if args.list:
            return list_prs(repo)
        if args.view is not None:
            return view_pr(repo, args.view)
        if args.checks is not None:
            return run_passthrough(["gh", "pr", "checks", str(args.checks), "--repo", repo], "Checks displayed")
        if args.approve is not None:
            command = ["gh", "pr", "review", str(args.approve), "--repo", repo, "--approve"]
            if args.body:
                command.extend(["--body", args.body])
            return run_passthrough(command, "Review submitted")
        if args.request_changes is not None:
            ensure_body(args, "--request-changes")
            return run_passthrough([
                "gh", "pr", "review", str(args.request_changes), "--repo", repo,
                "--request-changes", "--body", args.body,
            ], "Changes requested")
        if args.comment is not None:
            ensure_body(args, "--comment")
            return run_passthrough([
                "gh", "pr", "review", str(args.comment), "--repo", repo,
                "--comment", "--body", args.body,
            ], "Comment submitted")
        if args.diff is not None:
            return run_passthrough(["gh", "pr", "diff", str(args.diff), "--repo", repo], "Diff displayed")
        if args.merge is not None:
            merge_flag = "--squash" if args.squash else "--merge"
            return run_passthrough(["gh", "pr", "merge", str(args.merge), "--repo", repo, merge_flag], "Merge requested")
        parser.print_help()
        return 1
    except Exception as exc:
        fail(str(exc),
             causes=["gh command not found, returned non-zero, or produced invalid JSON",
                     "Repository not found or no GitHub auth token set"],
             try_=["gh auth status", "gh auth login"])


if __name__ == "__main__":
    sys.exit(main())
