Output docs/assets/cast/demo.gif

# Regenerate with: make demo-gif
#
# Use the make target, not bare `vhs`: the raw recording is ~1.7MB, over the
# pre-commit asset ceiling, and scripts/record-demo-gif.sh does the palette
# re-encode that brings it under budget.
#
# Keep this tape in step with scripts/demo.sh. It used to show a CUSTOMER token
# creating a user via POST /v1/user, and kept asserting that success long after
# #199/#218 moved those routes to the admin JWT realm — the recording outlived
# the API it depicted by two months.

Set FontSize 13
Set Width 1200
Set Height 640
Set Theme "Dracula"
# Size budget: the pre-commit check-added-large-files hook caps assets at
# 1300KB and asks non-font assets to stay well under it.
#
# What actually controls the size is RUNNING TIME, and running time here is
# mostly the typing animation — this tape types well over a thousand characters
# of curl payload. `Set Framerate` does not help: VHS emits ~25fps regardless,
# so 24 and 12 produce near-identical files. If the GIF grows past budget, cut
# TypingSpeed or Sleep values, not the framerate.
Set Framerate 24
Set TypingSpeed 12ms
Set PlaybackSpeed 1

Require make
Require curl
Require python3

# ── Reset (hidden) ───────────────────────────────────────────────────────────
# Not decoration: without a fresh database the register call below fails with
# USER_ALREADY_EXISTS and the recording bakes in an error. Keeping the reset in
# the tape rather than in a human's shell history is what makes re-recording
# reproducible.
Hide
Type "pkill -f run_server_local.py 2>/dev/null; rm -f quickstart.db; clear"
Enter
Sleep 2s
Show

# ── Quickstart server (background) ───────────────────────────────────────────
Type "make quickstart > /tmp/qs.log 2>&1 &"
Enter
Type "echo 'Waiting for server...'"
Enter
Sleep 6s

# ── Health check ─────────────────────────────────────────────────────────────
Type "curl -sS http://127.0.0.1:8001/health | python3 -m json.tool"
Enter
Sleep 1500ms

# ── Register + obtain JWT ─────────────────────────────────────────────────────
Type `RESP=$(curl -sS -X POST http://127.0.0.1:8001/v1/auth/register \`
Enter
Type `  -H 'Content-Type: application/json' \`
Enter
Type `  -d '{"username":"alice","full_name":"Alice Liddell","email":"alice@example.com","password":"secret123"}')`
Enter
Sleep 500ms
# Truncated on purpose. The two JWTs are ~350 base64 chars each; printed in
# full they wrap into a wall of high-entropy glyphs that roughly doubles the
# GIF, and they tell the reader nothing. `cut` keeps the envelope shape and the
# user object, which is the part worth seeing.
Type "echo $RESP | python3 -m json.tool | cut -c1-100"
Enter
Sleep 1500ms
Type `TOKEN=$(echo $RESP | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['accessToken'])")`
Enter
Sleep 300ms

# ── Admin realm — /v1/user* needs an admin token, not the customer one ───────
# The customer token above is refused by require_admin (#199/#218), and the
# quickstart bootstrap admin cannot stand in for it either. scripts/demo.sh
# seeds a real admin the way the NiceGUI setup wizard would; mirror that here.
Type "uv run python scripts/seed_demo_admin.py --env quickstart --username demoadmin --secret demoadmin123"
Enter
Sleep 3s

Type `ADMIN=$(curl -sS -X POST http://127.0.0.1:8001/v1/admin/login \`
Enter
Type `  -H 'Content-Type: application/json' \`
Enter
Type `  -d '{"username":"demoadmin","password":"demoadmin123"}' \`
Enter
Type `  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['accessToken'])")`
Enter
Sleep 800ms

# ── Create a user (admin-realm protected) ────────────────────────────────────
Type `curl -sS -X POST http://127.0.0.1:8001/v1/user \`
Enter
Type `  -H "Content-Type: application/json" -H "Authorization: Bearer $ADMIN" \`
Enter
Type `  -d '{"username":"bob","full_name":"Bob Builder","email":"bob@example.com","password":"secret456"}' \`
Enter
Type "  | python3 -m json.tool"
Enter
Sleep 1500ms

# ── List users ────────────────────────────────────────────────────────────────
Type `curl -sS "http://127.0.0.1:8001/v1/users?page=1&pageSize=10" \`
Enter
Type `  -H "Authorization: Bearer $ADMIN" | python3 -m json.tool`
Enter
Sleep 1500ms

# ── Teardown ──────────────────────────────────────────────────────────────────
Type "kill %1 2>/dev/null; echo 'Done. API docs: http://127.0.0.1:8001/docs'"
Enter
Sleep 1s
