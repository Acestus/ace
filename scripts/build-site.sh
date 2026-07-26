#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$repo_root/scripts/render-plantuml.sh"
(cd "$repo_root/web" && bun run build)
hugo --source "$repo_root"
