from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status

from ..db import Database, utc_now
from ..dependencies import get_db, teacher_user
from ..schemas import TeacherEssayOut, TeacherReviewOut, TeacherReviewRequest, UserOut, WritingPromptCreate, WritingPromptOut
from ..serializers import essay_from_row, job_from_row, review_from_row, writing_prompt_from_row

router = APIRouter(prefix="/teacher", tags=["teacher"])


@router.post("/prompts", response_model=WritingPromptOut)
def create_writing_prompt(
    payload: WritingPromptCreate,
    db: Database = Depends(get_db),
    user: UserOut = Depends(teacher_user),
) -> WritingPromptOut:
    now = utc_now()
    prompt_id = db.new_id()
    db.execute(
        """
        INSERT INTO writing_prompts(id, title, prompt, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (prompt_id, payload.title, payload.prompt, user.id, now, now),
    )
    row = db.one("SELECT * FROM writing_prompts WHERE id = ?", (prompt_id,))
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Writing prompt missing")
    return writing_prompt_from_row(row)


@router.get("/essays", response_model=list[TeacherEssayOut])
def list_teacher_essays(
    db: Database = Depends(get_db),
    _: UserOut = Depends(teacher_user),
) -> list[TeacherEssayOut]:
    rows = db.all("SELECT * FROM essays ORDER BY created_at DESC")
    result: list[TeacherEssayOut] = []
    for row in rows:
        essay = essay_from_row(row)
        job_row = db.one("SELECT * FROM analysis_jobs WHERE essay_id = ? ORDER BY started_at DESC LIMIT 1", (essay.id,))
        report_row = db.one("SELECT id FROM reports WHERE essay_id = ? LIMIT 1", (essay.id,))
        review_row = db.one("SELECT * FROM teacher_reviews WHERE essay_id = ?", (essay.id,))
        result.append(
            TeacherEssayOut(
                essay=essay,
                latest_job=job_from_row(job_row) if job_row is not None else None,
                report_available=report_row is not None,
                teacher_review=review_from_row(review_row),
            )
        )
    return result


@router.post("/essays/{essay_id}/review", response_model=TeacherReviewOut)
def review_essay(
    essay_id: str,
    payload: TeacherReviewRequest,
    db: Database = Depends(get_db),
    user: UserOut = Depends(teacher_user),
) -> TeacherReviewOut:
    essay_row = db.one("SELECT id FROM essays WHERE id = ?", (essay_id,))
    if essay_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Essay not found")

    now = utc_now()
    existing = db.one("SELECT * FROM teacher_reviews WHERE essay_id = ?", (essay_id,))
    annotations_json = json.dumps(payload.annotations, ensure_ascii=False)
    if existing is None:
        review_id = db.new_id()
        db.execute(
            """
            INSERT INTO teacher_reviews(id, essay_id, teacher_id, score, comment, annotations_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (review_id, essay_id, user.id, payload.score, payload.comment, annotations_json, now, now),
        )
    else:
        review_id = existing["id"]
        db.execute(
            """
            UPDATE teacher_reviews
            SET teacher_id = ?, score = ?, comment = ?, annotations_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (user.id, payload.score, payload.comment, annotations_json, now, review_id),
        )
    db.execute("UPDATE essays SET status = ?, updated_at = ? WHERE id = ?", ("teacher_reviewed", now, essay_id))
    row = db.one("SELECT * FROM teacher_reviews WHERE id = ?", (review_id,))
    return_value = review_from_row(row)
    if return_value is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Teacher review missing")
    return return_value
