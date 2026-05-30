#!/usr/bin/env python3
"""
Publish a Markdown file to a Confluence Live Doc as ADF (Atlassian Document Format).

Usage:
    python3 publish-markdown-to-confluence.py <page_id> <markdown_file> [--message "Update message"]

Reads CONFLUENCE_EMAIL and WWEEKS_CONFLUENCE_API_TOKEN from ../../.env or .env
"""

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import zlib
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).parent))
from lib.errors import fail, require_env, http_fail, CONFLUENCE_COMMON_CAUSES

SITE_URL = "https://<YOUR_ATLASSIAN>.atlassian.net/wiki"


def load_env():
    """Load credentials from .env file."""
    for env_path in [Path(__file__).parent / "../.env", Path(__file__).parent / ".env"]:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
            break


def _get_credentials():
    """Return base64-encoded credentials for Confluence API."""
    require_env(
        "CONFLUENCE_EMAIL", "WWEEKS_CONFLUENCE_API_TOKEN",
        hint="Add them to .env at the repo root",
        env_file=str(Path(__file__).parent.parent / ".env"),
    )
    email = os.environ["CONFLUENCE_EMAIL"]
    token = os.environ["WWEEKS_CONFLUENCE_API_TOKEN"]
    return base64.b64encode(f"{email}:{token}".encode()).decode()


def api_request(method, path, data=None):
    """Make an authenticated Confluence API v2 request."""
    credentials = _get_credentials()
    url = f"{SITE_URL}/api/v2/{path}"
    headers = {
        "Authorization": f"Basic {credentials}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        http_fail(e, api_name="Confluence", key=path, operation=f"{method} {path}",
                  common_causes=CONFLUENCE_COMMON_CAUSES)


