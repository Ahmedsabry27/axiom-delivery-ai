#!/usr/bin/env bash
set -euo pipefail

base_dir="$(cd "$(dirname "$0")/.." && pwd)"
svg_dir="$base_dir/svg"
png_dir="$base_dir/png"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
mkdir -p "$png_dir"

for svg in "$svg_dir"/*.svg; do
  dimensions="$(sed -n 's/.*<svg[^>]*width="\([0-9][0-9]*\)"[^>]*height="\([0-9][0-9]*\)".*/\1 \2/p' "$svg" | head -1)"
  read -r width height <<< "$dimensions"
  qlmanage -t -s "$width" -o "$tmp_dir" "$svg" >/dev/null
  rendered="$tmp_dir/$(basename "$svg").png"
  output="$png_dir/$(basename "${svg%.svg}").png"
  sips -c "$height" "$width" --cropOffset 0 0 "$rendered" --out "$output" >/dev/null
  echo "$(basename "$output"): ${width}x${height}"
done
