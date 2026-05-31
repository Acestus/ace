#!/usr/bin/env python3
"""
swa_deploy.py — Commit, push, and watch a GitHub Actions deploy for a Static Web App repo.

Usage:
    python3 scripts/swa_deploy.py --repo Acestus/fabricweb [--message "commit msg"] [--watch]
    python3 scripts/swa_deploy.py --repo Acestus/fabricweb --watch-run RUN_ID
    python3 scripts/swa_deploy.py --repo Acestus/fabricweb --status

Flags:
    --repo OWNER/REPO      GitHub repo (required)
    --message MSG          Commit message (default: "chore: deploy")
    --watch                Stream Actions output after push (default: true)
    --no-watch             Push only, don't wait for Actions
    --watch-run RUN_ID     Watch a specific existing run (no commit/push)
    --status               Show latest run + SWA resource status, no deploy

Examples:
    # Commit staged files and deploy
    python3 scripts/swa_deploy.py --repo Acestus/fabricweb

    # Watch a failed run without re-deploying
    python3 scripts/swa_deploy.py --repo Acestus/fabricweb --watch-run 26704151635

    # Just check current state
    python3 scripts/swa_deploy.py --repo Acestus/fabricweb --status
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


# ── helpers ──────────────────────────────────────────────────────────────────

def run(cmd: list[str], capture=True, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check,
    )


def gh(*args, json_out=False) -> str | dict | list:
    cmd = ["gh"] + list(args)
    if json_out:
        cmd += ["--json"]
    result = run(cmd)
    if json_out:
        return json.loads(result.stdout)
    return result.stdout.strip()


def print_section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


# ── git helpers ───────────────────────────────────────────────────────────────

def git_status() -> str:
    return run(["git", "status", "--short"]).stdout.strip()


def git_push(message: str) -> bool:
    status = git_status()
    if not status:
        print("  ℹ  Nothing to commit — pushing as-is")
    else:
        print(f"  Staging all changes:\n{status}")
        run(["git", "add", "-A"], capture=False)
        run(["git", "commit", "-m", message,
             "--trailer", "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"],
            capture=False)

    result = run(["git", "push"], capture=False, check=False)
    return result.returncode == 0


# ── Actions helpers ───────────────────────────────────────────────────────────

def latest_run_id(repo: str) -> str | None:
    result = run(["gh", "run", "list", "--repo", repo, "--limit", "1",
                  "--json", "databaseId"])
    data = json.loads(result.stdout)
    if not data:
        return None
    return str(data[0]["databaseId"])


def watch_run(repo: str, run_id: str):
    print(f"\n  👁  Watching run {run_id} → https://github.com/{repo}/actions/runs/{run_id}")
    result = subprocess.run(
        ["gh", "run", "watch", run_id, "--repo", repo],
        check=False,
    )
    return result.returncode == 0


def run_summary(repo: str, run_id: str) -> dict:
    result = run(["gh", "run", "view", run_id, "--repo", repo,
                  "--json", "status,conclusion,name,url,jobs"])
    return json.loads(result.stdout)


def print_run_summary(repo: str, run_id: str):
    summary = run_summary(repo, run_id)
    status = summary.get("conclusion") or summary.get("status")
    icon = {"success": "✅", "failure": "❌", "cancelled": "⛔"}.get(status, "⏳")
    print(f"\n  {icon} Run {run_id}: {status.upper()}")
    print(f"     URL: {summary.get('url')}")

    jobs = summary.get("jobs", [])
    for job in jobs:
        j_status = job.get("conclusion") or job.get("status") or "?"
        j_icon = {"success": "✓", "failure": "✗", "skipped": "-"}.get(j_status, "·")
        print(f"     {j_icon} {job['name']}: {j_status}")

    if status == "failure":
        print("\n  Run failed logs:")
        subprocess.run(
            ["gh", "run", "view", run_id, "--repo", repo, "--log-failed"],
            check=False,
        )


# ── SWA status from Azure ─────────────────────────────────────────────────────

def check_swa_status(swa_name: str, resource_group: str):
    """Query Azure for the SWA hostname. Requires az login."""
    try:
        result = run([
            "az", "staticwebapp", "show",
            "--name", swa_name,
            "--resource-group", resource_group,
            "--query", "{hostname:defaultHostname,state:repositoryUrl,sku:sku.name}",
            "--output", "json",
        ], check=False)
        if result.returncode != 0:
            print("  ⚠  Could not reach Azure (not logged in or resource not yet deployed)")
            return
        data = json.loads(result.stdout)
        print(f"  🌐 SWA hostname  : {data.get('hostname', 'unknown')}")
        print(f"  📦 SKU           : {data.get('sku', 'unknown')}")
        print(f"  🔗 Full URL      : https://{data.get('hostname')}")
    except Exception as e:
        print(f"  ⚠  Azure query failed: {e}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, help="GitHub owner/repo")
    parser.add_argument("--message", default="chore: deploy", help="Commit message")
    parser.add_argument("--watch", action="store_true", default=True)
    parser.add_argument("--no-watch", dest="watch", action="store_false")
    parser.add_argument("--watch-run", metavar="RUN_ID", help="Watch a specific run")
    parser.add_argument("--status", action="store_true", help="Show status only")
    parser.add_argument("--swa-name", help="SWA resource name (for Azure check)")
    parser.add_argument("--rg", help="Resource group (for Azure check)")
    args = parser.parse_args()

    # ── status only ──────────────────────────────────────────────────────────
    if args.status:
        print_section(f"Status — {args.repo}")
        run_id = latest_run_id(args.repo)
        if run_id:
            print_run_summary(args.repo, run_id)
        if args.swa_name and args.rg:
            check_swa_status(args.swa_name, args.rg)
        return

    # ── watch existing run ───────────────────────────────────────────────────
    if args.watch_run:
        print_section(f"Watching run {args.watch_run}")
        success = watch_run(args.repo, args.watch_run)
        print_run_summary(args.repo, args.watch_run)
        if args.swa_name and args.rg and success:
            check_swa_status(args.swa_name, args.rg)
        sys.exit(0 if success else 1)

    # ── commit + push ────────────────────────────────────────────────────────
    print_section(f"Deploy — {args.repo}")
    ok = git_push(args.message)
    if not ok:
        print("  ❌ Push failed")
        sys.exit(1)
    print("  ✓  Pushed to GitHub")

    if not args.watch:
        run_id = latest_run_id(args.repo)
        print(f"  ℹ  Run: https://github.com/{args.repo}/actions/runs/{run_id}")
        return

    # Give Actions a few seconds to pick up the push
    print("  ⏳ Waiting for Actions to start...")
    time.sleep(6)

    run_id = latest_run_id(args.repo)
    if not run_id:
        print("  ⚠  No run found — check https://github.com/{args.repo}/actions")
        return

    success = watch_run(args.repo, run_id)
    print_run_summary(args.repo, run_id)

    if args.swa_name and args.rg and success:
        print_section("Azure SWA")
        check_swa_status(args.swa_name, args.rg)


if __name__ == "__main__":
    main()
