from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from ..config import Settings
from ..schemas import (
    AnalysisReport,
    ExampleOut,
    GrammarIssue,
    ProviderMeta,
    SemanticMetric,
)
from .providers import AnalysisProvider, RuleSupportProvider


@dataclass
class SemanticScores:
    coherence: float
    relevance: float
    engine: str
    errors: list[str]


class NltkChineseGrammarChecker:
    """NLTK-backed sentence segmentation plus auditable Chinese grammar rules.

    NLTK does not ship a Chinese grammar model. It is therefore used for the
    tokenization pipeline while deterministic Chinese patterns produce stable,
    character-level annotations that can be evaluated against a labelled set.
    """

    _patterns = [
        (r"的的|地地|得得", "duplicate_particle", "助词疑似重复。", "删除重复的助词。", "medium"),
        (r"[，。！？；：]{2,}", "duplicate_punctuation", "标点符号疑似重复。", "保留一个合适的标点符号。", "low"),
        (r"通过[^。！？]{0,30}使", "missing_subject", "“通过……使……”可能造成主语缺失。", "删去“通过”或“使”，补出明确主语。", "high"),
        (r"避免[^。！？]{0,20}不", "double_negative", "“避免……不……”可能造成否定不当。", "根据句意删除“不”或改写“避免”。", "high"),
        (r"是否[^。！？]{0,30}是", "two_sided_mismatch", "“是否”与单向判断词“是”可能搭配不当。", "将“是”改为“是否”，或删除前面的“是否”。", "medium"),
        (r"(?:大约|约)[^，。！？]{0,12}左右", "redundant_approximation", "约数表达重复。", "删除“大约/约”或“左右”中的一个。", "medium"),
    ]

    def __init__(self) -> None:
        self.nltk_available = False
        self._tokenizer: Any = None
        try:
            from nltk.tokenize import RegexpTokenizer

            self._tokenizer = RegexpTokenizer(r"[^。！？]+[。！？]?")
            self.nltk_available = True
        except ImportError:
            self._tokenizer = None

    def sentences(self, text: str) -> list[str]:
        if self._tokenizer is not None:
            return [part.strip() for part in self._tokenizer.tokenize(text) if part.strip()]
        return [part.strip() for part in re.findall(r"[^。！？]+[。！？]?", text) if part.strip()]

    def check(self, text: str) -> list[GrammarIssue]:
        # Calling the tokenizer is deliberately part of the grammar pipeline,
        # even for rules that inspect the original text for exact offsets.
        sentences = self.sentences(text)
        issues: list[GrammarIssue] = []
        seen: set[tuple[int, int, str]] = set()
        for pattern, issue_type, message, suggestion, severity in self._patterns:
            for match in re.finditer(pattern, text):
                key = (match.start(), match.end(), issue_type)
                if key in seen:
                    continue
                seen.add(key)
                issues.append(
                    GrammarIssue(
                        id=f"nltk-{issue_type}-{match.start()}",
                        start=match.start(),
                        end=match.end(),
                        issue_type=issue_type,
                        severity=severity,
                        message=message,
                        suggestion=suggestion,
                    )
                )

        cursor = 0
        for index, sentence in enumerate(sentences):
            start = text.find(sentence, cursor)
            if start < 0:
                continue
            end = start + len(sentence)
            cursor = end
            body_length = len(sentence.rstrip("。！？"))
            if body_length > 90:
                issues.append(
                    GrammarIssue(
                        id=f"nltk-long-sentence-{index}-{start}",
                        start=start,
                        end=end,
                        issue_type="long_sentence",
                        severity="medium",
                        message="句子过长，句法关系可能不清晰。",
                        suggestion="按动作、转折或因果关系拆分句子。",
                    )
                )
        if text.strip() and text.rstrip()[-1] not in "。！？":
            end = len(text.rstrip())
            issues.append(
                GrammarIssue(
                    id="nltk-missing-final-punctuation",
                    start=max(0, end - 1),
                    end=end,
                    issue_type="punctuation",
                    severity="low",
                    message="文章末尾缺少句末标点。",
                    suggestion="在文章末尾补充句号、问号或感叹号。",
                )
            )
        return sorted(issues, key=lambda item: (item.start, item.end, item.issue_type))


