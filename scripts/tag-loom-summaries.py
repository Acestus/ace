#!/usr/bin/env python3
"""Reformat plain-text Loom summaries to italic with ▶ prefix for visual tagging."""
import json
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
CONFLUENCE_DIR = PROJ / "confluence"
SUMMARIES_FILE = PROJ / "scripts" / "loom-summaries.json"


def main():
    with open(SUMMARIES_FILE) as f:
        summaries = json.load(f)

    summary_set = set(summaries.values())
    total = 0

    for md in sorted(CONFLUENCE_DIR.glob("*.md")):
        with open(md) as f:
            lines = f.readlines()

        changed = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped in summary_set:
                new_lines.append(f"*▶ {stripped}*\n")
                changed = True
                total += 1
            else:
                new_lines.append(line)

        if changed:
            with open(md, 'w') as f:
                f.writelines(new_lines)
            file_count = sum(1 for l in new_lines if l.strip().startswith("*▶"))
            print(f"  {md.name}: {file_count} summaries tagged")

    print(f"\nTotal: {total} summaries reformatted")


if __name__ == "__main__":
    main()
