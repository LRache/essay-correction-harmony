from __future__ import annotations

import json
import urllib.request

from app.analysis.local_nlp import LocalNLPProvider, NltkChineseGrammarChecker
from app.analysis.providers import MockRuleProvider, OpenAICompatibleProvider
from app.config import Settings
from app.schemas import GrammarIssue, RewriteSuggestion


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


def test_rewrite_suggestions_are_actionable_and_have_positions() -> None:
    provider = MockRuleProvider()
    content = "这是一个重要的的选择。"
    issues = [
        GrammarIssue(
            id="duplicate", start=6, end=8, issue_type="duplicate_particle",
            severity="medium", message="重复", suggestion="删除重复助词",
        ),
        GrammarIssue(
            id="uncertain", start=2, end=3, issue_type="bert_grammar",
            severity="medium", message="可能有问题", suggestion="结合上下文检查",
        ),
    ]

    suggestions = provider._suggestions(content, issues)

    assert len(suggestions) == 1
    assert suggestions[0].original == "这是一个重要的的选择。"
    assert suggestions[0].rewrite == "这是一个重要的选择。"
    assert suggestions[0].issue_text == "的的"
    assert suggestions[0].paragraph_index == 1
    assert suggestions[0].sentence_index == 1
    assert suggestions[0].start == 6
    assert suggestions[0].end == 8
    assert "重复助词" in suggestions[0].rationale
    assert suggestions[0].improvement


def test_external_suggestion_filter_removes_noop_generic_and_unlocated_items() -> None:
    content = "我认真完成了作业。"
    candidates = [
        RewriteSuggestion(issue_id="noop", original="我", rewrite="我", rationale="没有变化"),
        RewriteSuggestion(
            issue_id="generic", original="认真", rewrite="仔细",
            rationale="结合上下文检查词语搭配、成分完整性或语序，并重写该处。",
        ),
        RewriteSuggestion(
            issue_id="valid", original="认真", rewrite="仔细",
            rationale="“仔细”更准确地修饰完成作业这一动作。",
        ),
        RewriteSuggestion(
            issue_id="missing", original="不存在", rewrite="其他", rationale="原文没有这个片段，因此不能定位。",
        ),
        RewriteSuggestion(
            issue_id="legacy-char", original="我", rewrite="他",
            rationale="这个单字可能需要替换，但旧报告没有保存准确位置。",
        ),
    ]

    cleaned = OpenAICompatibleProvider._sanitize_suggestions(content, candidates)

    assert len(cleaned) == 1
    assert cleaned[0].issue_id == "valid"
    assert cleaned[0].issue_text == "认真"
    assert cleaned[0].original == "我认真完成了作业。"
    assert cleaned[0].rewrite == "我仔细完成了作业。"
    assert cleaned[0].paragraph_index == 1
    assert cleaned[0].sentence_index == 1


def test_external_suggestion_keeps_positioned_character_fix_as_full_sentence() -> None:
    content = "他把书递给了我。"
    candidate = RewriteSuggestion(
        issue_id="positioned",
        original="把",
        rewrite="将",
        rationale="书面叙述中改用“将”，语气更正式。",
        issue_text="把",
        start=1,
        end=2,
    )

    cleaned = OpenAICompatibleProvider._sanitize_suggestions(content, [candidate])

    assert len(cleaned) == 1
    assert cleaned[0].original == "他把书递给了我。"
    assert cleaned[0].rewrite == "他将书递给了我。"


def test_rewrite_suggestion_locates_paragraph_and_sentence() -> None:
    provider = MockRuleProvider()
    content = "开头第一句。开头第二句。\n\n第二段有的的错误。"
    start = content.index("的的")
    issue = GrammarIssue(
        id="duplicate", start=start, end=start + 2, issue_type="duplicate_particle",
        severity="medium", message="重复", suggestion="删除重复助词",
    )

    suggestion = provider._suggestions(content, [issue])[0]

    assert suggestion.paragraph_index == 2
    assert suggestion.sentence_index == 1
    assert suggestion.original == "第二段有的的错误。"
    assert suggestion.rewrite == "第二段有的错误。"


def test_dimension_comments_are_specific_to_the_essay() -> None:
    provider = MockRuleProvider()
    content = "首先，我决定参加比赛。\n后来，我认真完成了训练。"

    dimensions = provider._dimensions("请以一次选择为题", content, [], 82.0, 88.0)
    comments = {item.name: item.comment for item in dimensions}

    assert f"正文约{len(content.replace(chr(10), ''))}字" in comments["内容充实"]
    assert "共2段" in comments["内容充实"]
    assert "“首先”" in comments["结构连贯"]
    assert "主题匹配度为88.0%" in comments["主题相关"]
    assert "未检测到明确的规则类语病" in comments["语言表达"]
