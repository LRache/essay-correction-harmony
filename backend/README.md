# Essay Correction Backend

FastAPI backend for the Harmony Chinese essay correction prototype.

## Run

```bash
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

Default seed accounts:

- Student: `student@example.com` / `student123`
- Teacher: `teacher@example.com` / `teacher123`

## AI Provider Configuration

The default provider is deterministic mock analysis. Copy `.env.example` to `.env` and configure an OpenAI-compatible service:

```dotenv
AI_PROVIDER=openai-compatible
AI_BASE_URL=https://api.example.com/v1
AI_API_KEY=...
AI_MODEL=...
# If a local VPN proxy breaks TLS to the API, bypass it for this host:
NO_PROXY=api.example.com
```

Process environment variables take precedence over values in `.env`.

If the LLM response fails schema validation, the backend falls back to the rule/mock provider and records provider errors in the report metadata.
