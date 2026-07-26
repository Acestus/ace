---
name: video-copy
description: 'Sync downloaded videos from eleanor (~/Downloads or mounted Infuse web folder) to violet media server (/media/kids-access/family-movies/youtube/) while keeping the eleanor/source copy. Use when the user says "sync the infuse files", "copy videos from eleanor", "send the kids videos to the media server", or references syncing downloaded YouTube videos from eleanor.'
argument-hint: 'Optionally specify filenames or source folder; defaults to video files in eleanor Downloads and /media/acestus/INFUSE/infuse01/web'
---

# Video Copy Skill

Sync (copy + verify, preserving the source) video files from Eleanor to
`violet`'s kids media library. See `TOOLS.md` for host/credential notes.

## When to Use

- User says "sync the Infuse files", "copy videos from eleanor",
  "send the kids' videos to the media server"
- Downloaded kids' YouTube/Infuse content should exist on both Eleanor and
  Violet

## Script

The original PowerShell helper from Eleanor is checked in at:

- `scripts/copy-to-violet.ps1`

It is also mirrored in Scout's local OpenClaw skill folder:

- `/Users/scout/.openclaw/main/skills/video-copy/scripts/copy-to-violet.ps1`

As of 2026-07-24, neither Scout nor Eleanor has `pwsh` installed, so use the
same safe rsync/SSH behavior from this skill unless PowerShell is available.
Do not use the script's old defaults blindly: it points at the older
`/media/violet/movies01` layout.

## Hosts

| Host | User | Role |
|------|------|------|
| `eleanor` | `acestus` | source — `~/Downloads` and `/media/acestus/INFUSE/infuse01/web/` |
| `violet` | `violet` | destination — `/media/kids-access/family-movies/youtube/` |

Current YouTube channel folders on Violet:

- `Campfire Saint Stories`
- `Catholic Kids`
- `Homeschool & Skills`
- `NFL Films & Football History`

Both accept this box's SSH key already (see `TOOLS.md`). If a connection is
ever rejected, the key may have been rotated — ask the user for host/user/
password before touching authorized_keys again.

## Workflow

### Step 1 — Find video files on Eleanor

```bash
ssh acestus@eleanor "find ~/Downloads -maxdepth 1 -type f \
  \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' \
     -o -iname '*.avi' -o -iname '*.webm' -o -iname '*.m4v' \) \
  -exec ls -la {} +"
```

Also check the mounted Infuse web folder:

```bash
ssh acestus@eleanor "find /media/acestus/INFUSE/infuse01/web -maxdepth 1 -type f \
  \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' \
     -o -iname '*.avi' -o -iname '*.webm' -o -iname '*.m4v' \) \
  -exec ls -la {} +"
```

If neither source has matching files, report that and stop.

### Step 2 — Confirm destination exists

```bash
ssh violet@violet "ls -ld /media/kids-access/family-movies/youtube/"
```

### Step 3 — Copy files without deleting the source

Direct eleanor→violet SCP may not be authorized between those two hosts, so
relay through scout:

```bash
scp -3 -o BatchMode=yes \
  "acestus@eleanor:~/Downloads/<FILENAME>" \
  "violet@violet:/media/kids-access/family-movies/youtube/<FILENAME>"
```

Quote filenames — they often contain spaces/punctuation (emoji, `!`, `&`).

For the mounted Infuse web folder, prefer rsync when possible:

```bash
ssh acestus@eleanor "rsync -rlptvh --progress --partial --ignore-existing \
  --exclude='.DS_Store' --exclude='Thumbs.db' --exclude='desktop.ini' \
  /media/acestus/INFUSE/infuse01/web/ \
  violet@violet:/media/kids-access/family-movies/youtube/"
```

After syncing, organize any loose files in `youtube/` into the channel folders
above. This is the server-side Infuse-friendly layout; Infuse native
Collections are app Library objects and must be created inside Infuse itself.

### Step 4 — Verify integrity

```bash
ssh acestus@eleanor "cd ~/Downloads && sha256sum '<FILENAME>'"
ssh acestus@eleanor "cd /media/acestus/INFUSE/infuse01/web && sha256sum '<FILENAME>'"
ssh violet@violet "cd /media/kids-access/family-movies/youtube && sha256sum '<FILENAME>'"
```

Compare hashes for every file. If any mismatch, do not delete that file —
re-copy and re-check instead.

### Step 5 — Report

List what synced (name + size), confirm both Eleanor and Violet retain matching
copies, and flag anything skipped due to checksum mismatch.

## Rules

1. **Never delete the source copy from Eleanor.** This workflow is a sync, not
   a move.
2. If `~/Downloads` contains non-video files, leave them alone — only touch
   video extensions.
3. If the destination directory is missing or unwritable, stop and report;
   do not create arbitrary directory structures under `/media/kids-access/`.
4. Keep this skill short and maintainable (<200 lines).
