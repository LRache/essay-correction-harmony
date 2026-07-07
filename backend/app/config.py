from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: str
    jwt_secret: str
    token_ttl_seconds: int
    ai_provider: str
    ai_base_url: str
    ai_api_key: str
    ai_model: str
    ai_model_configured: bool = False


def load_settings() -> Settings:
    backend_root = Path(__file__).resolve().parents[1]
    default_db = backend_root / "data" / "app.db"
    return Settings(
        database_path=os.getenv("ESSAY_DB_PATH", str(default_db)),
        jwt_secret=os.getenv("APP_JWT_SECRET", "dev-secret-change-me"),
        token_ttl_seconds=int(os.getenv("APP_TOKEN_TTL_SECONDS", "86400")),
        ai_provider=os.getenv("AI_PROVIDER", "llm"),
        ai_base_url=os.getenv("AI_BASE_URL", ""),
        ai_api_key=os.getenv("AI_API_KEY", ""),
        ai_model=os.getenv("AI_MODEL", "demo-model"),
        ai_model_configured="AI_MODEL" in os.environ,
    )
