---
name: video-copy
description: 'Move downloaded videos from eleanor (~/Downloads) to violet media server (/media/kids-access/family-movies/youtube/). Use when the user says "move the videos", "copy the videos to violet", "send the kids videos to the media server", or references moving downloaded YouTube videos from eleanor.'
argument-hint: 'Optionally specify filenames; defaults to all video files in ~/Downloads on eleanor'
---

# Video Copy Skill

Move (copy + verify + delete source) video files from `eleanor:~/Downloads`
to `violet`'s kids media library. See `TOOLS.md` for host/credential notes.

## When to Use

- User says "move the videos to violet", "copy videos from eleanor",
  "send the kids' videos to the media server"
- Cleanup of `~/Downloads` on eleanor after downloading kids' YouTube content

## Hosts

| Host | User | Role |
|------|------|------|
| `eleanor` | `acestus` | source — `~/Downloads` |
| `violet` | `violet` | destination — `/media/kids-access/family-movies/youtube/` |

Both accept this box's SSH key already (see `TOOLS.md`). If a connection is
ever rejected, the key may have been rotated — ask the user for host/user/
password before touching authorized_keys again.

## Workflow

### Step 1 — Find video files on eleanor

```bash
ssh acestus@eleanor "find ~/Downloads -maxdepth 1 -type f \
  \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' \
     -o -iname '*.avi' -o -iname '*.webm' -o -iname '*.m4v' \) \
  -exec ls -la {} +"
```

If nothing matches, report that and stop.

### Step 2 — Confirm destination exists

```bash
ssh violet@violet "ls -ld /media/kids-access/family-movies/youtube/"
```

### Step 3 — Copy each file (relay through this box with scp -3)

Direct eleanor→violet SCP may not be authorized between those two hosts, so
relay through scout:

```bash
scp -3 -o BatchMode=yes \
  "acestus@eleanor:~/Downloads/<FILENAME>" \
  "violet@violet:/media/kids-access/family-movies/youtube/<FILENAME>"
```

Quote filenames — they often contain spaces/punctuation (emoji, `!`, `&`).

### Step 4 — Verify integrity before deleting source

Never delete from eleanor until checksums match:

```bash
ssh acestus@eleanor "cd ~/Downloads && sha256sum '<FILENAME>'"
ssh violet@violet "cd /media/kids-access/family-movies/youtube && sha256sum '<FILENAME>'"
```

Compare hashes for every file. If any mismatch, do not delete that file —
re-copy and re-check instead.

### Step 5 — Delete verified originals from eleanor

```bash
ssh acestus@eleanor "rm -v ~/Downloads/'<FILENAME>'"
```

### Step 6 — Report

List what moved (name + size), confirm `~/Downloads` is now clear of those
files, and flag anything skipped due to checksum mismatch.

## Rules

1. **Never delete before checksum verification passes.** This is a move, not
   a blind copy — data loss on the source is not acceptable.
2. If `~/Downloads` contains non-video files, leave them alone — only touch
   video extensions.
3. If the destination directory is missing or unwritable, stop and report;
   do not create arbitrary directory structures under `/media/kids-access/`.
4. Keep this skill short and maintainable (<200 lines).