class BertSemanticAnalyzer:
    _cache: dict[tuple[str, bool], tuple[Any, Any, Any]] = {}
    _lock = Lock()

    def __init__(self, settings: Settings, checker: NltkChineseGrammarChecker):
        self.model_name = settings.local_bert_model
        self.files_only = settings.local_model_files_only
        self.checker = checker

    def analyze(self, prompt: str, content: str) -> SemanticScores:
        try:
            tokenizer, model, torch = self._load_model()
            sentences = self.checker.sentences(content)
            parts = sentences[:12] or [content]
            vectors = [self._embed(part, tokenizer, model, torch) for part in parts]
            prompt_vector = self._embed(prompt, tokenizer, model, torch)
            content_vector = self._embed(content[:1800], tokenizer, model, torch)
            coherence_values = [self._cosine(vectors[i], vectors[i + 1], torch) for i in range(len(vectors) - 1)]
            # A single sentence provides no evidence of discourse coherence.
            # Keep it neutral-low instead of awarding the old implicit 86/100.
            coherence_raw = sum(coherence_values) / len(coherence_values) if coherence_values else 0.10
            relevance_raw = self._cosine(prompt_vector, content_vector, torch)
            return SemanticScores(
                coherence=round(self._normalize_similarity(coherence_raw), 1),
                relevance=round(self._normalize_similarity(relevance_raw), 1),
                engine=f"huggingface:{self.model_name}",
                errors=[],
            )
        except Exception as exc:
            coherence, relevance = self._lexical_fallback(prompt, content)
            return SemanticScores(
                coherence=coherence,
                relevance=relevance,
                engine="lexical-fallback",
                errors=[f"BERT unavailable: {type(exc).__name__}: {exc}"],
            )

    def warmup(self) -> None:
        """Load model weights before serving requests so latency excludes cold start."""
        self._load_model()

    def _load_model(self) -> tuple[Any, Any, Any]:
        key = (self.model_name, self.files_only)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
            import torch
            from transformers import AutoModel, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=self.files_only)
            model = AutoModel.from_pretrained(self.model_name, local_files_only=self.files_only)
            model.eval()
            cached = (tokenizer, model, torch)
            self._cache[key] = cached
            return cached

    @staticmethod
    def _embed(text: str, tokenizer: Any, model: Any, torch: Any) -> Any:
        encoded = tokenizer(text or "空", return_tensors="pt", truncation=True, max_length=512)
        with torch.inference_mode():
            output = model(**encoded).last_hidden_state
        mask = encoded["attention_mask"].unsqueeze(-1).expand(output.size()).float()
        return (output * mask).sum(1) / mask.sum(1).clamp(min=1e-9)

    @staticmethod
    def _cosine(left: Any, right: Any, torch: Any) -> float:
        return float(torch.nn.functional.cosine_similarity(left, right).item())

    @staticmethod
    def _normalize_similarity(value: float) -> float:
        # Chinese BERT cosine similarities tend to occupy the upper half of
        # [-1, 1]. This maps useful separation into a readable 0-100 score.
        return max(0.0, min(100.0, 50.0 + value * 50.0))

    def _lexical_fallback(self, prompt: str, content: str) -> tuple[float, float]:
        sentences = self.checker.sentences(content)
        adjacent = [self._jaccard(sentences[i], sentences[i + 1]) for i in range(len(sentences) - 1)]
        connective_hits = sum(word in content for word in ("首先", "然后", "但是", "因此", "后来", "最后", "于是"))
        coherence = 60 + min(18, connective_hits * 3)
        if adjacent:
            coherence += min(15, sum(adjacent) / len(adjacent) * 30)
        relevance = 55 + self._jaccard(prompt, content) * 100
        prompt_terms = set(re.findall(r"[\u4e00-\u9fff]{2,4}", prompt))
        relevance += min(20, sum(term in content for term in prompt_terms) * 3)
        return round(min(95, coherence), 1), round(min(96, relevance), 1)

    @staticmethod
    def _jaccard(left: str, right: str) -> float:
        def grams(value: str) -> set[str]:
            chars = "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", value))
            return {chars[i : i + 2] for i in range(max(0, len(chars) - 1))}

        left_grams, right_grams = grams(left), grams(right)
        if not left_grams or not right_grams:
            return 0.0
        return len(left_grams & right_grams) / len(left_grams | right_grams)