def api_request_v1(method, path, data=None):
    """Make an authenticated Confluence API v1 request (labels, attachments)."""
    credentials = _get_credentials()
    url = f"{SITE_URL}/rest/api/{path}"
    headers = {
        "Authorization": f"Basic {credentials}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            resp_data = resp.read().decode()
            return json.loads(resp_data) if resp_data.strip() else {}
    except HTTPError as e:
        http_fail(e, api_name="Confluence v1", key=path, operation=f"{method} {path}",
                  common_causes=CONFLUENCE_COMMON_CAUSES)


# ── PlantUML rendering ─────────────────────────────────────────────────────────

# PlantUML text encoding (deflate + custom base64 for URL)
_PLANTUML_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"


def _plantuml_encode(text):
    """Encode PlantUML source for the public server URL."""
    compressed = zlib.compress(text.encode("utf-8"))[2:-4]  # raw deflate (strip zlib header/checksum)
    encoded = []
    for i in range(0, len(compressed), 3):
        chunk = compressed[i:i + 3]
        if len(chunk) == 3:
            b0, b1, b2 = chunk
            encoded.append(_PLANTUML_ALPHABET[b0 >> 2])
            encoded.append(_PLANTUML_ALPHABET[((b0 & 0x3) << 4) | (b1 >> 4)])
            encoded.append(_PLANTUML_ALPHABET[((b1 & 0xF) << 2) | (b2 >> 6)])
            encoded.append(_PLANTUML_ALPHABET[b2 & 0x3F])
        elif len(chunk) == 2:
            b0, b1 = chunk
            encoded.append(_PLANTUML_ALPHABET[b0 >> 2])
            encoded.append(_PLANTUML_ALPHABET[((b0 & 0x3) << 4) | (b1 >> 4)])
            encoded.append(_PLANTUML_ALPHABET[(b1 & 0xF) << 2])
            encoded.append(_PLANTUML_ALPHABET[0])
        elif len(chunk) == 1:
            b0 = chunk[0]
            encoded.append(_PLANTUML_ALPHABET[b0 >> 2])
            encoded.append(_PLANTUML_ALPHABET[(b0 & 0x3) << 4])
            encoded.append(_PLANTUML_ALPHABET[0])
            encoded.append(_PLANTUML_ALPHABET[0])
    return "".join(encoded)


def render_plantuml_png(puml_source):
    """Render PlantUML source to PNG bytes. Tries local CLI first, falls back to public server."""
    # Try local plantuml CLI (needs Java)
    try:
        result = subprocess.run(
            ["plantuml", "-tpng", "-pipe"],
            input=puml_source.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
        # Exit 200 = PlantUML rendered with minor syntax warnings (e.g. pie charts) —
        # accept if stdout contains PNG data (starts with PNG magic bytes)
        if result.returncode == 200 and result.stdout and result.stdout[:4] == b'\x89PNG':
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fall back to public PlantUML server
    encoded = _plantuml_encode(puml_source)
    url = f"https://www.plantuml.com/plantuml/png/{encoded}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        fail(
            f"Failed to render PlantUML diagram: {e}",
            causes=["plantuml binary returned a non-zero exit code",
                    "The public PlantUML server at plantuml.com returned an error",
                    "The .puml source contains invalid PlantUML syntax"],
            try_=["plantuml --version  # verify local binary is installed",
                  "Validate syntax at https://www.plantuml.com/plantuml/uml/"],
        )


def upload_attachment(page_id, filename, data, content_type="image/png"):
    """Upload a file as a Confluence page attachment (v1 API). Returns the attachment fileId."""
    credentials = _get_credentials()
    url = f"{SITE_URL}/rest/api/content/{page_id}/child/attachment"

    boundary = "----PythonBoundary"
    body_parts = []
    body_parts.append(f"--{boundary}".encode())
    body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode())
    body_parts.append(f"Content-Type: {content_type}".encode())
    body_parts.append(b"")
    body_parts.append(data)
    body_parts.append(f"--{boundary}--".encode())
    body = b"\r\n".join(body_parts)

    headers = {
        "Authorization": f"Basic {credentials}",
        "Accept": "application/json",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "X-Atlassian-Token": "nocheck",
    }

    req = Request(url, data=body, headers=headers, method="PUT")
    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read().decode())
    except HTTPError as e:
        http_fail(e, api_name="Confluence (attachment upload)", key=f"{page_id}/child/attachment",
                  operation=f"PUT {page_id}/child/attachment",
                  common_causes=CONFLUENCE_COMMON_CAUSES)

    # Extract the fileId from the response
    results = result.get("results", [result] if "id" in result else [])
    if not results:
        fail(
            "Confluence attachment upload succeeded but returned no attachment record",
            causes=["The Confluence API response did not include a 'results' array",
                    "The attachment may have been created under a different structure"],
            try_=[f"Check the page attachments in Confluence: {SITE_URL}/pages/{page_id}"],
        )
    att = results[0]
    file_id = att.get("extensions", {}).get("fileId", att.get("id", ""))
    return file_id


def media_single_node(file_id, page_id, width=50):
    """Create an ADF mediaSingle node for an inline image attachment."""
    return {
        "type": "mediaSingle",
        "attrs": {"layout": "center", "width": width},
        "content": [{
            "type": "media",
            "attrs": {
                "type": "file",
                "id": file_id,
                "collection": f"contentId-{page_id}",
            },
        }],
    }


# ── Markdown → ADF conversion ──────────────────────────────────────────────────


def text_node(text, marks=None):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


# Valid status lozenge colors in ADF
_STATUS_COLORS = {"neutral", "blue", "purple", "yellow", "red", "green"}
_STATUS_COUNTER = 0


def status_node(label, color="neutral"):
    """Create an ADF status (lozenge) node — colored inline badge."""
    global _STATUS_COUNTER
    _STATUS_COUNTER += 1
    if color not in _STATUS_COLORS:
        color = "neutral"
    return {
        "type": "status",
        "attrs": {
            "text": label,
            "color": color,
            "localId": f"status-{_STATUS_COUNTER}",
            "style": "",
        },
    }


