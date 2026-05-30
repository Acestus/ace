#!/usr/bin/env python3
"""Insert 1-3 sentence summaries before each Loom !embed directive in confluence markdown files."""
import re
import json
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
CONFLUENCE_DIR = PROJ / "confluence"
SUMMARIES_FILE = PROJ / "scripts" / "loom-summaries.json"


def load_summaries():
    with open(SUMMARIES_FILE) as f:
        return json.load(f)


def process_file(md_path, summaries):
    """Process a single markdown file, inserting summaries before Loom embeds."""
    with open(md_path) as f:
        lines = f.readlines()

    new_lines = []
    insertions = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this line is a Loom embed
        m = re.match(r'^(!embed\[.*?\]\((https://www\.loom\.com/share/\w+)\))\s*$', line)
        if m:
            url = m.group(2)
            summary = summaries.get(url)
            
            if summary:
                # Check if the previous non-blank line is already a summary we inserted
                # (avoid double-insertion on re-runs)
                prev_content_idx = len(new_lines) - 1
                while prev_content_idx >= 0 and new_lines[prev_content_idx].strip() == '':
                    prev_content_idx -= 1
                
                prev_line = new_lines[prev_content_idx].strip() if prev_content_idx >= 0 else ''
                
                # Skip if the previous content line IS the summary (idempotency)
                # Check both tagged (*▶ ...*) and plain formats
                tagged_summary = f"*▶ {summary}*"
                if prev_line == tagged_summary or prev_line == summary:
                    new_lines.append(line)
                    i += 1
                    continue
                
                # Ensure there's a blank line before the summary
                if new_lines and new_lines[-1].strip() != '':
                    new_lines.append('\n')
                
                # Insert summary paragraph with italic ▶ tag
                new_lines.append(f"*▶ {summary}*\n")
                new_lines.append('\n')
                insertions += 1
            
            new_lines.append(line)
        else:
            new_lines.append(line)
        
        i += 1

    if insertions > 0:
        with open(md_path, 'w') as f:
            f.writelines(new_lines)
    
    return insertions


def main():
    summaries = load_summaries()
    print(f"Loaded {len(summaries)} summaries")
    
    total = 0
    for md in sorted(CONFLUENCE_DIR.glob("*.md")):
        count = process_file(md, summaries)
        if count > 0:
            print(f"  {md.name}: {count} summaries inserted")
            total += count
    
    print(f"\nTotal: {total} summaries inserted across all files")


if __name__ == "__main__":
    main()
