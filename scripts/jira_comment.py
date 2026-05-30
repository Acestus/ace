#!/usr/bin/env python3
"""
jira_comment.py — Append a COMMENT entry to an issue file and push to trigger CI sync.

Usage:
    python3 scripts/jira_comment.py --key <PROJECT>-257 --comment "Following up on budget approval."

The comment is appended under today's Actions section in the issue file.
When pushed to main, the jira-worklog-sync CI workflow picks it up and posts it to Jira.
"""

import argparse
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail

REPO_ROOT = Path(__file__).parent.parent
ISSUES_DIR = REPO_ROOT / "issues"


def find_issue_file(key: str) -> Path | None:
    for folder in ISSUES_DIR.iterdir():
        if folder.name.startswith(key + " ") or folder.name == key:
            for f in folder.iterdir():
                if f.suffix == ".md":
                    return f
    return None


def ensure_actions_section(content: str, today: str) -> str:
    """Ensure ## Actions and a today date header exist; return updated content."""
    if "## Actions" not in content:
        content = content.rstrip() + "\n\n## Actions\n"
    if f"### {today}" not in content:
        # Insert today's date header at the top of the Actions section
        content = content.replace(
            "## Actions\n",
            f"## Actions\n\n### {today}\n",
            1,
        )
    return content


def append_comment(issue_file: Path, comment: str, today: str) -> None:
    content = issue_file.read_text()
    content = ensure_actions_section(content, today)

    comment_line = f"- COMMENT: {comment}\n"

    # Insert after the ### today header inside Actions
    date_header = f"### {today}\n"
    idx = content.find(date_header)
    if idx == -1:
        # Fallback: append at end of file
        content = content.rstrip() + f"\n{comment_line}"
    else:
        insert_at = idx + len(date_header)
        content = content[:insert_at] + comment_line + content[insert_at:]

    issue_file.write_text(content)
    print(f"  ✓ Appended COMMENT to {issue_file.name}")


def git_commit_push(issue_file: Path, key: str, comment_preview: str) -> None:
    short = comment_preview[:60] + ("…" if len(comment_preview) > 60 else "")
    msg = f"comment({key}): {short}\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    subprocess.run(["git", "add", str(issue_file)], cwd=REPO_ROOT, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=REPO_ROOT, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=REPO_ROOT, check=True)
    print(f"  ✓ Committed and pushed — CI will post comment to {key}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a Jira COMMENT via issue file.")
    parser.add_argument("--key", required=True, help="Jira issue key (e.g. <PROJECT>-257)")
    parser.add_argument("--comment", required=True, help="Comment text to post")
    parser.add_argument("--no-push", action="store_true", help="Write file only, skip git commit/push")
    args = parser.parse_args()

    today = date.today().strftime("%Y-%m-%d")

    issue_file = find_issue_file(args.key)
    if not issue_file:
        fail(
            f"No issue file found for {args.key} in {ISSUES_DIR}",
            causes=[
                f"Stub never created for {args.key}",
                "Key typo in --key argument",
            ],
            try_=[
                f"python3 scripts/jira_create_stub.py --key {args.key}",
                f"ls issues/ | grep -i {args.key.split('-')[0].lower()}",
            ],
        )

    print(f"  → Issue file: {issue_file.relative_to(REPO_ROOT)}")
    append_comment(issue_file, args.comment, today)

    if args.no_push:
        print("  ⚠  --no-push set — skipping commit. CI will not sync until you push.")
    else:
        git_commit_push(issue_file, args.key, args.comment)


if __name__ == "__main__":
    main()
