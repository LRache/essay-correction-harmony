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
    local_bert_model: str = "uer/chinese_roberta_L-2_H-128"
    local_model_files_only: bool = False
    local_model_warmup: bool = False
    local_scoring_model: str = ""
    local_grammar_model: str = ""
    ai_timeout_seconds: int = 60


def _load_local_env(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding process variables."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value.startswith(("\"", "'")):
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def load_settings() -> Settings:
    backend_root = Path(__file__).resolve().parents[1]
    _load_local_env(backend_root / ".env")
    os.environ.setdefault("HF_HOME", str(backend_root / ".cache" / "huggingface"))
    default_db = backend_root / "data" / "app.db"
    return Settings(
        database_path=os.getenv("ESSAY_DB_PATH", str(default_db)),
        jwt_secret=os.getenv("APP_JWT_SECRET", "dev-secret-change-me"),
        token_ttl_seconds=int(os.getenv("APP_TOKEN_TTL_SECONDS", "86400")),
        ai_provider=os.getenv("AI_PROVIDER", "local-nlp"),
        ai_base_url=os.getenv("AI_BASE_URL", ""),
        ai_api_key=os.getenv("AI_API_KEY", ""),
        ai_model=os.getenv("AI_MODEL", "openai-compatible-model"),
        local_bert_model=os.getenv("LOCAL_BERT_MODEL", "uer/chinese_roberta_L-2_H-128"),
        local_model_files_only=os.getenv("LOCAL_MODEL_FILES_ONLY", "false").lower() in {"1", "true", "yes"},
        local_model_warmup=os.getenv("LOCAL_MODEL_WARMUP", "true").lower() in {"1", "true", "yes"},
        local_scoring_model=os.getenv("LOCAL_SCORING_MODEL", str(backend_root / "models" / "aes-scorer")),
        local_grammar_model=os.getenv("LOCAL_GRAMMAR_MODEL", str(backend_root / "models" / "grammar-detector")),
        ai_timeout_seconds=int(os.getenv("AI_TIMEOUT_SECONDS", "60")),
    )
