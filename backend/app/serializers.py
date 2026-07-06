from __future__ import annotations

import json
import sqlite3

from .schemas import AnalysisJobOut, EssayOut, ExampleOut, TeacherReviewOut, WritingPromptOut


def essay_from_row(row: sqlite3.Row) -> EssayOut:
    return EssayOut(
        id=row["id"],
        prompt_id=row["prompt_id"],
        title=row["title"],
        prompt=row["prompt"],
        content=row["content"],
        student_id=row["student_id"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def writing_prompt_from_row(row: sqlite3.Row) -> WritingPromptOut:
    return WritingPromptOut(
        id=row["id"],
        title=row["title"],
        prompt=row["prompt"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def job_from_row(row: sqlite3.Row) -> AnalysisJobOut:
    return AnalysisJobOut(
        id=row["id"],
        essay_id=row["essay_id"],
        status=row["status"],
        provider=row["provider"],
        model=row["model"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        latency_ms=row["latency_ms"],
        error=row["error"],
    )


def example_from_row(row: sqlite3.Row) -> ExampleOut:
    return ExampleOut(
        id=row["id"],
        title=row["title"],
        prompt=row["prompt"],
        content=row["content"],
        theme=row["theme"],
        highlights=json.loads(row["highlights_json"]),
    )


def review_from_row(row: sqlite3.Row | None) -> TeacherReviewOut | None:
    if row is None:
        return None
    return TeacherReviewOut(
        id=row["id"],
        essay_id=row["essay_id"],
        teacher_id=row["teacher_id"],
        score=row["score"],
        comment=row["comment"],
        annotations=json.loads(row["annotations_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
