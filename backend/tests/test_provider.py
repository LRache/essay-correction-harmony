from __future__ import annotations

import json
import urllib.request

from app.analysis.local_nlp import LocalNLPProvider, NltkChineseGrammarChecker, SemanticScores
from app.analysis.providers import OpenAICompatibleProvider, RuleSupportProvider
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
    provider = OpenAICompatibleProvider(settings, RuleSupportProvider())

    report = provider.analyze("essay-1", "标题", "要求", "作文正文。", [])

    assert report.essay_id == "essay-1"
    assert report.provider.provider == "openai-compatible"
    assert report.provider.model == "test-model"
    assert report.provider.fallback_used is False
    # Moonshot may return valid JSON while omitting useful optional content.
    # A successful external report must still be as complete as the BERT path.
    assert report.suggestions
    assert report.materials


def test_openai_provider_preserves_requested_provider_when_falling_back() -> None:
    settings = Settings(
        database_path=":memory:", jwt_secret="test", token_ttl_seconds=60,
        ai_provider="openai-compatible", ai_base_url="", ai_api_key="", ai_model="moonshot-test",
    )

    report = OpenAICompatibleProvider(settings, RuleSupportProvider()).analyze(
        "essay-1", "标题", "作文要求", "这是一篇用于测试降级逻辑的作文正文。", []
    )

    assert report.provider.provider == "openai-compatible"
    assert report.provider.model == "moonshot-test"
    assert report.provider.fallback_used is True
    assert "fallback provider=local-nlp" in report.provider.errors[-1]


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


def test_local_nlp_caps_short_gibberish_even_when_aes_predicts_high(monkeypatch) -> None:
    settings = Settings(
        database_path=":memory:", jwt_secret="test", token_ttl_seconds=60,
        ai_provider="local-nlp", ai_base_url="", ai_api_key="", ai_model="unused",
        local_model_warmup=False,
    )
    provider = LocalNLPProvider(settings)
    monkeypatch.setattr(
        provider.semantic, "analyze",
        lambda *_: SemanticScores(coherence=86.0, relevance=92.1, engine="test", errors=[]),
    )
    monkeypatch.setattr(provider.scorer, "predict", lambda *_: (85.9, None))
    monkeypatch.setattr(provider.grammar_detector, "detect", lambda *_: ([], None))

    report = provider.analyze(
        "essay-1", "校园里的温暖", "请围绕校园生活中的温暖瞬间写一篇记叙文。",
        "答案是打发打发的地方高大上的工作新东方大师傅似的发生过对方哈哈绕过", [],
    )

    assert report.total_score == 30.0
    assert round(sum(item.score for item in report.dimensions), 1) == 30.0
    assert "有效性检查" in report.dimensions[0].comment


def test_quality_gate_does_not_cap_full_length_multi_sentence_essay() -> None:
    content = "。".join(["清晨我走进校园，看见老师正在帮助同学整理散落的书本" for _ in range(12)]) + "。"

    cap, reason = LocalNLPProvider._quality_score_cap(content)

    assert cap is None
    assert reason is None


def test_rewrite_suggestions_are_actionable_and_have_positions() -> None:
    provider = RuleSupportProvider()
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
    assert suggestions[0].category == "语言表达"
    assert suggestions[0].scope == "sentence"
    assert suggestions[0].start == 6
    assert suggestions[0].end == 8
    assert "重复助词" in suggestions[0].rationale
    assert suggestions[0].improvement


def test_deep_suggestions_include_material_detail_and_theme_feedback() -> None:
    provider = RuleSupportProvider()
    prompt = "请以成长中的一次选择为题，写一篇记叙文。"
    content = (
        "我想到守株待兔的故事，就决定等机会自己出现。"
        "老师让我报名时，我很犹豫。"
        "后来我明白自己应该做出选择。"
    )

    report = provider.analyze("essay-1", "一次选择", prompt, content, [])

    categories = {suggestion.category for suggestion in report.suggestions}
    assert "素材与典故" in categories
    assert "描写细化" in categories
    allusion = next(suggestion for suggestion in report.suggestions if suggestion.category == "素材与典故")
    assert allusion.issue_text == "守株待兔"
    assert allusion.priority == "high"
    detail = next(suggestion for suggestion in report.suggestions if suggestion.category == "描写细化")
    assert "动作" in detail.rewrite
    assert detail.scope == "paragraph"


def test_polished_warmth_essay_still_gets_upgrade_suggestion() -> None:
    provider = RuleSupportProvider()
    prompt = "请以“藏在细节里的温暖”为题，写一篇记叙文。要求选取真实具体的生活事件，运用动作、语言和心理描写。"
    content = (
        "清晨，雨点密密地落在窗户上。母亲追到门口，把一把雨伞塞进我的手里，又蹲下来替我系好松开的鞋带。"
        "“天气凉，记得把外套穿好。”她叮嘱道。“知道了。”我随口回答，心里却有些不耐烦。"
        "放学时，雨下得更大了。母亲站在马路对面，裤脚已经湿透，手里还提着一个保温袋。"
        "袋子里装着一个烤红薯。剥开外皮，热气立刻冒了出来，甜甜的香味驱散了雨天的寒意。"
        "母亲接过我的书包，又把伞向我这边倾斜。雨水顺着伞沿落下，很快打湿了她的一侧肩膀。"
        "那一刻，我悄悄把伞推向她，她却又将伞移了回来。"
        "我第一次明白，那些藏在细节里的温暖始终陪伴着我。"
    )

    report = provider.analyze("essay-1", "藏在细节里的温暖", prompt, content, [])

    assert report.suggestions
    suggestion = report.suggestions[0]
    assert suggestion.category == "描写细化"
    assert suggestion.issue_text == "可进一步升格"
    assert suggestion.priority == "low"
    assert suggestion.rewrite != suggestion.original


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
    provider = RuleSupportProvider()
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
    provider = RuleSupportProvider()
    content = "首先，我决定参加比赛。\n后来，我认真完成了训练。"

    dimensions = provider._dimensions("请以一次选择为题", content, [], 82.0, 88.0)
    comments = {item.name: item.comment for item in dimensions}

    assert f"正文约{len(content.replace(chr(10), ''))}字" in comments["内容充实"]
    assert "共2段" in comments["内容充实"]
    assert "“首先”" in comments["结构连贯"]
    assert "主题匹配度为88.0%" in comments["主题相关"]
    assert "未检测到明确的规则类语病" in comments["语言表达"]
