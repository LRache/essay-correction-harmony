from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["student", "teacher"]
JobStatus = Literal["queued", "running", "completed", "failed"]


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str
    role: Role


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: UserOut


class WritingPromptCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=500)


class WritingPromptOut(BaseModel):
    id: str
    title: str
    prompt: str
    created_by: str
    created_at: str
    updated_at: str


class EssayCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=10, max_length=8000)
    prompt_id: str | None = None


class EssayOut(BaseModel):
    id: str
    prompt_id: str | None
    title: str
    prompt: str
    content: str
    student_id: str
    status: str
    created_at: str
    updated_at: str


class GrammarIssue(BaseModel):
    id: str
    start: int
    end: int
    issue_type: str
    severity: Literal["low", "medium", "high"]
    message: str
    suggestion: str


class ScoreDimension(BaseModel):
    name: str
    score: float
    max_score: float
    comment: str


class SemanticMetric(BaseModel):
    score: float
    summary: str
    evidence: list[str]


class RewriteSuggestion(BaseModel):
    issue_id: str
    original: str
    rewrite: str
    rationale: str


class MaterialSuggestion(BaseModel):
    theme: str
    material: str
    usage_tip: str


class ExampleOut(BaseModel):
    id: str
    title: str
    prompt: str
    content: str
    theme: str
    highlights: list[str]


class ProviderMeta(BaseModel):
    provider: str
    model: str
    version: str
    latency_ms: int
    fallback_used: bool
    errors: list[str]


class AnalysisReport(BaseModel):
    essay_id: str
    title: str
    prompt: str
    grammar_issues: list[GrammarIssue]
    coherence: SemanticMetric
    relevance: SemanticMetric
    total_score: float
    max_score: float
    dimensions: list[ScoreDimension]
    suggestions: list[RewriteSuggestion]
    materials: list[MaterialSuggestion]
    examples: list[ExampleOut]
    provider: ProviderMeta


class ReportOverview(BaseModel):
    essay_id: str
    prompt_id: str | None
    prompt_title: str
    title: str
    submitted_at: str
    status: str
    total_score: float
    max_score: float
    provider: str
    latency_ms: int


class AnalysisJobCreate(BaseModel):
    provider: Literal["mock", "openai-compatible"] = "openai-compatible"


class AnalysisJobOut(BaseModel):
    id: str
    essay_id: str
    status: JobStatus
    provider: str
    model: str
    started_at: str
    finished_at: str | None
    latency_ms: int
    error: str | None


class TeacherEssayOut(BaseModel):
    essay: EssayOut
    latest_job: AnalysisJobOut | None
    report_available: bool
    teacher_review: "TeacherReviewOut | None"


class TeacherReviewRequest(BaseModel):
    score: float = Field(ge=0, le=100)
    comment: str = Field(min_length=1, max_length=2000)
    annotations: list[str] = Field(default_factory=list)


class TeacherReviewOut(BaseModel):
    id: str
    essay_id: str
    teacher_id: str
    score: float
    comment: str
    annotations: list[str]
    created_at: str
    updated_at: str


TeacherEssayOut.model_rebuild()
