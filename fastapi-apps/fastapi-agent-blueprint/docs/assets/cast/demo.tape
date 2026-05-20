Output docs/assets/cast/demo.gif

Set FontSize 13
Set Width 1400
Set Height 700
Set Theme "Dracula"
Set Framerate 24
Set TypingSpeed 40ms
Set PlaybackSpeed 1

# ── Quickstart server (background) ───────────────────────────────────────────
Require make
Require curl
Require python3

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
Type "echo $RESP | python3 -m json.tool"
Enter
Sleep 1500ms
Type `TOKEN=$(echo $RESP | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['accessToken'])")`
Enter
Sleep 300ms

# ── Create a user (JWT-protected) ────────────────────────────────────────────
Type `curl -sS -X POST http://127.0.0.1:8001/v1/user \`
Enter
Type `  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \`
Enter
Type `  -d '{"username":"bob","full_name":"Bob Builder","email":"bob@example.com","password":"secret456"}' \`
Enter
Type "  | python3 -m json.tool"
Enter
Sleep 1500ms

# ── List users ────────────────────────────────────────────────────────────────
Type `curl -sS "http://127.0.0.1:8001/v1/users?page=1&pageSize=10" \`
Enter
Type `  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool`
Enter
Sleep 1500ms

# ── Teardown ──────────────────────────────────────────────────────────────────
Type "kill %1 2>/dev/null; echo 'Done. API docs: http://127.0.0.1:8001/docs'"
Enter
Sleep 1s
