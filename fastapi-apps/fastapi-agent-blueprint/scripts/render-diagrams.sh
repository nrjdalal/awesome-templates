#!/usr/bin/env bash
# ------------------------------------------------------------------
# Render every Mermaid block inside `docs/ai/shared/architecture-diagrams.md`
# to an SVG file under `docs/assets/architecture/`.
#
# Intent:
# - `architecture-diagrams.md` stays the single maintained source
#   (GitHub renders it natively).
# - SVG copies let non-Mermaid clients (Claude Code CLI, Codex CLI,
#   plain terminals) display the same diagrams as images.
#
# Usage:
#   make diagrams              # recommended
#   bash scripts/render-diagrams.sh    # direct
#
# Requires `npx` (ships with Node) — mmdc is fetched on demand.
# ------------------------------------------------------------------

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="${ROOT}/docs/ai/shared/architecture-diagrams.md"
OUT_DIR="${ROOT}/docs/assets/architecture"
TMP_DIR="$(mktemp -d -t mmd-render.XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

if [ ! -f "${SOURCE}" ]; then
  echo "Source not found: ${SOURCE}" >&2
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "npx not found. Install Node.js first (https://nodejs.org)." >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

# Extract Mermaid blocks in order, tagged by the nearest preceding "## N."
# or "### ..." heading so files get stable, human-readable names.
awk -v tmp="${TMP_DIR}" '
  BEGIN { slug="unknown"; subhead=""; idx=0 }
  /^## +[0-9]+\. +/ {
    s=tolower($0)
    gsub(/^## +[0-9]+\. +/, "", s)
    gsub(/[^a-z0-9]+/, "-", s)
    gsub(/^-|-$/, "", s)
    slug=s; subhead=""; next
  }
  /^### +/ {
    s=tolower($0)
    gsub(/^### +/, "", s)
    gsub(/[^a-z0-9]+/, "-", s)
    gsub(/^-|-$/, "", s)
    subhead=s; next
  }
  /^```mermaid$/ {
    capture=1; idx++
    # Prefer the subhead when present (shorter, scoped); fall back to
    # the section slug so every block still gets a stable filename.
    name=(subhead != "" ? subhead : slug)
    out=sprintf("%s/%02d-%s.mmd", tmp, idx, name)
    next
  }
  /^```$/ && capture { capture=0; subhead=""; next }
  capture { print > out }
' "${SOURCE}"

shopt -s nullglob
blocks=("${TMP_DIR}"/*.mmd)
if [ ${#blocks[@]} -eq 0 ]; then
  echo "No Mermaid blocks found in ${SOURCE}" >&2
  exit 1
fi

# Render each block to SVG via mmdc (fetched via npx on first run).
# Use a puppeteer config that works under Docker/CI if ever needed.
printf '{"args":["--no-sandbox"]}\n' > "${TMP_DIR}/puppeteer.json"

for src in "${blocks[@]}"; do
  name="$(basename "${src}" .mmd)"
  out="${OUT_DIR}/${name}.svg"
  printf '→ %s → %s\n' "${name}.mmd" "docs/assets/architecture/${name}.svg"
  npx --yes -p @mermaid-js/mermaid-cli@11 mmdc \
    -i "${src}" \
    -o "${out}" \
    -b transparent \
    -p "${TMP_DIR}/puppeteer.json" \
    -q
done

printf '\nRendered %d diagram(s) to %s\n' "${#blocks[@]}" "docs/assets/architecture/"
