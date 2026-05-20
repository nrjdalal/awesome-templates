Output docs/assets/cast/new-domain.gif

Set FontSize 13
Set Width 1400
Set Height 700
Set Theme "Dracula"
Set Framerate 24
Set TypingSpeed 40ms
Set PlaybackSpeed 1

# ── Context ────────────────────────────────────────────────────────────────────
# Run from the project root (fastapi-agent-blueprint/).
# This tape demonstrates what /new-domain scaffolds:
# - The src/order/ domain (44 files) is already present from a prior /new-domain run
# - We show the before-state of src/, then the scaffolded file tree, then tests
#
# Record with:
#   VHS_CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
#   vhs docs/assets/cast/new-domain.tape
# ──────────────────────────────────────────────────────────────────────────────

Require find
Require uv

# ── Show current src/ layout (before scaffold) ────────────────────────────────
Type "ls src/"
Enter
Sleep 1500ms

# ── Invoke /new-domain ────────────────────────────────────────────────────────
Type "# /new-domain order  →  one command scaffolds 44 files"
Enter
Sleep 500ms

# ── Show scaffolded file count ────────────────────────────────────────────────
Type `find src/order -type f -name "*.py" | wc -l`
Enter
Sleep 1000ms

# ── Show the file tree ────────────────────────────────────────────────────────
Type `find src/order -name "*.py" | grep -v __pycache__ | sort`
Enter
Sleep 3s

# ── Run unit + integration + e2e tests ────────────────────────────────────────
Type "uv run pytest tests/unit/order/ tests/integration/order/ tests/e2e/order/ -q --tb=no 2>&1 | tail -5"
Enter
Sleep 15s

Type "# Domain scaffold complete — add your business logic to src/order/domain/"
Enter
Sleep 1s