# Patterns for embeddable video URLs
_VIDEO_URL_RE = re.compile(
    r'^https?://(?:www\.)?(?:'
    r'youtube\.com/watch\?v=[\w-]+'
    r'|youtu\.be/[\w-]+'
    r'|loom\.com/share/[\w-]+'
    r')(?:\S*)$'
)

# YouTube and Loom URLs use the widget macro (renders embedded video player).
# Requires the Loom Marketplace app to be installed for Loom URLs.


def widget_extension(url):
    """Create an ADF extension node for the Confluence widget macro (embeds video)."""
    return {
        "type": "extension",
        "attrs": {
            "extensionType": "com.atlassian.confluence.macro.core",
            "extensionKey": "widget",
            "parameters": {
                "macroParams": {
                    "url": {"value": url}
                }
            },
            "layout": "default",
        },
    }


def _extract_video_url(line):
    """If the line is solely a video URL (bare or as [text](url)), return the URL; else None."""
    stripped = line.strip()
    # bare URL
    if _VIDEO_URL_RE.match(stripped):
        return stripped
    # markdown link where text == url or text is display label
    m = re.match(r'^\[([^\]]*)\]\(([^)]+)\)$', stripped)
    if m and _VIDEO_URL_RE.match(m.group(2)):
        return m.group(2)
    return None


def embed_card(url):
    """Create an ADF embedCard node (full interactive embed — video player, preview)."""
    return {
        "type": "embedCard",
        "attrs": {
            "url": url,
            "layout": "wide",
        },
    }


def block_card(url):
    """Create an ADF blockCard node (rich preview card — title, description, thumbnail)."""
    return {
        "type": "blockCard",
        "attrs": {
            "url": url,
        },
    }


def _parse_embed_directive(line):
    """Parse !embed[label](url) or !embed url directives. Returns (type, url) or None."""
    stripped = line.strip()
    # !embed[label](url)
    m = re.match(r'^!embed\[([^\]]*)\]\(([^)]+)\)$', stripped)
    if m:
        return ("embed", m.group(2))
    # !embed url
    m = re.match(r'^!embed\s+(https?://\S+)$', stripped)
    if m:
        return ("embed", m.group(1))
    # !card[label](url)
    m = re.match(r'^!card\[([^\]]*)\]\(([^)]+)\)$', stripped)
    if m:
        return ("card", m.group(2))
    # !card url
    m = re.match(r'^!card\s+(https?://\S+)$', stripped)
    if m:
        return ("card", m.group(1))
    return None


def parse_inline(text):
    """Parse inline markdown (bold, italic, code, links, status lozenges) into ADF nodes."""
    nodes = []
    # Pattern handles: !status[text](color), [text](url), **bold**, *italic*, `code`
    pattern = re.compile(
        r'(!status\[([^\]]+)\]\(([^)]+)\))'  # !status[text](color)
        r'|(\[([^\]]+)\]\(([^)]+)\))'         # [text](url)
        r'|(\*\*(.+?)\*\*)'                    # **bold**
        r'|(\*(.+?)\*)'                        # *italic*
        r'|(`(.+?)`)'                          # `code`
    )

    pos = 0
    for m in pattern.finditer(text):
        # plain text before this match
        if m.start() > pos:
            nodes.append(text_node(text[pos:m.start()]))

        if m.group(2) is not None:  # !status[text](color)
            nodes.append(status_node(m.group(2), m.group(3).strip()))
        elif m.group(5) is not None:  # link
            nodes.append(text_node(m.group(5), [{"type": "link", "attrs": {"href": m.group(6)}}]))
        elif m.group(8) is not None:  # bold
            nodes.append(text_node(m.group(8), [{"type": "strong"}]))
        elif m.group(10) is not None:  # italic
            nodes.append(text_node(m.group(10), [{"type": "em"}]))
        elif m.group(12) is not None:  # code
            nodes.append(text_node(m.group(12), [{"type": "code"}]))

        pos = m.end()

    # trailing plain text
    if pos < len(text):
        nodes.append(text_node(text[pos:]))

    return nodes if nodes else [text_node(text)]