class BertEssayScorer:
    """Optional BERT regression head fine-tuned on human essay scores."""

    _cache: dict[str, tuple[Any, Any, Any]] = {}
    _lock = Lock()

    def __init__(self, model_path: str):
        self.model_path = str(Path(model_path).resolve()) if model_path else ""

    def available(self) -> bool:
        return bool(self.model_path) and (Path(self.model_path) / "config.json").is_file()

    def predict(self, prompt: str, content: str) -> tuple[float | None, str | None]:
        if not self.available():
            return None, "Fine-tuned essay scoring model is not installed"
        try:
            tokenizer, model, torch = self._load()
            chunks = self._chunks(content)
            encoded = tokenizer(
                [prompt] * len(chunks), chunks, return_tensors="pt",
                padding=True, truncation=True, max_length=512,
            )
            with torch.inference_mode():
                value = float(model(**encoded).logits.squeeze(-1).mean().item())
            score_mean = float(getattr(model.config, "score_mean", 0.0))
            score_std = float(getattr(model.config, "score_std", 0.0))
            score = value * score_std + score_mean if score_std > 0 else value * 100.0
            return round(max(0.0, min(100.0, score)), 1), None
        except Exception as exc:
            return None, f"Essay scorer unavailable: {type(exc).__name__}: {exc}"

    @staticmethod
    def _chunks(content: str, size: int = 420, overlap: int = 40) -> list[str]:
        if len(content) <= size:
            return [content]
        step = size - overlap
        return [content[start : start + size] for start in range(0, len(content), step) if content[start : start + size]]

    def warmup(self) -> None:
        if self.available():
            self._load()

    def _load(self) -> tuple[Any, Any, Any]:
        with self._lock:
            if self.model_path in self._cache:
                return self._cache[self.model_path]
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
            model = AutoModelForSequenceClassification.from_pretrained(self.model_path, local_files_only=True)
            model.eval()
            value = (tokenizer, model, torch)
            self._cache[self.model_path] = value
            return value


class BertGrammarDetector:
    """Character-offset grammar detector fine-tuned on source/correction pairs."""

    _cache: dict[str, tuple[Any, Any, Any]] = {}
    _lock = Lock()

    def __init__(self, model_path: str, checker: NltkChineseGrammarChecker):
        self.model_path = str(Path(model_path).resolve()) if model_path else ""
        self.checker = checker

    def available(self) -> bool:
        return bool(self.model_path) and (Path(self.model_path) / "config.json").is_file()

    def detect(self, content: str) -> tuple[list[GrammarIssue], str | None]:
        if not self.available():
            return [], "Fine-tuned grammar detector is not installed"
        try:
            tokenizer, model, torch = self._load()
            sentences = self.checker.sentences(content)[:40]
            if not sentences:
                return [], None
            encoded = tokenizer(
                sentences, padding=True, truncation=True, max_length=256,
                return_tensors="pt", return_offsets_mapping=True,
            )
            offsets = encoded.pop("offset_mapping")
            with torch.inference_mode():
                probabilities = torch.softmax(model(**encoded).logits, dim=-1)[..., 1]
            threshold = float(getattr(model.config, "error_threshold", 0.5))
            issues: list[GrammarIssue] = []
            search_cursor = 0
            for sentence_index, sentence in enumerate(sentences):
                sentence_start = content.find(sentence, search_cursor)
                if sentence_start < 0:
                    continue
                search_cursor = sentence_start + len(sentence)
                predicted_spans: list[tuple[int, int]] = []
                for token_index, probability in enumerate(probabilities[sentence_index].tolist()):
                    start, end = offsets[sentence_index][token_index].tolist()
                    if end <= start or probability < threshold:
                        continue
                    absolute = (sentence_start + start, sentence_start + end)
                    if predicted_spans and absolute[0] <= predicted_spans[-1][1]:
                        predicted_spans[-1] = (predicted_spans[-1][0], max(predicted_spans[-1][1], absolute[1]))
                    else:
                        predicted_spans.append(absolute)
                for start, end in predicted_spans:
                    issues.append(
                        GrammarIssue(
                            id=f"bert-grammar-{sentence_index}-{start}",
                            start=start,
                            end=end,
                            issue_type="bert_grammar",
                            severity="medium",
                            message="BERT 检测到此处可能存在语法或搭配问题。",
                            suggestion="结合上下文检查词语搭配、成分完整性或语序，并重写该处。",
                        )
                    )
            return issues, None
        except Exception as exc:
            return [], f"Grammar detector unavailable: {type(exc).__name__}: {exc}"

    def warmup(self) -> None:
        if self.available():
            self._load()

    def _load(self) -> tuple[Any, Any, Any]:
        with self._lock:
            if self.model_path in self._cache:
                return self._cache[self.model_path]
            import torch
            from transformers import AutoModelForTokenClassification, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True, use_fast=True)
            model = AutoModelForTokenClassification.from_pretrained(self.model_path, local_files_only=True)
            model.eval()
            value = (tokenizer, model, torch)
            self._cache[self.model_path] = value
            return value


