#!/usr/bin/env python3
"""
end_my_day.py — Stop active timers and close today's daily note.

Usage:
    python3 scripts/end_my_day.py
    python3 scripts/end_my_day.py --blocker "<PROJECT>-342: waiting for <USER_C>"
    python3 scripts/end_my_day.py --no-push

Environment (reads from .env if not already set):
    CONFLUENCE_EMAIL
    WWEEKS_CONFLUENCE_API_TOKEN
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TIMERS_FILE = REPO_ROOT / "planner" / ".timers.json"

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail


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



def read_timers() -> dict:
    if not TIMERS_FILE.exists():
        return {}
    try:
        return json.loads(TIMERS_FILE.read_text() or "{}")
    except json.JSONDecodeError as error:
        fail(
            f"Timer file is corrupted: {TIMERS_FILE}",
            causes=["A previous write was interrupted mid-file",
                    f"Manual edit introduced invalid JSON: {error}"],
            try_=[f"Inspect the file: cat {TIMERS_FILE}",
                  "Restore from git: git checkout -- planner/.timers.json"],
        )



def active_timer_keys(timers: dict) -> list[str]:
    active = []
    for key, info in timers.items():
        if isinstance(info, dict) and info.get("start") and not info.get("end"):
            active.append(key)
    return sorted(active)



def extract_duration(output: str) -> str:
    for line in output.splitlines():
        if "Duration :" in line:
            return line.split("Duration :", 1)[1].strip().split("(", 1)[0].strip()
    return "duration unavailable"



def stop_timer(key: str) -> None:
    result = subprocess.run(
        ["python3", "scripts/tl", "stop", key],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        fail(
            f"Timer stop failed for {key}",
            causes=["scripts/tl encountered an error stopping the timer",
                    "Timer file may be locked or corrupted"],
            try_=[f"Run manually: python3 scripts/tl stop {key}",
                  f"Check timer state: cat {TIMERS_FILE}"],
            exit_code=result.returncode,
        )
    duration = extract_duration(result.stdout)
    print(f"  ✓ {key} stopped — {duration}")



def current_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""



def latest_commit() -> str:
    result = subprocess.run(
        ["git", "--no-pager", "log", "-1", "--pretty=%h %s"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()



def run_daily_note_end(blockers: list[str], no_push: bool) -> None:
    command = ["python3", "scripts/daily_note.py", "--end"]
    for blocker in blockers:
        command.extend(["--blocker", blocker])
    if no_push:
        command.append("--no-push")

    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        fail(
            "daily_note.py --end failed",
            causes=["daily_note.py returned a non-zero exit code",
                    "Git push may have failed if --no-push was not set"],
            try_=["Run manually: python3 scripts/daily_note.py --end",
                  "Pass --no-push to skip the git push step"],
            exit_code=result.returncode,
        )



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stop timers and close today's daily note")
    parser.add_argument("--blocker", action="append", dest="blockers", metavar="TEXT",
                        help="Blocker to include (repeat for multiple)")
    parser.add_argument("--no-push", action="store_true", help="Skip git push")
    return parser.parse_args()



def main():
    load_env_file()
    args = parse_args()
    before_head = current_head()

    active_keys = active_timer_keys(read_timers())
    if active_keys:
        print("⏱  Stopping active timers...")
        for key in active_keys:
            stop_timer(key)
    else:
        print("✓ No active timers running.")

    print()
    print("Closing day...")
    run_daily_note_end(args.blockers or [], args.no_push)

    after_head = current_head()
    if after_head and after_head != before_head:
        print(f"✓ Latest commit: {latest_commit()}")

    if args.no_push:
        print("✓ EOD complete. Push skipped.")
    elif after_head and after_head != before_head:
        print("✓ EOD complete. Committed and pushed.")
    else:
        print("⚠  EOD complete. No new commit was created.")



if __name__ == "__main__":
    main()
