from __future__ import annotations

import json
import urllib.request

from app.analysis.providers import MockRuleProvider, OpenAICompatibleProvider
from app.config import Settings


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def test_openai_provider_builds_server_owned_report(monkeypatch) -> None:
    correction = {
        "grammar_issues": [],
        "coherence": {"score": 80, "summary": "结构清晰", "evidence": ["有开头和结尾"]},
        "relevance": {"score": 85, "summary": "切合题意", "evidence": ["围绕主题展开"]},
        "total_score": 82,
        "max_score": 100,
        "dimensions": [
            {"name": "内容", "score": 82, "max_score": 100, "comment": "内容完整"}
        ],
        "suggestions": [],
        "materials": [],
    }
    api_response = {"choices": [{"message": {"content": json.dumps(correction, ensure_ascii=False)}}]}
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse(api_response))
    settings = Settings(
        database_path=":memory:",
        jwt_secret="test",
        token_ttl_seconds=60,
        ai_provider="openai-compatible",
        ai_base_url="https://api.example.com/v1",
        ai_api_key="test-key",
        ai_model="test-model",
    )
    provider = OpenAICompatibleProvider(settings, MockRuleProvider())

    report = provider.analyze("essay-1", "标题", "要求", "作文正文。", [])

    assert report.essay_id == "essay-1"
    assert report.provider.provider == "openai-compatible"
    assert report.provider.model == "test-model"
    assert report.provider.fallback_used is False

