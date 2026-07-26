#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$repo_root/assets/plantuml"
output_dir="$repo_root/static/diagrams"

mkdir -p "$output_dir"

diagrams=()
while IFS= read -r -d '' source; do
  diagrams+=("$source")
done < <(find "$source_dir" -type f -name '*.puml' -print0 | sort -z)

if [ "${#diagrams[@]}" -eq 0 ]; then
  echo "No PlantUML sources found in $source_dir"
  exit 0
fi

for source in "${diagrams[@]}"; do
  relative="${source#"$source_dir"/}"
  target_dir="$output_dir/$(dirname "$relative")"
  mkdir -p "$target_dir"
  plantuml -tsvg -o "$target_dir" "$source"
done
