from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ValidationError

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


def locate_sentence(content: str, start: int, end: int) -> tuple[int, int, int, int, str]:
    """Return paragraph/sentence numbers and exact sentence bounds for an issue."""
    safe_start = max(0, min(start, len(content)))
    paragraph_number = 0
    cursor = 0
    paragraph_start = 0
    paragraph_end = len(content)
    for line in content.splitlines(keepends=True) or [content]:
        line_end = cursor + len(line)
        if line.strip():
            paragraph_number += 1
        if cursor <= safe_start < line_end or (safe_start == len(content) and line_end == len(content)):
            paragraph_start = cursor
            paragraph_end = line_end
            paragraph_number = max(paragraph_number, 1)
            break
        cursor = line_end

    paragraph_text = content[paragraph_start:paragraph_end].rstrip("\r\n")
    sentence_number = 0
    for match in re.finditer(r"[^。！？!?；;]+[。！？!?；;]?", paragraph_text):
        raw = match.group(0)
        if not raw.strip():
            continue
        sentence_number += 1
        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw) - len(raw.rstrip())
        sentence_start = paragraph_start + match.start() + leading
        sentence_end = paragraph_start + match.end() - trailing
        if sentence_start <= safe_start < sentence_end or (
            safe_start == sentence_end and end == safe_start
        ):
            return paragraph_number, sentence_number, sentence_start, sentence_end, content[sentence_start:sentence_end]

    fallback_start = max(paragraph_start, safe_start)
    fallback_end = max(fallback_start, min(max(end, safe_start + 1), len(content)))
    return max(paragraph_number, 1), max(sentence_number, 1), fallback_start, fallback_end, content[fallback_start:fallback_end]


class AnalysisProvider(ABC):
    @abstractmethod
    def analyze(self, essay_id: str, title: str, prompt: str, content: str, examples: list[ExampleOut]) -> AnalysisReport:
        raise NotImplementedError


class LLMCorrectionResult(BaseModel):
    """Only fields that the external model is responsible for generating."""

    grammar_issues: list[GrammarIssue]
    coherence: SemanticMetric
    relevance: SemanticMetric
    total_score: float
    max_score: float
    dimensions: list[ScoreDimension]
    suggestions: list[RewriteSuggestion]
    materials: list[MaterialSuggestion]