def paragraph(text):
    content = parse_inline(text)
    return {"type": "paragraph", "content": content}


def heading(level, text):
    content = parse_inline(text)
    return {"type": "heading", "attrs": {"level": level}, "content": content}


def md_to_adf(markdown_text, attachments=None):
    """Convert markdown text to ADF document structure.

    Args:
        markdown_text: Markdown body text (without frontmatter).
        attachments: Optional dict mapping puml paths to {"file_id": ..., "page_id": ...}
    """
    if attachments is None:
        attachments = {}
    lines = markdown_text.split("\n")
    doc_content = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # blank line — skip
        if not line.strip():
            i += 1
            continue

        # heading
        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            level = len(heading_match.group(1))
            doc_content.append(heading(level, heading_match.group(2).strip()))
            i += 1
            continue

        # horizontal rule
        if re.match(r'^---+\s*$', line):
            doc_content.append({"type": "rule"})
            i += 1
            continue

        # fenced code block
        code_match = re.match(r'^```(\w*)$', line)
        if code_match:
            lang = code_match.group(1)
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            code_node = {"type": "codeBlock", "content": [text_node("\n".join(code_lines))]}
            if lang:
                code_node["attrs"] = {"language": lang}
            doc_content.append(code_node)
            continue

        # table
        if line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            doc_content.append(parse_table(table_lines))
            continue

        # unordered list
        if re.match(r'^- ', line):
            items = []
            while i < len(lines) and re.match(r'^- ', lines[i]):
                item_text = lines[i][2:].strip()
                items.append({
                    "type": "listItem",
                    "content": [paragraph(item_text)]
                })
                i += 1
            doc_content.append({"type": "bulletList", "content": items})
            continue

        # ordered list
        ol_match = re.match(r'^(\d+)\.\s+', line)
        if ol_match:
            items = []
            while i < len(lines) and re.match(r'^\d+\.\s+', lines[i]):
                item_text = re.sub(r'^\d+\.\s+', '', lines[i]).strip()
                items.append({
                    "type": "listItem",
                    "content": [paragraph(item_text)]
                })
                i += 1
            doc_content.append({"type": "orderedList", "attrs": {"order": 1}, "content": items})
            continue

        # !panel block — collects lines until next blank line into a panel node
        if line.strip() == '!panel' or re.match(r'^!panel\(([^)]+)\)$', line.strip()):
            panel_match = re.match(r'^!panel\(([^)]+)\)$', line.strip())
            panel_type = panel_match.group(1) if panel_match else 'info'
            if panel_type not in ('info', 'note', 'warning', 'error', 'success', 'tip'):
                panel_type = 'info'
            i += 1
            panel_content = []
            while i < len(lines) and lines[i].strip():
                panel_content.append(paragraph(lines[i].strip()))
                i += 1
            if panel_content:
                doc_content.append({
                    "type": "panel",
                    "attrs": {"panelType": panel_type},
                    "content": panel_content,
                })
            continue

        # !plantuml(path) directive — rendered SVG uploaded as attachment
        plantuml_match = re.match(r'^!plantuml\(([^)]+)\)$', line.strip())
        if plantuml_match:
            puml_path = plantuml_match.group(1).strip()
            att_info = attachments.get(puml_path)
            if att_info:
                doc_content.append(media_single_node(att_info["file_id"], att_info["page_id"]))
            else:
                # Fallback: show as a note that the diagram wasn't rendered
                doc_content.append(paragraph(f"[PlantUML diagram: {puml_path} — not rendered]"))
            i += 1
            continue

        # !image(path) directive — static image uploaded as attachment
        image_match = re.match(r'^!image\(([^)]+)\)$', line.strip())
        if image_match:
            img_path = image_match.group(1).strip()
            att_info = attachments.get(img_path)
            if att_info:
                doc_content.append(media_single_node(att_info["file_id"], att_info["page_id"], width=att_info.get("width", 100)))
            else:
                doc_content.append(paragraph(f"[Image: {img_path} — not uploaded]"))
            i += 1
            continue

        # !embed / !card directives
        embed_result = _parse_embed_directive(line)
        if embed_result:
            etype, eurl = embed_result
            if etype == "embed":
                doc_content.append(embed_card(eurl))
            else:
                doc_content.append(block_card(eurl))
            i += 1
            continue

        # bare video URL (YouTube, Loom) → embedCard (renders as Smart Link player in Live Docs)
        video_url = _extract_video_url(line)
        if video_url:
            doc_content.append(embed_card(video_url))
            i += 1
            continue

        # default: paragraph
        doc_content.append(paragraph(line.strip()))
        i += 1

    return {"version": 1, "type": "doc", "content": doc_content}