class LocalNLPProvider(AnalysisProvider):
    version = "nltk-bert-2026-07-08"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.checker = NltkChineseGrammarChecker()
        self.semantic = BertSemanticAnalyzer(settings, self.checker)
        self.scorer = BertEssayScorer(settings.local_scoring_model)
        self.grammar_detector = BertGrammarDetector(settings.local_grammar_model, self.checker)
        self.rules = RuleSupportProvider(model="rule-support-v2")
        if settings.local_model_warmup:
            try:
                self.semantic.warmup()
                self.scorer.warmup()
                self.grammar_detector.warmup()
            except Exception:
                # The analyze call records the concrete fallback reason. Startup
                # remains available for the browser and external API paths.
                pass

    def analyze(self, essay_id: str, title: str, prompt: str, content: str, examples: list[ExampleOut]) -> AnalysisReport:
        started = time.perf_counter()
        grammar_issues = self.checker.check(content)
        learned_issues, grammar_model_error = self.grammar_detector.detect(content)
        for learned_issue in learned_issues:
            if not any(
                max(learned_issue.start, issue.start) < min(learned_issue.end, issue.end)
                for issue in grammar_issues
            ):
                grammar_issues.append(learned_issue)
        grammar_issues.sort(key=lambda item: (item.start, item.end, item.issue_type))
        scores = self.semantic.analyze(prompt, content)
        # The learned detector is intentionally recall-oriented and may still
        # produce false positives. Until a concrete rewrite can be generated,
        # those tentative spans must not lower the language score.
        actionable_issues = [issue for issue in grammar_issues if issue.issue_type != "bert_grammar"]
        dimensions = self.rules._dimensions(prompt, content, actionable_issues, scores.coherence, scores.relevance)
        predicted_score, scoring_error = self.scorer.predict(prompt, content)
        total_score = predicted_score if predicted_score is not None else round(sum(item.score for item in dimensions), 1)
        quality_cap, quality_reason = self._quality_score_cap(content)
        if quality_cap is not None and total_score > quality_cap:
            total_score = quality_cap
            dimensions[0].comment = f"有效性检查：{quality_reason}；总分最高按 {quality_cap:.0f} 分计。{dimensions[0].comment}"
        if predicted_score is not None or quality_cap is not None:
            raw_total = sum(item.score for item in dimensions) or 1
            for dimension in dimensions:
                dimension.score = round(min(dimension.max_score, dimension.score * total_score / raw_total), 1)
            difference = round(total_score - sum(item.score for item in dimensions), 1)
            dimensions[-1].score = round(max(0, min(dimensions[-1].max_score, dimensions[-1].score + difference)), 1)
        report = AnalysisReport(
            essay_id=essay_id,
            title=title,
            prompt=prompt,
            grammar_issues=grammar_issues,
            coherence=SemanticMetric(
                score=scores.coherence,
                summary="使用 BERT 句向量计算相邻句语义连贯性。" if not scores.errors else "BERT 不可用，使用可复现的词汇衔接特征降级计算。",
                evidence=[f"语义引擎：{scores.engine}", f"共分析 {len(self.checker.sentences(content))} 个句子"],
            ),
            relevance=SemanticMetric(
                score=scores.relevance,
                summary="比较作文要求与正文的 BERT 语义向量。" if not scores.errors else "使用题目关键词和字符二元组重合度降级计算。",
                evidence=self.rules._keyword_evidence(prompt, content),
            ),
            total_score=total_score,
            max_score=100,
            dimensions=dimensions,
            suggestions=self.rules._suggestions(content, actionable_issues)
            + self.rules._deep_suggestions(prompt, content),
            materials=self.rules._materials(prompt, content),
            examples=examples[:2],
            provider=ProviderMeta(
                provider="local-nlp",
                model=f"{scores.engine} + {Path(self.scorer.model_path).name if predicted_score is not None else 'feature-scorer'}",
                version=self.version,
                latency_ms=int((time.perf_counter() - started) * 1000),
                fallback_used=bool(scores.errors) or not self.checker.nltk_available or scoring_error is not None or grammar_model_error is not None,
                errors=(["NLTK is not installed; regex sentence splitter used"] if not self.checker.nltk_available else [])
                + scores.errors
                + ([grammar_model_error] if grammar_model_error else [])
                + ([scoring_error] if scoring_error else []),
            ),
        )
        return report

    @staticmethod
    def _quality_score_cap(content: str) -> tuple[float | None, str | None]:
        """Prevent an AES regressor from rewarding text outside essay-like input."""
        compact = "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", content))
        sentence_count = len([part for part in re.split(r"[。！？!?]+", content) if part.strip()])
        length = len(compact)
        if length < 60:
            return 30.0, f"正文仅约 {length} 字，未达到可评分作文的基本篇幅"
        if length < 120:
            return 50.0, f"正文仅约 {length} 字，内容展开明显不足"
        if length < 200:
            return 65.0, f"正文仅约 {length} 字，篇幅不足"
        if sentence_count <= 1:
            return 40.0, "全文只有一个句子，无法形成完整篇章结构"
        return None, None
