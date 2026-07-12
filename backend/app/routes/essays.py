from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..analysis import AnalysisProvider, build_provider
from ..db import Database, utc_now
from ..dependencies import current_user, get_db
from ..schemas import AnalysisJobCreate, AnalysisJobOut, AnalysisReport, EssayCreate, EssayOut, ExampleOut, ReportOverview, UserOut, WritingPromptOut
from ..serializers import essay_from_row, example_from_row, job_from_row, review_from_row, writing_prompt_from_row

router = APIRouter(tags=["essays"])


def _normalize_legacy_external_fallback(report: AnalysisReport) -> AnalysisReport:
    """Keep reports created before fallback metadata preserved the requested provider."""
    if (
        report.provider.fallback_used
        and report.provider.provider == "local-nlp"
        and any("LLM schema validation or request failed" in error for error in report.provider.errors)
    ):
        report.provider.provider = "openai-compatible"
        report.provider.version = f"fallback-to-local-nlp:{report.provider.model}"
    return report


def _clean_legacy_suggestions(report: AnalysisReport, content: str) -> AnalysisReport:
    """Normalize persisted suggestions and replace obsolete placeholder comments."""
    from ..analysis.providers import OpenAICompatibleProvider, RuleSupportProvider

    report.suggestions = OpenAICompatibleProvider._sanitize_suggestions(content, report.suggestions)
    placeholder_comments = (
        "依据篇幅和素材展开度估算",
        "首版由规则特征映射",
        "依据规则检测问题数量估算",
    )
    if any(not item.comment.strip() or any(text in item.comment for text in placeholder_comments) for item in report.dimensions):
        actionable_issues = [issue for issue in report.grammar_issues if issue.issue_type != "bert_grammar"]
        generated = RuleSupportProvider()._dimensions(
            report.prompt,
            content,
            actionable_issues,
            report.coherence.score,
            report.relevance.score,
        )
        generated_comments = {item.name: item.comment for item in generated}
        for item in report.dimensions:
            if not item.comment.strip() or any(text in item.comment for text in placeholder_comments):
                item.comment = generated_comments.get(item.name, item.comment)
    return report


def _load_essay_or_404(db: Database, essay_id: str, user: UserOut) -> EssayOut:
    row = db.one("SELECT * FROM essays WHERE id = ?", (essay_id,))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Essay not found")
    essay = essay_from_row(row)
    if user.role == "teacher":
        class_row = db.one(
            """
            SELECT cm.id
            FROM class_members cm
            JOIN classes c ON c.id = cm.class_id
            JOIN writing_prompts wp ON wp.id = ?
            WHERE cm.student_id = ? AND c.teacher_id = ?
              AND wp.created_by = c.teacher_id
            LIMIT 1
            """,
            (essay.prompt_id, essay.student_id, user.id),
        )
        if class_row is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Essay is not visible to this user")
    elif essay.student_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Essay is not visible to this user")
    return essay