def parse_table(table_lines):
    """Parse markdown table lines into ADF table node."""
    rows = []
    for line in table_lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)

    # Remove separator row (the --- row)
    if len(rows) > 1 and all(re.match(r'^-+$', c.strip()) for c in rows[1]):
        rows.pop(1)

    adf_rows = []
    for idx, row in enumerate(rows):
        cell_type = "tableHeader" if idx == 0 else "tableCell"
        adf_cells = []
        for cell_text in row:
            adf_cells.append({
                "type": cell_type,
                "content": [paragraph(cell_text)]
            })
        adf_rows.append({"type": "tableRow", "content": adf_cells})

    return {"type": "table", "content": adf_rows}


# ── Frontmatter parsing ─────────────────────────────────────────────────────────


def parse_frontmatter(text):
    """Parse YAML frontmatter from markdown text. Returns (tags, version, body)."""
    m = re.match(r'^---\r?\n(.+?)\r?\n---\r?\n(.*)', text, re.DOTALL)
    if not m:
        return [], None, text

    frontmatter = m.group(1)
    body = m.group(2)
    tags = []
    version = None
    in_tags = False

    for line in frontmatter.splitlines():
        if re.match(r'^\s*tags:\s*$', line):
            in_tags = True
            continue
        if in_tags:
            tag_match = re.match(r'^\s*-\s+(.+)$', line)
            if tag_match:
                tags.append(tag_match.group(1).strip())
            else:
                in_tags = False
        version_match = re.match(r'^\s*version:\s*(\d+)\s*$', line)
        if version_match:
            version = int(version_match.group(1))

    return tags, version, body


def sync_labels(page_id, tags):
    """Sync frontmatter tags to Confluence page labels."""
    if not tags:
        return

    print(f"🏷️  Syncing {len(tags)} labels...")
    existing = api_request("GET", f"pages/{page_id}/labels")
    existing_names = [r["name"] for r in existing.get("results", [])]

    # Add missing labels (v1 — no v2 write endpoint for labels)
    to_add = [t for t in tags if t not in existing_names]
    if to_add:
        label_data = [{"prefix": "global", "name": t} for t in to_add]
        api_request_v1("POST", f"content/{page_id}/label", label_data)
        print(f"   Added: {', '.join(to_add)}")

    # Remove labels not in frontmatter (v1)
    to_remove = [n for n in existing_names if n not in tags]
    for label in to_remove:
        api_request_v1("DELETE", f"content/{page_id}/label/{label}")
        print(f"   Removed: {label}")

    if not to_add and not to_remove:
        print("   Labels already in sync")


def update_frontmatter_version(md_path, new_version):
    """Update the version field in the file's YAML frontmatter."""
    content = md_path.read_text(encoding="utf-8")
    if re.search(r'(?m)^version:\s*\d+\s*$', content):
        content = re.sub(r'(?m)^version:\s*\d+\s*$', f"version: {new_version}", content)
    elif content.startswith("---\n"):
        content = content.replace("---\n", f"---\nversion: {new_version}\n", 1)
    md_path.write_text(content, encoding="utf-8")
    print(f"📌 Updated local frontmatter to version {new_version}")


