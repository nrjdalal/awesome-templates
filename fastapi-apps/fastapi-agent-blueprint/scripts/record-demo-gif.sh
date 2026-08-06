#!/usr/bin/env bash
# ------------------------------------------------------------------
# Record `docs/assets/cast/demo.gif` from `docs/assets/cast/demo.tape`.
#
# Intent:
# - `demo.tape` stays the single maintained source; the committed GIF is
#   a build artefact of it. The previous GIF went stale for months because
#   re-recording was an undocumented two-tool ritual nobody repeated.
#
# Why this is not just `vhs demo.tape`:
#   VHS output for this flow lands around 1.9MB, over the 1300KB ceiling
#   enforced by the check-added-large-files pre-commit hook. A terminal
#   recording needs very few colours, so a palette re-encode cuts it to
#   roughly half with no legibility loss. `Set Framerate` in the tape does
#   NOT help — VHS emits ~25fps regardless — which is why the fps reduction
#   happens here instead.
#
# Usage:
#   make demo-gif                        # recommended
#   bash scripts/record-demo-gif.sh      # direct
#
# Requires `vhs` (brew install vhs — pulls ttyd) and `ffmpeg`.
# Port 8001 must be free: the tape boots its own quickstart server and
# resets ./quickstart.db, so do not run this while `make quickstart` is up.
# ------------------------------------------------------------------

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAPE="${ROOT}/docs/assets/cast/demo.tape"
GIF="${ROOT}/docs/assets/cast/demo.gif"

# Keep in step with `check-added-large-files --maxkb` in
# .pre-commit-config.yaml. The hook asks non-font assets to stay well under
# its 1300KB ceiling, so this budget is deliberately tighter.
MAX_KB=1100

# Palette re-encode settings. Raise COLORS before WIDTH if text ever looks
# rough; 16 is comfortable for a themed terminal at this font size.
FPS=10
COLORS=16
WIDTH=1200

for dep in vhs ffmpeg; do
  if ! command -v "${dep}" >/dev/null 2>&1; then
    echo "${dep} is required but not installed." >&2
    echo "  macOS: brew install ${dep}" >&2
    exit 1
  fi
done

[ -f "${TAPE}" ] || { echo "Tape not found: ${TAPE}" >&2; exit 1; }

if curl -sf http://127.0.0.1:8001/health >/dev/null 2>&1; then
  echo "Something is already serving 127.0.0.1:8001." >&2
  echo "The tape starts its own quickstart server — stop that one first." >&2
  exit 1
fi

TMP_DIR="$(mktemp -d -t demo-gif.XXXXXX)"
trap 'rm -rf "${TMP_DIR}"' EXIT

echo "→ Recording ${TAPE}"
( cd "${ROOT}" && vhs "${TAPE}" )

RAW_KB=$(( $(wc -c < "${GIF}") / 1024 ))
echo "→ Raw recording: ${RAW_KB} KB"

echo "→ Re-encoding (fps=${FPS}, colors=${COLORS}, width=${WIDTH})"
FILTERS="fps=${FPS},scale=${WIDTH}:-1:flags=lanczos"
ffmpeg -v error -i "${GIF}" \
  -vf "${FILTERS},palettegen=max_colors=${COLORS}" \
  -y "${TMP_DIR}/palette.png"
ffmpeg -v error -i "${GIF}" -i "${TMP_DIR}/palette.png" \
  -lavfi "${FILTERS}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5" \
  -y "${TMP_DIR}/optimized.gif"

mv "${TMP_DIR}/optimized.gif" "${GIF}"
FINAL_KB=$(( $(wc -c < "${GIF}") / 1024 ))

if [ "${FINAL_KB}" -gt "${MAX_KB}" ]; then
  echo "" >&2
  echo "${GIF} is ${FINAL_KB} KB, over the ${MAX_KB} KB budget." >&2
  echo "Trim Sleep values in the tape, or lower COLORS / WIDTH here." >&2
  echo "Do not just raise MAX_KB: the pre-commit hook rejects at 1300 KB." >&2
  exit 1
fi

echo "→ Done: ${GIF} (${FINAL_KB} KB, budget ${MAX_KB} KB)"
