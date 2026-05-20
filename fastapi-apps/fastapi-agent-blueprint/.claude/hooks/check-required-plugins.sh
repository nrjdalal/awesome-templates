#!/usr/bin/env bash
# SessionStart Hook: Check required plugins are available
# stdout is injected into Claude's context as a system message

set -euo pipefail

if ! command -v pyright-langserver &>/dev/null; then
    echo ""
    echo "=== [WARNING] pyright-langserver not found in PATH ==="
    echo "This project requires pyright-lsp for code intelligence."
    echo ""
    echo "Install steps:"
    echo "  1. uv sync                              # installs pyright binary"
    echo "  2. claude plugin install pyright-lsp     # installs Claude Code plugin"
    echo ""
    echo "Without pyright-lsp, symbol navigation falls back to Grep (less precise, more tokens)."
    echo "======================================================="
fi

if [ -z "${CONTEXT7_API_KEY:-}" ]; then
    echo ""
    echo "=== [INFO] CONTEXT7_API_KEY not set ==="
    echo "context7 works without an API key, but anonymous requests have lower rate limits."
    echo ""
    echo "Get your API key: https://context7.com/dashboard"
    echo "Then set: export CONTEXT7_API_KEY=ctx7sk-xxxx"
    echo "================================================"
fi

exit 0
