#!/usr/bin/env python3
"""Extract text from VTT transcripts and map them to Loom URLs for summary generation."""
import re
import os
import json
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
TRANSCRIPTS_DIR = PROJ / "transcripts"
LOOM_LIBRARY = PROJ / "docs" / "transcripts" / "loom-library.md"
CONFLUENCE_DIR = PROJ / "confluence"

def parse_loom_library(path):
    """Parse loom-library.md → {url: title}"""
    url_to_title = {}
    with open(path) as f:
        for line in f:
            m = re.search(r'\|\s*\d+\s*\|\s*(.+?)\s*\|\s*\[Link\]\((https://www\.loom\.com/share/\w+)\)', line)
            if m:
                title = m.group(1).strip().rstrip(' ✅')
                url = m.group(2).strip()
                url_to_title[url] = title
    return url_to_title

def find_vtt(title, vtt_files):
    """Find best matching VTT file for a title."""
    # Exact match
    target = f"{title}.vtt"
    if target in vtt_files:
        return target
    # Case-insensitive match
    for f in vtt_files:
        if f.lower() == target.lower():
            return f
    # Try with apostrophe variants
    for f in vtt_files:
        if f.lower().replace("'s", "s").replace("'", "") == target.lower().replace("'s", "s").replace("'", ""):
            return f
    return None

def extract_vtt_text(path, max_words=300):
    """Extract plain text from a VTT file, up to max_words."""
    with open(path) as f:
        content = f.read()
    
    lines = content.split('\n')
    text_lines = []
    for line in lines:
        line = line.strip()
        # Skip WEBVTT header, blank lines, timestamps, and cue IDs
        if not line or line == 'WEBVTT':
            continue
        if re.match(r'\d{2}:\d{2}:\d{2}\.\d{3}\s*-->', line):
            continue
        if re.match(r'^[a-f0-9-]+/\d+-\d+$', line):
            continue
        text_lines.append(line)
    
    full_text = ' '.join(text_lines)
    # Clean up double spaces
    full_text = re.sub(r'\s+', ' ', full_text).strip()
    
    words = full_text.split()
    return ' '.join(words[:max_words])

def get_loom_urls_from_confluence():
    """Get all unique Loom URLs used in confluence files."""
    urls = set()
    for md in CONFLUENCE_DIR.glob("*.md"):
        with open(md) as f:
            for line in f:
                m = re.search(r'!embed\[.*?\]\((https://www\.loom\.com/share/\w+)\)', line)
                if m:
                    urls.add(m.group(1))
    return urls

def main():
    url_to_title = parse_loom_library(LOOM_LIBRARY)
    needed_urls = get_loom_urls_from_confluence()
    vtt_files = [f.name for f in TRANSCRIPTS_DIR.iterdir() if f.suffix == '.vtt']
    
    result = {}
    missing_title = []
    missing_vtt = []
    
    for url in sorted(needed_urls):
        title = url_to_title.get(url)
        if not title:
            missing_title.append(url)
            continue
        
        vtt_name = find_vtt(title, vtt_files)
        if not vtt_name:
            missing_vtt.append((url, title))
            continue
        
        text = extract_vtt_text(TRANSCRIPTS_DIR / vtt_name)
        result[url] = {
            "title": title,
            "vtt_file": vtt_name,
            "text_preview": text
        }
    
    # Output
    output = {
        "transcripts": result,
        "missing_title": missing_title,
        "missing_vtt": missing_vtt,
        "stats": {
            "total_needed": len(needed_urls),
            "found": len(result),
            "missing_title": len(missing_title),
            "missing_vtt": len(missing_vtt)
        }
    }
    
    out_path = PROJ / "scripts" / "transcript-data.json"
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Stats: {output['stats']}")
    if missing_title:
        print(f"\nMissing title mapping: {missing_title}")
    if missing_vtt:
        print(f"\nMissing VTT files:")
        for url, title in missing_vtt:
            print(f"  {title} → (no VTT found)")

if __name__ == "__main__":
    main()
