#!/usr/bin/env bash
# SessionStart Hook: Check optional session setup
# stdout is injected into Claude's context as a system message

set -euo pipefail

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
