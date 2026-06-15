#!/usr/bin/env python3
"""rounds_transition.py — Execute mechanical transition steps for a rounds ticket.

The AI handles judgment (what did you do? who's it waiting on? write worklog).
This script handles deterministic execution after judgment is complete.

Usage:
    rounds_transition.py --key <PROJECT>-123 --action done    [--next <PROJECT>-456] [--no-push]
    rounds_transition.py --key <PROJECT>-123 --action waiting [--next <PROJECT>-456] [--no-push]
    rounds_transition.py --key <PROJECT>-123 --action blocked [--next <PROJECT>-456] [--no-push]
    rounds_transition.py --key <PROJECT>-123 --action park

Actions:
    done     Stop timer · flow:done · activate next · commit+push
    waiting  Stop timer · flow:waiting · activate next · commit+push
    blocked  Stop timer · flow stays active · commit+push
    park     Stop timer only — flow unchanged, no push
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECTS_DIR = Path("/home/wweeks/git/projects")
SCRIPTS = PROJECTS_DIR / "scripts"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, check=check, capture_output=False, text=True, cwd=str(PROJECTS_DIR)
    )


def stop_timer(key: str) -> None:
    status = subprocess.run(
        ["python3", str(SCRIPTS / "tl.py"), "status"],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(PROJECTS_DIR),
    )
    if key not in status.stdout:
        return
    run(["python3", str(SCRIPTS / "tl.py"), "stop", key], check=False)


def set_flow(key: str, flow: str) -> None:
    run(["python3", str(SCRIPTS / "linear_set_flow.py"), "--key", key, "--flow", flow])


def create_stub(key: str) -> None:
    """Idempotent — no-op if file already exists."""
    run(["python3", str(SCRIPTS / "linear_create_stub.py"), "--key", key], check=False)


def git_commit_push(key: str, action: str, next_key: str) -> None:
    msg = f"chore(rounds): {action} {key}"
    if next_key:
        msg += f" → {next_key}"
    msg += "\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    run(["git", "add", "-A"])
    result = run(["git", "commit", "-m", msg], check=False)
    if result.returncode == 0:
        run(["git", "push"])


def activate_next(next_key: str) -> None:
    set_flow(next_key, "active")
    create_stub(next_key)


def cmd_done(key: str, next_key: str, no_push: bool) -> None:
    stop_timer(key)
    set_flow(key, "done")
    if next_key:
        activate_next(next_key)
    if not no_push:
        git_commit_push(key, "done", next_key)
    print(f"✓ {key} → done")
    if next_key:
        print(f"✓ {next_key} → active")


def cmd_waiting(key: str, next_key: str, no_push: bool) -> None:
    stop_timer(key)
    set_flow(key, "waiting")
    if next_key:
        activate_next(next_key)
    if not no_push:
        git_commit_push(key, "waiting", next_key)
    print(f"✓ {key} → waiting")
    if next_key:
        print(f"✓ {next_key} → active")


def cmd_blocked(key: str, next_key: str, no_push: bool) -> None:
    """Flow label stays flow:active."""
    stop_timer(key)
    if next_key:
        activate_next(next_key)
    if not no_push:
        git_commit_push(key, "blocked", next_key)
    print(f"✓ {key} → blocked (flow:active retained)")
    if next_key:
        print(f"✓ {next_key} → active")


def cmd_park(key: str) -> None:
    """Stop timer only. Flow unchanged, no push."""
    stop_timer(key)
    print(f"⏸  {key} parked — timer stopped, flow unchanged.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute mechanical rounds transition steps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--key", required=True, help="Current ticket key, e.g. <PROJECT>-123")
    parser.add_argument(
        "--action", required=True, choices=["done", "waiting", "blocked", "park"],
        help="Transition action"
    )
    parser.add_argument(
        "--next", dest="next_key", default="",
        help="Next ticket to activate (set flow:active + create stub)"
    )
    parser.add_argument(
        "--no-push", action="store_true",
        help="Skip git commit + push (dry-run mode)"
    )
    args = parser.parse_args()

    key = args.key.upper()
    next_key = args.next_key.upper() if args.next_key else ""

    if args.action == "park":
        cmd_park(key)
    elif args.action == "done":
        cmd_done(key, next_key, args.no_push)
    elif args.action == "waiting":
        cmd_waiting(key, next_key, args.no_push)
    elif args.action == "blocked":
        cmd_blocked(key, next_key, args.no_push)


if __name__ == "__main__":
    main()
