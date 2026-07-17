# Web Search Chatbot Example

This example demonstrates a minimal, stateless PydanticAI Agent that can invoke a real web search tool (DuckDuckGo, keyless) to answer questions requiring current or up-to-date information. It builds on `examples/simple_chatbot/` - same structured output model (`ChatReply`) and database persistence (`ChatMessageDTO`) - with a tool-calling agent in place of the plain chat agent.

It serves as a starting point for agentic tool-use workflows within the blueprint's 3-tier DDD architecture.

## How it works

1. **Client Request:** The client sends a prompt via `POST /v1/chat`.
2. **Execution & Tool Use:** `ChatService` invokes the LLM chatbot adapter, which runs a PydanticAI Agent configured with `tools=[duckduckgo_search_tool()]` and a structured output type `ChatReply(reply, confidence)`. The agent decides on its own whether the prompt needs a web search before replying.
3. **Token Usage Calculation:** Raw token usage (including any tool-call tokens) is extracted from PydanticAI's `RunResult.usage()` in the service layer to calculate `tokens_used = (input_tokens + output_tokens)`.
4. **Database Persistence:** The prompt, generated reply, and total tokens used are persisted to the `web_search_chatbot_message` database table as a `ChatMessageDTO` record.
5. **API Response:** The endpoint returns the generated reply, the model's confidence, and the tokens used.
6. **History Retrieval:** Historical messages can be queried by ID via `GET /v1/chat/{chat_id}`, which retrieves records directly from the database.

> [!NOTE]
> Surfaces `tokens_used` for educational visibility only. For production-grade multi-tenant usage/cost tracking, see the `ai_usage` domain (#75).

> [!IMPORTANT]
> **Production Considerations:** This example communicates with both a real external LLM and a real external search engine. For production deployments, you must implement authentication, rate limiting, and cost/budget controls. Additionally, see [guardrails.py](../../src/_core/infrastructure/llm/guardrails.py) for examples of protecting LLM boundaries against prompt-injection attacks - this matters more with tool use, since search results are untrusted third-party content flowing back into the agent.

## Running the Example

### 1. Copy the example to `src/`

Since the blueprint auto-discovers packages under `src/` on boot:

```bash
cp -r examples/web_search_chatbot src/web_search_chatbot
```

### 2. Install the DuckDuckGo search extra

```bash
uv sync --extra admin --extra pydantic-ai-duckduckgo --extra openai
```
> Note: If you run `make quickstart` again after this, it re-syncs with only the `admin` extra — you'll need to re-run the combined sync above.

### 3. Configure Environment Variables

Edit `_env/quickstart.env` (or create a local env file) and configure your LLM provider and API key:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your-openai-api-key-here
```

Supported providers are `openai`, `anthropic`, and `bedrock`. No separate API key is needed for DuckDuckGo search itself - it's keyless. If `LLM_PROVIDER`/`LLM_MODEL` are not set, the example falls back to a deterministic `StubChatbot` with no network calls at all.

### 4. Start the Server

```bash
rm -f ./quickstart.db  # Wipes old SQLite database so new tables migrate on start
make quickstart
```

### 5. Exercise the Endpoints

#### POST a message to the chatbot

```bash
curl -X POST http://127.0.0.1:8001/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the latest stable version of Python?"}'
```

Response format:

```json
{
  "status": "success",
  "data": {
    "reply": "The latest stable version of Python is 3.13.x as of the search results.",
    "confidence": 0.9,
    "tokensUsed": 210
  }
}
```

#### GET a historical reply by ID

```bash
curl http://127.0.0.1:8001/v1/chat/1
```

Response format:

```json
{
  "status": "success",
  "data": {
    "id": 1,
    "prompt": "What is the latest stable version of Python?",
    "reply": "The latest stable version of Python is 3.13.x as of the search results.",
    "tokensUsed": 210,
    "createdAt": "2026-06-20T17:52:12.456Z"
  }
}
```

### 6. Cleanup

Remove the example once you are done evaluating:

```bash
rm -rf src/web_search_chatbot
rm -f ./quickstart.db
```

## Running Tests

Unit tests verify both the stub fallback flow and the real LLM adapter's tool wiring. The tool-invocation test runs fully offline (a fake/stub tool via `FunctionModel`, not the real `duckduckgo_search_tool`), so no network call happens during tests.

Run the unit tests:

```bash
pytest tests/unit/web_search_chatbot/ -v
```
