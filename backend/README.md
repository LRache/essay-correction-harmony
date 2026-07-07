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

The default provider is the LLM mock report provider. You can override the model name with:

```bash
AI_PROVIDER=llm
AI_MODEL=demo-model
```

The LLM mock report uses a random score and prompt-title-based mock text for the example essay, comments, grammar issues, rewrite suggestions, material suggestions, and related fields. Generated examples are saved into the examples table so the app's example tab can display them. Set `AI_PROVIDER=mock` to use the older deterministic rule template.