# ── Main ────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Upload markdown to Confluence Live Doc")
    parser.add_argument("page_id", help="Confluence page ID")
    parser.add_argument("markdown_file", help="Path to the markdown file")
    parser.add_argument("--message", default="Updated from VSCode", help="Version message")
    parser.add_argument("--dry-run", action="store_true", help="Generate ADF JSON without uploading")
    parser.add_argument("--force", action="store_true", help="Skip conflict detection")
    args = parser.parse_args()

    load_env()

    # Read markdown
    md_path = Path(args.markdown_file)
    if not md_path.exists():
        fail(
            f"Markdown file not found: {md_path}",
            causes=["Path was mistyped or the file was moved"],
            try_=[f"ls confluence/*.md", "Check the path argument"],
        )

    markdown_text = md_path.read_text(encoding="utf-8")
    print(f"📄 Read {len(markdown_text)} chars from {md_path.name}")

    # Parse frontmatter
    tags, local_version, body_text = parse_frontmatter(markdown_text)
    if tags:
        print(f"🏷️  Tags: {', '.join(tags)}")
    if local_version:
        print(f"📌 Local version: {local_version}")
    else:
        print("⚠️  No version in frontmatter — conflict detection disabled")

    # Scan for !plantuml directives and render/upload SVGs as attachments
    plantuml_attachments = {}
    puml_directives = re.findall(r'^!plantuml\(([^)]+)\)$', body_text, re.MULTILINE)
    if puml_directives and not args.dry_run:
        md_dir = md_path.parent
        for puml_rel_path in puml_directives:
            puml_file = (md_dir / puml_rel_path).resolve()
            if not puml_file.exists():
                # Try relative to workspace root
                puml_file = (md_dir.parent / puml_rel_path).resolve()
            if not puml_file.exists():
                print(f"⚠️  PlantUML file not found: {puml_rel_path}", file=sys.stderr)
                continue

            puml_source = puml_file.read_text(encoding="utf-8")
            source_hash = hashlib.sha256(puml_source.encode("utf-8")).hexdigest()
            png_cache_path = puml_file.with_suffix(".png")
            hash_cache_path = puml_file.with_suffix(".sha256")

            # Check if cached PNG matches current source
            if png_cache_path.exists() and hash_cache_path.exists():
                cached_hash = hash_cache_path.read_text(encoding="utf-8").strip()
                if cached_hash == source_hash:
                    print(f"⏩ PlantUML unchanged, using cached PNG: {puml_file.name}")
                    png_data = png_cache_path.read_bytes()
                else:
                    print(f"🌱 Rendering PlantUML (source changed): {puml_file.name}")
                    png_data = render_plantuml_png(puml_source)
                    png_cache_path.write_bytes(png_data)
                    hash_cache_path.write_text(source_hash, encoding="utf-8")
            else:
                print(f"🌱 Rendering PlantUML: {puml_file.name}")
                png_data = render_plantuml_png(puml_source)
                png_cache_path.write_bytes(png_data)
                hash_cache_path.write_text(source_hash, encoding="utf-8")

            png_filename = puml_file.stem + ".png"
            print(f"📎 Uploading attachment: {png_filename} ({len(png_data)} bytes)")
            file_id = upload_attachment(args.page_id, png_filename, png_data)
            plantuml_attachments[puml_rel_path] = {
                "file_id": file_id,
                "page_id": args.page_id,
            }
            print(f"   Attached: {png_filename} (fileId: {file_id})")

    # Scan for !image directives and upload static images as attachments
    image_directives = re.findall(r'^!image\(([^)]+)\)$', body_text, re.MULTILINE)
    if image_directives and not args.dry_run:
        md_dir = md_path.parent
        for img_rel_path in image_directives:
            img_file = (md_dir / img_rel_path).resolve()
            if not img_file.exists():
                # Try relative to workspace root
                img_file = (md_dir.parent / img_rel_path).resolve()
            if not img_file.exists():
                print(f"⚠️  Image file not found: {img_rel_path}", file=sys.stderr)
                continue

            img_data = img_file.read_bytes()
            suffix = img_file.suffix.lower()
            content_type = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }.get(suffix, "image/png")
            img_filename = img_file.name
            print(f"📎 Uploading image: {img_filename} ({len(img_data)} bytes)")
            file_id = upload_attachment(args.page_id, img_filename, img_data, content_type=content_type)
            plantuml_attachments[img_rel_path] = {
                "file_id": file_id,
                "page_id": args.page_id,
            }
            print(f"   Attached: {img_filename} (fileId: {file_id})")

    # Convert body (without frontmatter) to ADF
    adf_doc = md_to_adf(body_text, attachments=plantuml_attachments)
    adf_json = json.dumps(adf_doc, ensure_ascii=False)
    print(f"🔄 Converted to ADF: {len(adf_doc['content'])} top-level nodes")

    if args.dry_run:
        out_path = md_path.with_suffix(".adf-upload.json")
        out_path.write_text(json.dumps(adf_doc, indent=2, ensure_ascii=False))
        print(f"💾 Dry run — saved ADF to {out_path}")
        return

    # Get current page version and body (v2)
    print(f"🔍 Fetching page {args.page_id}...")
    page = api_request("GET", f"pages/{args.page_id}?include-version=true&body-format=atlas_doc_format")
    current_version = page["version"]["number"]
    current_title = page["title"]
    print(f"   Title: {current_title}")
    print(f"   Version: {current_version} (remote)")

    # Skip upload if content is unchanged
    remote_body = page.get("body", {}).get("atlas_doc_format", {}).get("value", "")
    if remote_body:
        try:
            remote_adf = json.loads(remote_body) if isinstance(remote_body, str) else remote_body
            if json.dumps(remote_adf, sort_keys=True) == json.dumps(adf_doc, sort_keys=True):
                print(f"⏩ No content changes — skipping upload")
                # Still sync labels in case tags changed
                sync_labels(args.page_id, tags)
                # Ensure local version matches remote
                if local_version != current_version:
                    update_frontmatter_version(md_path, current_version)
                return
        except (json.JSONDecodeError, TypeError):
            pass  # Can't compare — proceed with upload

    # Conflict detection
    if local_version and local_version != current_version:
        if args.force:
            print(f"⚠️  Version conflict: local={local_version}, remote={current_version}. Proceeding due to --force.")
        else:
            fail(
                f"Version conflict — upload aborted (local={local_version}, remote={current_version})",
                causes=["The Confluence page was edited directly since you last downloaded it",
                        "Another process pushed a newer version"],
                try_=["Re-download: python3 scripts/get-confluence-page.py " + str(args.page_id),
                      "Or force-overwrite: add --force to skip conflict detection"],
            )

    # Upload ADF (v2)
    update_body = {
        "id": str(args.page_id),
        "status": "current",
        "title": current_title,
        "body": {
            "representation": "atlas_doc_format",
            "value": adf_json,
        },
        "version": {
            "number": current_version + 1,
            "message": args.message,
        },
    }

    print(f"🚀 Uploading version {current_version + 1}...")
    result = api_request("PUT", f"pages/{args.page_id}", update_body)
    new_version = result["version"]["number"]
    print(f"✅ Updated to version {new_version}")
    page_url = result.get("_links", {}).get("webui") or result.get("_links", {}).get("base", "")
    if page_url and not page_url.startswith("http"):
        page_url = f"{SITE_URL}{page_url}"
    print(f"   URL: {page_url}")

    # Update local frontmatter version
    update_frontmatter_version(md_path, new_version)

    # Clean up dry-run ADF file if it exists
    adf_path = md_path.with_suffix(".adf-upload.json")
    if adf_path.exists():
        adf_path.unlink()
        print(f"🧹 Removed {adf_path}")

    # Sync labels
    sync_labels(args.page_id, tags)


if __name__ == "__main__":
    main()
