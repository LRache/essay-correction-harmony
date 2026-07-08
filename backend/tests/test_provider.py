from __future__ import annotations

import json
import urllib.request

from app.analysis.local_nlp import LocalNLPProvider, NltkChineseGrammarChecker
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


def test_openai_provider_preserves_requested_provider_when_falling_back() -> None:
    settings = Settings(
        database_path=":memory:", jwt_secret="test", token_ttl_seconds=60,
        ai_provider="openai-compatible", ai_base_url="", ai_api_key="", ai_model="moonshot-test",
    )

    report = OpenAICompatibleProvider(settings, MockRuleProvider()).analyze(
        "essay-1", "标题", "作文要求", "这是一篇用于测试降级逻辑的作文正文。", []
    )

    assert report.provider.provider == "openai-compatible"
    assert report.provider.model == "moonshot-test"
    assert report.provider.fallback_used is True
    assert "fallback provider=mock" in report.provider.errors[-1]


def test_nltk_checker_returns_character_level_chinese_grammar_issues() -> None:
    checker = NltkChineseGrammarChecker()
    content = "通过这次活动使我明白了坚持的的意义。。"

    issues = checker.check(content)

    issue_types = {issue.issue_type for issue in issues}
    assert {"missing_subject", "duplicate_particle", "duplicate_punctuation"}.issubset(issue_types)
    duplicate = next(issue for issue in issues if issue.issue_type == "duplicate_particle")
    assert content[duplicate.start : duplicate.end] == "的的"


def test_local_nlp_provider_has_safe_semantic_fallback() -> None:
    settings = Settings(
        database_path=":memory:", jwt_secret="test", token_ttl_seconds=60,
        ai_provider="local-nlp", ai_base_url="", ai_api_key="", ai_model="unused",
        local_bert_model="model-that-does-not-exist", local_model_files_only=True,
    )
    report = LocalNLPProvider(settings).analyze(
        "essay-1", "坚持", "请围绕坚持写一篇作文。",
        "通过这次长跑使我懂得坚持的的意义。后来，我每天认真训练，最后跑到了终点。", [],
    )

    assert report.provider.provider == "local-nlp"
    assert report.provider.fallback_used is True
    assert report.coherence.score > 0
    assert report.relevance.score > 0
