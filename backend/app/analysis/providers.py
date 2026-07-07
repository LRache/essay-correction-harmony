from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from pydantic import ValidationError

from ..config import Settings
from ..schemas import (
    AnalysisReport,
    ExampleOut,
    GrammarIssue,
    MaterialSuggestion,
    ProviderMeta,
    RewriteSuggestion,
    ScoreDimension,
    SemanticMetric,
)


class AnalysisProvider(ABC):
    @abstractmethod
    def analyze(self, essay_id: str, title: str, prompt: str, content: str, examples: list[ExampleOut]) -> AnalysisReport:
        raise NotImplementedError


class MockRuleProvider(AnalysisProvider):
    version = "mock-rules-2026-07-06"

    def __init__(self, model: str = "mock-v1"):
        self.model = model

    def analyze(self, essay_id: str, title: str, prompt: str, content: str, examples: list[ExampleOut]) -> AnalysisReport:
        started = time.perf_counter()
        grammar_issues = self._grammar_issues(content)
        coherence_score = self._coherence_score(content)
        relevance_score = self._relevance_score(prompt, content)
        dimensions = self._dimensions(content, grammar_issues, coherence_score, relevance_score)
        total_score = round(sum(item.score for item in dimensions), 1)
        suggestions = self._suggestions(content, grammar_issues)
        materials = self._materials(prompt, content)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return AnalysisReport(
            essay_id=essay_id,
            title=title,
            prompt=prompt,
            grammar_issues=grammar_issues,
            coherence=SemanticMetric(
                score=coherence_score,
                summary="段落和句意衔接基本完整，首版使用规则特征估算。",
                evidence=["存在清晰开头和结尾" if len(content) > 80 else "篇幅偏短，论述展开不足"],
            ),
            relevance=SemanticMetric(
                score=relevance_score,
                summary="内容与题目关键词有一定关联，后续可替换为向量或 LLM 判分。",
                evidence=self._keyword_evidence(prompt, content),
            ),
            total_score=total_score,
            max_score=100,
            dimensions=dimensions,
            suggestions=suggestions,
            materials=materials,
            examples=examples[:2],
            provider=ProviderMeta(
                provider="mock",
                model=self.model,
                version=MockRuleProvider.version,
                latency_ms=latency_ms,
                fallback_used=False,
                errors=[],
            ),
        )

    def _grammar_issues(self, content: str) -> list[GrammarIssue]:
        issues: list[GrammarIssue] = []
        if "的的" in content:
            start = content.index("的的")
            issues.append(
                GrammarIssue(
                    id="grammar-duplicate-de",
                    start=start,
                    end=start + 2,
                    issue_type="duplicate_particle",
                    severity="medium",
                    message="疑似助词重复。",
                    suggestion="删除一个“的”，或重写该短语。",
                )
            )
        if "。" not in content and "！" not in content and "？" not in content:
            issues.append(
                GrammarIssue(
                    id="grammar-punctuation",
                    start=max(len(content) - 1, 0),
                    end=len(content),
                    issue_type="punctuation",
                    severity="low",
                    message="全文缺少明显句末标点。",
                    suggestion="按语义层次补充句号、问号或感叹号。",
                )
            )
        long_threshold = 90
        sentence_start = 0
        for index, char in enumerate(content):
            if char in "。！？":
                if index - sentence_start > long_threshold:
                    issues.append(
                        GrammarIssue(
                            id=f"grammar-long-sentence-{index}",
                            start=sentence_start,
                            end=index + 1,
                            issue_type="long_sentence",
                            severity="medium",
                            message="句子过长，可能影响表达清晰度。",
                            suggestion="拆分为两到三个短句，并补充连接词。",
                        )
                    )
                sentence_start = index + 1
        return issues

    def _coherence_score(self, content: str) -> float:
        connectors = ["首先", "然后", "因此", "但是", "后来", "最后", "于是", "同时"]
        hits = sum(1 for word in connectors if word in content)
        length_bonus = min(len(content) / 500, 1.0) * 20
        return round(min(62 + hits * 4 + length_bonus, 95), 1)

    def _relevance_score(self, prompt: str, content: str) -> float:
        keywords = [word for word in prompt.replace("，", " ").replace("。", " ").split(" ") if len(word) >= 2]
        if not keywords:
            return 76.0
        hits = sum(1 for word in keywords if word in content)
        return round(min(68 + hits * 8, 96), 1)

    def _keyword_evidence(self, prompt: str, content: str) -> list[str]:
        words = [word for word in prompt.replace("，", " ").replace("。", " ").split(" ") if len(word) >= 2]
        evidence: list[str] = []
        for word in words[:3]:
            if word in content:
                evidence.append(f"正文出现题目关键词：{word}")
        if not evidence:
            evidence.append("暂未发现明显题目关键词，建议补充扣题句。")
        return evidence

    def _dimensions(
        self,
        content: str,
        grammar_issues: list[GrammarIssue],
        coherence_score: float,
        relevance_score: float,
    ) -> list[ScoreDimension]:
        expression = max(18, 28 - len(grammar_issues) * 2)
        content_score = min(30, 18 + len(content) / 80)
        return [
            ScoreDimension(name="内容充实", score=round(content_score, 1), max_score=30, comment="依据篇幅和素材展开度估算。"),
            name_score("结构连贯", coherence_score, 25),
            name_score("主题相关", relevance_score, 25),
            ScoreDimension(name="语言表达", score=round(expression, 1), max_score=20, comment="依据规则检测问题数量估算。"),
        ]

    def _suggestions(self, content: str, grammar_issues: list[GrammarIssue]) -> list[RewriteSuggestion]:
        suggestions: list[RewriteSuggestion] = []
        for issue in grammar_issues:
            original = content[issue.start : issue.end]
            rewrite = original.replace("的的", "的")
            if issue.issue_type == "long_sentence":
                rewrite = "将长句拆成两句：先交代事实，再写感受或结果。"
            suggestions.append(
                RewriteSuggestion(
                    issue_id=issue.id,
                    original=original,
                    rewrite=rewrite,
                    rationale=issue.suggestion,
                )
            )
        if not suggestions:
            suggestions.append(
                RewriteSuggestion(
                    issue_id="style-clarity",
                    original="文章主体段",
                    rewrite="在关键情节后补一句心理变化，让叙事和主题连接更紧。",
                    rationale="增强内容层次和情感推进。",
                )
            )
        return suggestions

    def _materials(self, prompt: str, content: str) -> list[MaterialSuggestion]:
        theme = "成长"
        if "亲情" in prompt or "外婆" in content or "父母" in content:
            theme = "亲情"
        return [
            MaterialSuggestion(
                theme=theme,
                material="可补充一个具体场景：一次等待、一次选择、一次主动承担责任的细节。",
                usage_tip="素材不必很大，重点写动作、对话和心理变化。",
            )
        ]


