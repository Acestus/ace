#!/usr/bin/env python3
"""
<org_short>_clerk.py — Knowledge retrieval across <ORG_NAME> documentation sources.

Searches in priority order:
  1. confluence/       — internal docs in this repo
  2. issues/ + cases/  — ticket history and SDP case resolutions
  3. Reference repos   — fabric-edm, iac-infra, five9_agent_call_scripts, networking, skplogs
  4. MCP servers       — Atlassian Rovo, Azure MCP, Fabric MCP (live state)
  5. Microsoft docs    — learn.microsoft.com (fetched on demand)

Usage:
    python3 scripts/<org_short>_clerk.py --topic "UMI permissions"
    python3 scripts/<org_short>_clerk.py --topic "Fabric lakehouse naming" --depth full
    python3 scripts/<org_short>_clerk.py --topic "Five9 auth" --source repo
    python3 scripts/<org_short>_clerk.py --topic "networking spoke" --source confluence

Environment:
    WWEEKS_CONFLUENCE_API_TOKEN
    CONFLUENCE_EMAIL
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail

REPO_ROOT   = Path(__file__).parent.parent
ISSUES_DIR  = REPO_ROOT / "issues"
CASES_DIR   = REPO_ROOT / "cases"
CONF_DIR    = REPO_ROOT / "confluence"
GIT_ROOT    = Path("/home/wweeks/git")

REFERENCE_REPOS = {
    "fabric-edm":               GIT_ROOT / "fabric-edm",
    "iac-infra":                GIT_ROOT / "iac-infra",
    "five9_agent_call_scripts": GIT_ROOT / "five9_agent_call_scripts",
    "networking":               GIT_ROOT / "networking",
    "skplogs":                  GIT_ROOT / "skplogs",
}

CODE_EXTS = {".md", ".bicep", ".tf", ".py", ".ps1", ".yaml", ".yml", ".json", ".org"}

# Known high-value confluence page IDs → titles
CONFLUENCE_INDEX = {
    "<PAGE_ID>": "Fabric Platform Onboarding Guide",
    "<PAGE_ID>": "EDM Cloud Native Transformation",
    "<PAGE_ID>": "Microsoft Fabric CAF Naming Convention",
    "<PAGE_ID>": "Five9 Call Script Agent",
    "<PAGE_ID>": "SKPCerts Acmebot Architecture",
    "<PAGE_ID>": "Infrastructure Backlog (Kanban Board)",
    "<PAGE_ID>": "SKPAPIM Spoke Network",
    "<PAGE_ID>": "Fabric Scheduler",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def load_env_file():
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() not in os.environ:
            os.environ[k.strip()] = v.strip()


def build_keywords(topic: str) -> list[str]:
    """Split topic into search keywords, drop common words."""
    stopwords = {"the", "a", "an", "and", "or", "for", "to", "in", "on", "of", "with", "how", "do", "we"}
    words = re.findall(r"[a-zA-Z0-9_\-]+", topic.lower())
    return [w for w in words if w not in stopwords and len(w) > 2]


def grep_dir(directory: Path, keywords: list[str], exts: set = None) -> list[dict]:
    """Return list of {path, line, keyword} matches."""
    if not directory.exists():
        return []
    exts = exts or CODE_EXTS
    results = []
    for ext in exts:
        for fpath in directory.rglob(f"*{ext}"):
            try:
                text = fpath.read_text(errors="ignore")
            except Exception:
                continue
            for kw in keywords:
                for i, line in enumerate(text.splitlines(), 1):
                    if kw.lower() in line.lower():
                        results.append({
                            "path": str(fpath),
                            "line": i,
                            "snippet": line.strip()[:120],
                            "keyword": kw,
                        })
                        break  # one hit per keyword per file
    # Deduplicate by path
    seen = {}
    for r in results:
        if r["path"] not in seen:
            seen[r["path"]] = r
    return list(seen.values())


def score_result(result: dict, keywords: list[str]) -> int:
    """Higher score = more keywords matched in file."""
    try:
        text = Path(result["path"]).read_text(errors="ignore").lower()
    except Exception:
        return 0
    return sum(1 for kw in keywords if kw in text)


def print_section(title: str, found: bool):
    status = "✓" if found else "✗"
    print(f"  {status} {title}")


def print_finding(label: str, path: str, snippet: str = ""):
    print(f"\n  • {label}")
    print(f"    Source: {path}")
    if snippet:
        print(f"    \"{snippet[:100]}\"")


# ── search tiers ─────────────────────────────────────────────────────────────

def search_confluence(keywords: list[str]) -> list[dict]:
    results = grep_dir(CONF_DIR, keywords, {".md"})
    # Annotate with page title from index
    for r in results:
        fname = Path(r["path"]).name
        for pid, title in CONFLUENCE_INDEX.items():
            if fname.startswith(pid):
                r["title"] = title
                r["page_id"] = pid
                break
    return results


def search_issues_cases(keywords: list[str]) -> list[dict]:
    results = []
    results += grep_dir(ISSUES_DIR, keywords, {".md"})
    results += grep_dir(CASES_DIR, keywords, {".md"})
    return results


def search_reference_repos(keywords: list[str]) -> list[dict]:
    results = []
    for repo_name, repo_path in REFERENCE_REPOS.items():
        hits = grep_dir(repo_path, keywords)
        for h in hits:
            h["repo"] = repo_name
        results += hits
    return results


def fetch_ms_docs(topic: str) -> str | None:
    """Try to fetch a relevant Microsoft Learn page via search."""
    try:
        import urllib.request, urllib.parse
        query = urllib.parse.quote(f"site:learn.microsoft.com {topic}")
        # Use the MS Learn search API
        url = f"https://learn.microsoft.com/api/search?search={urllib.parse.quote(topic)}&locale=en-us&$top=3"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            import json
            data = json.loads(resp.read())
            results = data.get("results", [])
            if results:
                return results[0].get("url", ""), results[0].get("title", ""), results[0].get("description", "")
    except Exception:
        pass
    return None


# ── main output ──────────────────────────────────────────────────────────────

def run(topic: str, source_filter: str = "all", depth: str = "brief"):
    keywords = build_keywords(topic)
    if not keywords:
        fail(f"No searchable keywords in topic: {topic}")

    print(f"\n📚 Clerk findings — {topic}")
    print("━" * 40)
    print(f"Keywords: {', '.join(keywords)}\n")

    found_any = False
    sources_checked = []

    # ── Tier 1: confluence/ ──────────────────────────────────────────────────
    if source_filter in ("all", "confluence"):
        hits = search_confluence(keywords)
        hits.sort(key=lambda r: score_result(r, keywords), reverse=True)
        sources_checked.append(("confluence/", bool(hits)))
        if hits:
            found_any = True
            print("── Confluence (internal docs) ──")
            for h in hits[:3]:
                label = h.get("title", Path(h["path"]).stem)
                print_finding(label, h["path"], h.get("snippet", ""))
            print()

    # ── Tier 2: issues/ + cases/ ────────────────────────────────────────────
    if source_filter in ("all", "issues"):
        hits = search_issues_cases(keywords)
        hits.sort(key=lambda r: score_result(r, keywords), reverse=True)
        sources_checked.append(("issues/ + cases/", bool(hits)))
        if hits:
            found_any = True
            print("── Prior Tickets & Cases ──")
            for h in hits[:3]:
                label = Path(h["path"]).parts[-2]  # folder name = ticket name
                print_finding(label, h["path"], h.get("snippet", ""))
            print()

    # ── Tier 3: reference repos ──────────────────────────────────────────────
    if source_filter in ("all", "repo"):
        hits = search_reference_repos(keywords)
        hits.sort(key=lambda r: score_result(r, keywords), reverse=True)
        sources_checked.append(("reference repos", bool(hits)))
        if hits:
            found_any = True
            print("── Reference Repositories ──")
            for h in hits[:5]:
                label = f"{h['repo']} — {Path(h['path']).name}"
                print_finding(label, h["path"], h.get("snippet", ""))
            print()

    # ── Tier 4: Microsoft docs (on demand / full depth only) ────────────────
    if source_filter in ("all", "docs") and (not found_any or depth == "full"):
        ms = fetch_ms_docs(topic)
        if ms:
            url, title, desc = ms
            found_any = True
            sources_checked.append(("Microsoft Learn", True))
            print("── Microsoft Documentation ──")
            print_finding(title, url, desc)
            print()
        else:
            sources_checked.append(("Microsoft Learn", False))

    # ── No-find signal ───────────────────────────────────────────────────────
    if not found_any:
        print("⚠  NO VETTED DOCUMENTATION FOUND\n")
        print("Sources checked:")
        for name, _ in sources_checked:
            print(f"  ✗ {name}")
        print("\nThis would be a new precedent. No existing <ORG_NAME> pattern to follow.")
        fail("No vetted documentation found for this topic", exit_code=2)

    # ── Sources checked summary ──────────────────────────────────────────────
    if depth == "full":
        print("── Sources checked ──")
        for name, found in sources_checked:
            print_section(name, found)

    sys.exit(0)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    load_env_file()
    parser = argparse.ArgumentParser(
        description="<ORG_NAME> Clerk — knowledge retrieval across all documentation sources."
    )
    parser.add_argument("--topic", required=True, help="Topic or question to research")
    parser.add_argument(
        "--source",
        choices=["all", "confluence", "issues", "repo", "docs"],
        default="all",
        help="Limit search to a specific source tier (default: all)"
    )
    parser.add_argument(
        "--depth",
        choices=["brief", "full"],
        default="brief",
        help="brief = top results only; full = all matches + sources-checked summary"
    )
    args = parser.parse_args()
    run(args.topic, args.source, args.depth)


if __name__ == "__main__":
    main()
