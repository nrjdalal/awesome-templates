# Chatbot With Memory Example

A multi-turn chatbot example that extends `simple_chatbot` by persisting
conversation history to the database and replaying it into the agent on
each call — giving the LLM full context of the ongoing session.

## What This Example Teaches

- How to maintain stateful conversation history across multiple requests
- How to load prior turns from the database and pass them as context to a PydanticAI Agent
- How to organise session-scoped data in a DDD domain following the blueprint layout

Compare with `examples/simple_chatbot/` for the stateless baseline this
example builds on.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/memory` | Send a message; reply is context-aware using session history |
| GET | `/v1/chat/memory/{session_id}` | Retrieve full conversation history for a session |

## Quick Start

```bash
# Copy into src/ so auto-discovery picks it up
cp -r examples/chatbot_with_memory src/chatbot_with_memory

# Start the server
rm -f ./quickstart.db
make quickstart
```

### Send a message

```bash
curl -X POST http://127.0.0.1:8001/v1/chat/memory \
  -H "Content-Type: application/json" \
  -d '{"session_id": "my-session", "prompt": "Hello, who are you?"}'
```

### Continue the conversation

```bash
curl -X POST http://127.0.0.1:8001/v1/chat/memory \
  -H "Content-Type: application/json" \
  -d '{"session_id": "my-session", "prompt": "What did I just ask you?"}'
```

### Retrieve session history

```bash
curl http://127.0.0.1:8001/v1/chat/memory/my-session
```

## Running Tests

```bash
pytest tests/unit/chatbot_with_memory/ -v
```

## Production Considerations

This example is intentionally minimal — no auth on the endpoint and no
rate limiting. Production deployments should add authentication, rate
limiting, and cost controls before exposing a session-based LLM endpoint
publicly. For prompt-injection handling see
[guardrails.py](../../src/_core/infrastructure/llm/guardrails.py).