def name_score(name: str, raw_score: float, max_score: float) -> ScoreDimension:
    score = round(raw_score / 100 * max_score, 1)
    return ScoreDimension(name=name, score=score, max_score=max_score, comment="首版由规则特征映射，后续可替换模型回归。")


class OpenAICompatibleProvider(AnalysisProvider):
    def __init__(self, settings: Settings, fallback: AnalysisProvider):
        self.settings = settings
        self.fallback = fallback

    def analyze(self, essay_id: str, title: str, prompt: str, content: str, examples: list[ExampleOut]) -> AnalysisReport:
        started = time.perf_counter()
        if not self.settings.ai_base_url or not self.settings.ai_api_key:
            report = self.fallback.analyze(essay_id, title, prompt, content, examples)
            report.provider.fallback_used = True
            report.provider.errors.append("AI_BASE_URL or AI_API_KEY is not configured")
            return report

        try:
            payload = self._request_payload(title, prompt, content)
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(
                url=f"{self.settings.ai_base_url.rstrip('/')}/chat/completions",
                data=data,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.settings.ai_api_key}",
                },
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                response_data = json.loads(response.read().decode("utf-8"))
            content_json = response_data["choices"][0]["message"]["content"]
            candidate = json.loads(content_json)
            report = AnalysisReport.model_validate(candidate)
            report.provider.provider = "openai-compatible"
            report.provider.model = self.settings.ai_model
            report.provider.latency_ms = int((time.perf_counter() - started) * 1000)
            return report
        except (KeyError, ValueError, urllib.error.URLError, TimeoutError, ValidationError) as exc:
            report = self.fallback.analyze(essay_id, title, prompt, content, examples)
            report.provider.fallback_used = True
            report.provider.errors.append(f"LLM schema validation or request failed: {exc}")
            return report

    def _request_payload(self, title: str, prompt: str, content: str) -> dict[str, Any]:
        schema_hint = (
            "Return JSON matching fields: essay_id,title,prompt,grammar_issues,coherence,"
            "relevance,total_score,max_score,dimensions,suggestions,materials,examples,provider."
        )
        return {
            "model": self.settings.ai_model,
            "messages": [
                {"role": "system", "content": f"You are a Chinese essay correction engine. {schema_hint}"},
                {"role": "user", "content": f"题目：{title}\n要求：{prompt}\n作文：{content}"},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }


class AIModelMockProvider(AnalysisProvider):
    version = "ai-model-mock-2026-07-07"

    def __init__(self, model: str):
        self.model = model

    def analyze(self, essay_id: str, title: str, prompt: str, content: str, examples: list[ExampleOut]) -> AnalysisReport:
        started = time.perf_counter()
        total_score = random.randint(60, 100)
        score_parts = [
            ("内容充实", round(total_score * 0.30, 1), 30),
            ("结构连贯", round(total_score * 0.25, 1), 25),
            ("主题相关", round(total_score * 0.25, 1), 25),
            ("语言表达", round(total_score * 0.20, 1), 20),
        ]
        comment = f"{title}的评语"
        grammar_message = f"{title}的语法问题"
        grammar_suggestion = f"{title}的语法建议"
        rewrite_original = f"{title}的原文片段"
        rewrite = f"{title}的改写建议"
        rewrite_rationale = f"{title}的改写说明"
        material = f"{title}的素材建议"
        usage_tip = f"{title}的素材使用建议"
        issue_end = min(max(len(title), 1), len(content))
        example = ExampleOut(
            id=f"mock-example-{essay_id}",
            title=f"{title}范文",
            prompt=prompt,
            content=f"{title}的范文",
            theme=title,
            highlights=[comment],
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        return AnalysisReport(
            essay_id=essay_id,
            title=title,
            prompt=prompt,
            grammar_issues=[
                GrammarIssue(
                    id="mock-grammar",
                    start=0,
                    end=issue_end,
                    issue_type="mock_grammar",
                    severity="medium",
                    message=grammar_message,
                    suggestion=grammar_suggestion,
                )
            ],
            coherence=SemanticMetric(score=float(total_score), summary=comment, evidence=[comment]),
            relevance=SemanticMetric(score=float(total_score), summary=comment, evidence=[comment]),
            total_score=float(total_score),
            max_score=100,
            dimensions=[
                ScoreDimension(name=name, score=score, max_score=max_score, comment=comment)
                for name, score, max_score in score_parts
            ],
            suggestions=[
                RewriteSuggestion(
                    issue_id="mock-grammar",
                    original=rewrite_original,
                    rewrite=rewrite,
                    rationale=rewrite_rationale,
                )
            ],
            materials=[
                MaterialSuggestion(
                    theme=title,
                    material=material,
                    usage_tip=usage_tip,
                )
            ],
            examples=[example],
            provider=ProviderMeta(
                provider="ai-model-mock",
                model=self.model,
                version=AIModelMockProvider.version,
                latency_ms=latency_ms,
                fallback_used=False,
                errors=[],
            ),
        )


def build_provider(settings: Settings) -> AnalysisProvider:
    if settings.ai_provider == "llm" or settings.ai_provider == "ai-model-mock" or settings.ai_model_configured:
        return AIModelMockProvider(model=settings.ai_model)
    fallback = MockRuleProvider(model=settings.ai_model)
    if settings.ai_provider == "openai-compatible":
        return OpenAICompatibleProvider(settings=settings, fallback=fallback)
    return fallback