class MockRuleProvider(AnalysisProvider):
    version = "mock-rules-2026-07-06"

    def __init__(self, model: str = "mock-v1"):
        self.model = model

    def analyze(self, essay_id: str, title: str, prompt: str, content: str, examples: list[ExampleOut]) -> AnalysisReport:
        started = time.perf_counter()
        grammar_issues = self._grammar_issues(content)
        coherence_score = self._coherence_score(content)
        relevance_score = self._relevance_score(prompt, content)
        dimensions = self._dimensions(prompt, content, grammar_issues, coherence_score, relevance_score)
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
        prompt: str,
        content: str,
        grammar_issues: list[GrammarIssue],
        coherence_score: float,
        relevance_score: float,
    ) -> list[ScoreDimension]:
        expression = max(10, 20 - len(grammar_issues) * 2)
        content_score = min(30, 18 + len(content) / 80)
        compact_content = re.sub(r"\s+", "", content)
        paragraphs = [part.strip() for part in re.split(r"\n+", content) if part.strip()]
        sentences = [part.strip() for part in re.split(r"[。！？!?]+", content) if part.strip()]
        connector_words = ["首先", "然后", "因此", "但是", "后来", "最后", "于是", "同时", "然而"]
        used_connectors = [word for word in connector_words if word in content]
        dialogue_count = min(content.count("“"), content.count("”"))

        if len(compact_content) >= 600:
            content_judgement = "篇幅充足"
        elif len(compact_content) >= 400:
            content_judgement = "篇幅基本充足"
        else:
            content_judgement = "篇幅偏短，可补充关键场景和人物细节"
        detail_note = f"，含{dialogue_count}处对话描写" if dialogue_count else "，可增加动作、语言或心理细节"
        content_comment = (
            f"正文约{len(compact_content)}字，共{len(paragraphs)}段、{len(sentences)}句；"
            f"{content_judgement}{detail_note}。"
        )

        if used_connectors:
            connector_note = "、".join(f"“{word}”" for word in used_connectors[:3])
            structure_comment = (
                f"全文分为{len(paragraphs)}段，使用了{connector_note}等衔接词；"
                "段落推进较清楚，可继续加强段尾与下段开头的照应。"
            )
        else:
            structure_comment = (
                f"全文共{len(paragraphs)}段、{len(sentences)}句，未发现明显衔接词；"
                "建议在事件转折和结尾处补充承接句。"
            )

        prompt_excerpt = re.sub(r"\s+", "", prompt)[:18]
        if relevance_score >= 85:
            relevance_judgement = "中心内容与题目要求贴合，扣题较明确"
        elif relevance_score >= 75:
            relevance_judgement = "基本围绕题目展开，但关键段落还可增加点题句"
        else:
            relevance_judgement = "与题目关键词的呼应不足，建议在开头和结尾明确主题"
        relevance_comment = f"针对“{prompt_excerpt}”的主题匹配度为{relevance_score:.1f}%；{relevance_judgement}。"

        if grammar_issues:
            issue_types = "、".join(dict.fromkeys(issue.message.rstrip("。") for issue in grammar_issues[:2]))
            expression_comment = (
                f"检测到{len(grammar_issues)}处可确认的表达问题（{issue_types}）；"
                "修改后应再通读，检查句子是否简洁顺畅。"
            )
        else:
            expression_comment = "未检测到明确的规则类语病，句子整体通顺；可进一步减少重复词并丰富句式变化。"
        return [
            ScoreDimension(name="内容充实", score=round(content_score, 1), max_score=30, comment=content_comment),
            ScoreDimension(
                name="结构连贯", score=round(coherence_score / 100 * 25, 1), max_score=25,
                comment=structure_comment,
            ),
            ScoreDimension(
                name="主题相关", score=round(relevance_score / 100 * 25, 1), max_score=25,
                comment=relevance_comment,
            ),
            ScoreDimension(
                name="语言表达", score=round(expression, 1), max_score=20,
                comment=expression_comment,
            ),
        ]

    def _suggestions(self, content: str, grammar_issues: list[GrammarIssue]) -> list[RewriteSuggestion]:
        suggestions: list[RewriteSuggestion] = []
        for issue in grammar_issues:
            issue_text = content[issue.start : issue.end]
            paragraph, sentence, sentence_start, sentence_end, original_sentence = locate_sentence(
                content, issue.start, issue.end
            )
            replacement: str | None = None
            rewritten_sentence: str | None = None
            rationale = issue.suggestion
            improvement = ""
            if issue.issue_type == "duplicate_particle":
                replacement = issue_text.replace("的的", "的").replace("地地", "地").replace("得得", "得")
                rationale = "删除重复助词，避免成分赘余。"
                improvement = "修改后消除了重复成分，句子更简洁、读起来更自然。"
            elif issue.issue_type == "duplicate_punctuation" and issue_text:
                replacement = issue_text[0]
                rationale = "连续标点在此处没有额外语义，保留一个即可。"
                improvement = "修改后标点使用规范，避免不必要的停顿和视觉干扰。"
            elif issue.issue_type == "missing_subject" and "通过" in issue_text:
                replacement = issue_text.replace("通过", "", 1)
                rationale = "“通过……使……”同时使用介词和使令结构，容易造成句子缺少明确主语。"
                improvement = "删去介词后，句子的主语和谓语关系更清楚，结构也更完整。"
            elif issue.issue_type == "double_negative" and "不" in issue_text:
                replacement = issue_text.replace("不", "", 1)
                rationale = "“避免”已经含有否定意味，再使用“不”会造成否定关系混乱。"
                improvement = "修改后否定关系单一明确，不会产生与原意相反的理解。"
            elif issue.issue_type == "two_sided_mismatch" and "是否" in issue_text:
                replacement = issue_text.replace("是否", "", 1)
                rationale = "“是否”表示两种可能，不能与单向判断词“是”直接对应。"
                improvement = "修改后前后表意保持一致，判断关系更严谨。"
            elif issue.issue_type == "redundant_approximation" and "左右" in issue_text:
                replacement = issue_text.replace("左右", "", 1)
                rationale = "“大约/约”和“左右”都表示估计，保留一处即可。"
                improvement = "修改后数量表达不再重复，语义更准确。"
            elif issue.issue_type == "punctuation" and issue.end == len(content) and original_sentence:
                rewritten_sentence = f"{original_sentence}。"
                rationale = "文章末句需要使用句末标点，使语意完整结束。"
                improvement = "补充句号后，句意边界明确，文章结尾更加完整。"
            elif issue.issue_type == "long_sentence" and original_sentence:
                comma_positions = [index for index, char in enumerate(original_sentence) if char in "，；"]
                if comma_positions:
                    split_at = min(comma_positions, key=lambda index: abs(index - len(original_sentence) / 2))
                    rewritten_sentence = original_sentence[:split_at] + "。" + original_sentence[split_at + 1 :].lstrip()
                    rationale = "本句包含的信息过多，多个动作或观点挤在同一句中，层次不够清楚。"
                    improvement = "在语意转折处拆句后，信息层次更清晰，读者更容易把握重点。"
            # A token detector can locate suspicious text but cannot infer a
            # trustworthy replacement. Do not turn its guesses into no-op
            # rewrites or generic advice.
            if rewritten_sentence is None and replacement is not None:
                relative_start = issue.start - sentence_start
                relative_end = issue.end - sentence_start
                if 0 <= relative_start <= relative_end <= len(original_sentence):
                    rewritten_sentence = (
                        original_sentence[:relative_start] + replacement + original_sentence[relative_end:]
                    )
            if rewritten_sentence is None or rewritten_sentence.strip() == original_sentence.strip():
                continue
            suggestions.append(
                RewriteSuggestion(
                    issue_id=issue.id,
                    original=original_sentence,
                    rewrite=rewritten_sentence,
                    rationale=rationale,
                    improvement=improvement,
                    issue_text=issue_text,
                    paragraph_index=paragraph,
                    sentence_index=sentence,
                    start=issue.start,
                    end=issue.end,
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


class OpenAICompatibleProvider(AnalysisProvider):
    def __init__(self, settings: Settings, fallback: AnalysisProvider):
        self.settings = settings
        self.fallback = fallback

    def analyze(self, essay_id: str, title: str, prompt: str, content: str, examples: list[ExampleOut]) -> AnalysisReport:
        started = time.perf_counter()
        if not self.settings.ai_base_url or not self.settings.ai_api_key:
            report = self.fallback.analyze(essay_id, title, prompt, content, examples)
            return self._mark_fallback(report, "AI_BASE_URL or AI_API_KEY is not configured", started)

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
            with urllib.request.urlopen(request, timeout=self.settings.ai_timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
            content_json = response_data["choices"][0]["message"]["content"].strip()
            if content_json.startswith("```"):
                content_json = content_json.split("\n", 1)[-1]
                content_json = content_json.rsplit("```", 1)[0].strip()
            candidate = json.loads(content_json)
            correction = LLMCorrectionResult.model_validate(candidate)
            # Identity, local examples, and provider metadata are authoritative
            # backend data rather than fields the model should invent.
            report = AnalysisReport(
                essay_id=essay_id,
                title=title,
                prompt=prompt,
                grammar_issues=correction.grammar_issues,
                coherence=correction.coherence,
                relevance=correction.relevance,
                total_score=correction.total_score,
                max_score=correction.max_score,
                dimensions=correction.dimensions,
                suggestions=self._sanitize_suggestions(content, correction.suggestions),
                materials=correction.materials,
                examples=examples[:2],
                provider=ProviderMeta(
                    provider="openai-compatible",
                    model=self.settings.ai_model,
                    version="chat-completions-v1",
                    latency_ms=0,
                    fallback_used=False,
                    errors=[],
                ),
            )
            report.provider.latency_ms = int((time.perf_counter() - started) * 1000)
            return report
        except (KeyError, ValueError, urllib.error.URLError, TimeoutError, ValidationError) as exc:
            report = self.fallback.analyze(essay_id, title, prompt, content, examples)
            return self._mark_fallback(report, f"LLM schema validation or request failed: {exc}", started)

    def _mark_fallback(self, report: AnalysisReport, reason: str, started: float) -> AnalysisReport:
        fallback_provider = report.provider.provider
        fallback_model = report.provider.model
        report.provider.provider = "openai-compatible"
        report.provider.model = self.settings.ai_model
        report.provider.version = f"fallback-to-{fallback_provider}:{fallback_model}"
        report.provider.latency_ms = int((time.perf_counter() - started) * 1000)
        report.provider.fallback_used = True
        report.provider.errors.append(
            f"{reason}; fallback provider={fallback_provider}, model={fallback_model}"
        )
        return report

    @staticmethod
    def _sanitize_suggestions(content: str, suggestions: list[RewriteSuggestion]) -> list[RewriteSuggestion]:
        cleaned: list[RewriteSuggestion] = []
        seen: set[tuple[int, int, str]] = set()
        generic_reasons = (
            "结合上下文检查",
            "检查词语搭配、成分完整性或语序",
            "并重点核实该处",
        )
        for suggestion in suggestions:
            supplied_original = suggestion.original.strip()
            supplied_issue_text = suggestion.issue_text.strip()
            proposed_rewrite = suggestion.rewrite.strip()
            rationale = suggestion.rationale.strip()
            if (
                not supplied_original
                or not proposed_rewrite
                or supplied_original == proposed_rewrite
                or len(rationale) < 6
                or any(reason in rationale for reason in generic_reasons)
            ):
                continue
            start, end = suggestion.start, suggestion.end
            if supplied_issue_text and 0 <= start < end <= len(content) and content[start:end].strip() == supplied_issue_text:
                issue_text = content[start:end]
            elif 0 <= start < end <= len(content) and content[start:end].strip() == supplied_original:
                issue_text = content[start:end]
            else:
                # Legacy reports often contain an unpositioned single-character guess.
                # Its first occurrence is not a trustworthy location, so do not invent one.
                if len(supplied_original) < 2 or content.count(supplied_original) != 1:
                    continue
                fragment_start = content.find(supplied_original)
                if fragment_start < 0:
                    continue
                start = fragment_start
                end = start + len(supplied_original)
                issue_text = content[start:end]
            if start < 0 or end <= start:
                continue
            paragraph, sentence, sentence_start, _sentence_end, original_sentence = locate_sentence(content, start, end)
            if not original_sentence:
                continue
            if supplied_original == original_sentence.strip():
                rewritten_sentence = proposed_rewrite
            else:
                relative_start = start - sentence_start
                relative_end = end - sentence_start
                if not (0 <= relative_start <= relative_end <= len(original_sentence)):
                    continue
                rewritten_sentence = (
                    original_sentence[:relative_start] + proposed_rewrite + original_sentence[relative_end:]
                )
            if rewritten_sentence.strip() == original_sentence.strip():
                continue
            key = (start, end, rewritten_sentence)
            if key in seen:
                continue
            seen.add(key)
            suggestion.start = start
            suggestion.end = end
            suggestion.original = original_sentence
            suggestion.rewrite = rewritten_sentence
            suggestion.rationale = rationale
            suggestion.issue_text = issue_text
            suggestion.paragraph_index = paragraph
            suggestion.sentence_index = sentence
            if not suggestion.improvement.strip():
                suggestion.improvement = "修改后语句表达更准确，结构更清晰，也更便于读者理解。"
            cleaned.append(suggestion)
            if len(cleaned) >= 8:
                break
        return cleaned

    def _request_payload(self, title: str, prompt: str, content: str) -> dict[str, Any]:
        schema_hint = json.dumps(LLMCorrectionResult.model_json_schema(), ensure_ascii=False)
        return {
            "model": self.settings.ai_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是中文作文批改引擎。只返回一个完整、合法的 JSON 对象，不要使用 Markdown，"
                        "不要输出 schema 中没有的字段。即使没有语病，也要返回空数组。总分与各维度"
                        "分数必须一致，语病位置必须对应作文中的字符下标。改写建议宁缺毋滥，只能针对"
                        "能够确认的明确错误；original 必须是原文中的连续片段，rewrite 必须与 original"
                        "不同，start/end 必须精确对应字符位置，rationale 必须说明该处具体错误和修改原因；"
                        "improvement 必须具体说明改写后在准确性、清晰度或表达效果上好在哪里。"
                        "建议必须提供完整句子的改写，不得只返回单个字的同义替换。"
                        "禁止输出泛泛的“结合上下文检查”类建议。严格遵循此 JSON Schema："
                        f"{schema_hint}"
                    ),
                },
                {"role": "user", "content": f"题目：{title}\n要求：{prompt}\n作文：{content}"},
            ],
            "temperature": 0.2,
            "max_tokens": 3000,
            "response_format": {"type": "json_object"},
        }


def build_provider(settings: Settings, provider_name: str | None = None) -> AnalysisProvider:
    fallback = MockRuleProvider()
    selected_provider = provider_name or settings.ai_provider
    if selected_provider == "local-nlp":
        from .local_nlp import LocalNLPProvider

        return LocalNLPProvider(settings)
    if selected_provider == "openai-compatible":
        # Keep the external API fully supported. When local NLP dependencies
        # are available it also provides a more capable deterministic fallback.
        try:
            from .local_nlp import LocalNLPProvider

            fallback = LocalNLPProvider(settings)
        except Exception:
            pass
        return OpenAICompatibleProvider(settings=settings, fallback=fallback)
    return fallback
