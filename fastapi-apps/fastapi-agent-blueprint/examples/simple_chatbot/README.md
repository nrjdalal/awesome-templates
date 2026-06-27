# Simple Chatbot Example

This example demonstrates a minimal, stateless PydanticAI Agent utilizing structured output models (`ChatReply`) and database persistence (`ChatMessageDTO`), without vector stores or conversation history/memory. 

It serves as a clean starting point for executing LLM-backed workflows within the blueprint's 3-tier DDD architecture.

## How it works

1. **Client Request:** The client sends a prompt via `POST /v1/chat`.
2. **Execution & Structured Output:** `ChatService` invokes the LLM chatbot adapter which runs a PydanticAI Agent initialized with a structured output type `ChatReply(reply, confidence)` and the inline instructions (`_INSTRUCTIONS = "You are a helpful assistant."`).
3. **Token Usage Calculation:** Raw token usage is extracted from PydanticAI's `RunResult.usage()` in the service layer to calculate `tokens_used = (input_tokens + output_tokens)`.
4. **Database Persistence:** The prompt, generated reply, and total tokens used are persisted to the `chatbot_message` database table as a `ChatMessageDTO` record.
5. **API Response:** The endpoint returns the generated reply, the model's confidence, and the tokens used.
6. **History Retrieval:** Historical messages can be queried by ID via `GET /v1/chat/{chat_id}` which retrieves records directly from the database.

> [!NOTE]
> Surfaces `tokens_used` for educational visibility only. For production-grade multi-tenant usage/cost tracking, see the `ai_usage` domain (#75).

> [!IMPORTANT]
> **Production Considerations:** Unlike the database-centric CRUD examples, this example communicates with a real external LLM. For production deployments, you must implement authentication, rate limiting, and cost/budget controls. Additionally, see [guardrails.py](../../src/_core/infrastructure/llm/guardrails.py) for examples of protecting LLM boundaries against prompt-injection attacks.

## Running the Example

### 1. Copy the example to `src/`

Since the blueprint auto-discovers packages under `src/` on boot:

```bash
cp -r examples/simple_chatbot src/simple_chatbot
```

### 2. Configure Environment Variables

Edit `_env/quickstart.env` (or create a local env file) and configure your LLM provider and API key:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your-openai-api-key-here
```

Supported providers are `openai`, `anthropic`, and `bedrock`.

### 3. Start the Server

```bash
rm -f ./quickstart.db  # Wipes old SQLite database so new tables migrate on start
make quickstart
```

### 4. Exercise the Endpoints

#### POST a message to the chatbot

```bash
curl -X POST http://127.0.0.1:8001/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain the color blue in one sentence."}'
```

Response format:
```json
{
  "status": "success",
  "data": {
    "reply": "Blue is a cool, calming color that is often associated with the sky and the sea, representing depth, stability, and trust.",
    "confidence": 0.95,
    "tokens_used": 64
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
    "prompt": "Explain the color blue in one sentence.",
    "reply": "Blue is a cool, calming color that is often associated with the sky and the sea, representing depth, stability, and trust.",
    "tokens_used": 64,
    "created_at": "2026-06-20T17:52:12.456Z"
  }
}
```

### 5. Cleanup

Remove the example once you are done evaluating:

```bash
rm -rf src/simple_chatbot
rm -f ./quickstart.db
```

## Running Tests

Unit tests are written to verify both the stub fallback flow and real LLM adapter integration (using PydanticAI's `TestModel` to mock model runs without requiring actual API keys).

Run the unit tests:

```bash
pytest tests/unit/simple_chatbot/ -v
```