@router.post("/essays", response_model=EssayOut)
def create_essay(
    payload: EssayCreate,
    db: Database = Depends(get_db),
    user: UserOut = Depends(current_user),
) -> EssayOut:
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can submit essays")
    now = utc_now()
    essay_id = db.new_id()
    prompt_id = payload.prompt_id
    title = payload.title
    prompt = payload.prompt
    if prompt_id is not None:
        prompt_row = db.one("SELECT * FROM writing_prompts WHERE id = ?", (prompt_id,))
        if prompt_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Writing prompt not found")
        class_row = db.one(
            """
            SELECT cm.id
            FROM class_members cm
            JOIN classes c ON c.id = cm.class_id
            WHERE cm.student_id = ? AND c.teacher_id = ?
            LIMIT 1
            """,
            (user.id, prompt_row["created_by"]),
        )
        if class_row is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Writing prompt is not visible to this student")
        title = prompt_row["title"]
        prompt = prompt_row["prompt"]
    db.execute(
        """
        INSERT INTO essays(id, prompt_id, title, prompt, content, student_id, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (essay_id, prompt_id, title, prompt, payload.content, user.id, "submitted", now, now),
    )
    return _load_essay_or_404(db, essay_id, user)


@router.get("/essays/{essay_id}", response_model=EssayOut)
def get_essay(
    essay_id: str,
    db: Database = Depends(get_db),
    user: UserOut = Depends(current_user),
) -> EssayOut:
    return _load_essay_or_404(db, essay_id, user)


@router.get("/writing-prompts", response_model=list[WritingPromptOut])
def list_writing_prompts(
    db: Database = Depends(get_db),
    user: UserOut = Depends(current_user),
) -> list[WritingPromptOut]:
    if user.role == "teacher":
        rows = db.all(
            "SELECT * FROM writing_prompts WHERE created_by = ? ORDER BY created_at DESC, title",
            (user.id,),
        )
    else:
        rows = db.all(
            """
            SELECT DISTINCT wp.*
            FROM writing_prompts wp
            JOIN classes c ON c.teacher_id = wp.created_by
            JOIN class_members cm ON cm.class_id = c.id
            WHERE cm.student_id = ?
            ORDER BY wp.created_at DESC, wp.title
            """,
            (user.id,),
        )
    return [writing_prompt_from_row(row) for row in rows]


@router.post("/essays/{essay_id}/analysis-jobs", response_model=AnalysisJobOut)
def create_analysis_job(
    essay_id: str,
    request: Request,
    payload: AnalysisJobCreate | None = None,
    db: Database = Depends(get_db),
    user: UserOut = Depends(current_user),
) -> AnalysisJobOut:
    essay = _load_essay_or_404(db, essay_id, user)
    settings = request.app.state.settings
    requested_provider = payload.provider if payload is not None else settings.ai_provider
    requested_model = settings.local_bert_model if requested_provider == "local-nlp" else settings.ai_model
    providers: dict[str, AnalysisProvider] = request.app.state.analysis_providers
    provider = providers.get(requested_provider)
    if provider is None:
        provider = build_provider(settings, requested_provider)
        providers[requested_provider] = provider
    started_at = utc_now()
    job_id = db.new_id()
    db.execute(
        """
        INSERT INTO analysis_jobs(id, essay_id, status, provider, model, started_at, latency_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (job_id, essay_id, "running", requested_provider, requested_model, started_at, 0),
    )

    examples = [example_from_row(row) for row in db.all("SELECT * FROM examples ORDER BY theme, title LIMIT 2")]
    try:
        report = provider.analyze(essay.id, essay.title, essay.prompt, essay.content, examples)
        finished_at = utc_now()
        db.execute(
            """
            UPDATE analysis_jobs
            SET status = ?, finished_at = ?, latency_ms = ?, error = ?
            WHERE id = ?
            """,
            ("completed", finished_at, report.provider.latency_ms, None, job_id),
        )
        db.execute(
            """
            INSERT INTO reports(id, essay_id, job_id, data_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (db.new_id(), essay_id, job_id, report.model_dump_json(), finished_at),
        )
        db.execute("UPDATE essays SET status = ?, updated_at = ? WHERE id = ?", ("analyzed", finished_at, essay_id))
    except Exception as exc:
        finished_at = utc_now()
        db.execute(
            """
            UPDATE analysis_jobs
            SET status = ?, finished_at = ?, error = ?
            WHERE id = ?
            """,
            ("failed", finished_at, str(exc), job_id),
        )
    row = db.one("SELECT * FROM analysis_jobs WHERE id = ?", (job_id,))
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Analysis job missing")
    return job_from_row(row)


@router.get("/analysis-jobs/{job_id}", response_model=AnalysisJobOut)
def get_analysis_job(
    job_id: str,
    db: Database = Depends(get_db),
    user: UserOut = Depends(current_user),
) -> AnalysisJobOut:
    row = db.one("SELECT * FROM analysis_jobs WHERE id = ?", (job_id,))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found")
    essay = _load_essay_or_404(db, row["essay_id"], user)
    if essay.id != row["essay_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found")
    return job_from_row(row)


@router.get("/essays/{essay_id}/report", response_model=AnalysisReport)
def get_report(
    essay_id: str,
    db: Database = Depends(get_db),
    user: UserOut = Depends(current_user),
) -> AnalysisReport:
    essay = _load_essay_or_404(db, essay_id, user)
    row = db.one("SELECT data_json FROM reports WHERE essay_id = ? ORDER BY created_at DESC LIMIT 1", (essay_id,))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    report = AnalysisReport.model_validate(json.loads(row["data_json"]))
    report = _normalize_legacy_external_fallback(report)
    return _clean_legacy_suggestions(report, essay.content)


@router.get("/reports", response_model=list[ReportOverview])
def list_reports(
    db: Database = Depends(get_db),
    user: UserOut = Depends(current_user),
) -> list[ReportOverview]:
    if user.role == "teacher":
        essay_rows = db.all(
            """
            SELECT DISTINCT e.*
            FROM essays e
            JOIN writing_prompts wp ON wp.id = e.prompt_id
            JOIN class_members cm ON cm.student_id = e.student_id
            JOIN classes c ON c.id = cm.class_id
            WHERE c.teacher_id = ? AND wp.created_by = ?
            ORDER BY e.created_at DESC
            """,
            (user.id, user.id),
        )
    else:
        essay_rows = db.all("SELECT * FROM essays WHERE student_id = ? ORDER BY created_at DESC", (user.id,))

    reports: list[ReportOverview] = []
    for essay_row in essay_rows:
        essay = essay_from_row(essay_row)
        report_row = db.one(
            "SELECT data_json FROM reports WHERE essay_id = ? ORDER BY created_at DESC LIMIT 1",
            (essay.id,),
        )
        if report_row is None:
            continue
        report = _normalize_legacy_external_fallback(AnalysisReport.model_validate(json.loads(report_row["data_json"])))
        review_row = db.one("SELECT * FROM teacher_reviews WHERE essay_id = ?", (essay.id,))
        reports.append(
            ReportOverview(
                essay_id=essay.id,
                prompt_id=essay.prompt_id,
                prompt_title=essay.title,
                title=essay.title,
                submitted_at=essay.created_at,
                status=essay.status,
                total_score=report.total_score,
                max_score=report.max_score,
                provider=report.provider.provider,
                latency_ms=report.provider.latency_ms,
                teacher_review=review_from_row(review_row),
            )
        )
    return reports
