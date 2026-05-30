#!/usr/bin/env python3
"""
Validates shell commands for forbidden patterns.
Exit 0 = clean. Exit 1 = violations found.

Usage:
  python3 scripts/lint_bash_commands.py "cd /foo"          # check a command string
  python3 scripts/lint_bash_commands.py --file script.sh   # check a file
  python3 scripts/lint_bash_commands.py --staged           # check git staged files

Rule: cd must not be chained with other commands on the same line.
"""

import re
import sys
import subprocess

CD_CHAIN = re.compile(r'\bcd\b[^;\n]*&&')
CD_SEMICOLON_CHAIN = re.compile(r'\bcd\b[^;\n]*;[^#\n]')

VIOLATIONS = [
    (CD_CHAIN, "cd combined with && -- use separate bash calls"),  # noqa
    (CD_SEMICOLON_CHAIN, "cd combined with ; command -- use separate bash calls"),  # noqa
]


def check_text(text, source="<input>"):
    found = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # Skip comment lines and lines with noqa marker
        if stripped.startswith("#") or "# noqa" in line or "# nolint" in line:
            continue
        for pattern, message in VIOLATIONS:
            if pattern.search(line):
                found.append(f"  {source}:{lineno}: ⛔ {message}\n    {line.strip()}")
    return found


def check_staged():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True
    )
    staged = [f for f in result.stdout.splitlines()
              if f.endswith((".sh", ".py", ".yaml", ".yml"))]

    all_violations = []
    for path in staged:
        try:
            content = open(path).read()
            all_violations.extend(check_text(content, path))
        except Exception:
            pass
    return all_violations


if __name__ == "__main__":
    violations = []

    if "--staged" in sys.argv:
        violations = check_staged()
    elif "--file" in sys.argv:
        idx = sys.argv.index("--file")
        path = sys.argv[idx + 1]
        violations = check_text(open(path).read(), path)
    elif len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
        violations = check_text(cmd)
    else:
        print(__doc__)
        sys.exit(0)

    if violations:
        print("⛔ cd-chain violations found:")
        for v in violations:
            print(v)
        sys.exit(1)
    else:
        print("✓ No cd-chain violations")
        sys.exit(0)
