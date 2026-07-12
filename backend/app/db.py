from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable

from .security import password_hash


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str):
        self.path = path
        db_dir = Path(path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id TEXT PRIMARY KEY,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  display_name TEXT NOT NULL,
                  role TEXT NOT NULL CHECK(role IN ('student', 'teacher')),
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS writing_prompts (
                  id TEXT PRIMARY KEY,
                  title TEXT NOT NULL,
                  prompt TEXT NOT NULL,
                  created_by TEXT NOT NULL REFERENCES users(id),
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS classes (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  invite_code TEXT UNIQUE NOT NULL,
                  teacher_id TEXT NOT NULL REFERENCES users(id),
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS class_members (
                  id TEXT PRIMARY KEY,
                  class_id TEXT NOT NULL REFERENCES classes(id),
                  student_id TEXT NOT NULL REFERENCES users(id),
                  joined_at TEXT NOT NULL,
                  UNIQUE(class_id, student_id)
                );

                CREATE TABLE IF NOT EXISTS essays (
                  id TEXT PRIMARY KEY,
                  prompt_id TEXT,
                  title TEXT NOT NULL,
                  prompt TEXT NOT NULL,
                  content TEXT NOT NULL,
                  student_id TEXT NOT NULL REFERENCES users(id),
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analysis_jobs (
                  id TEXT PRIMARY KEY,
                  essay_id TEXT NOT NULL REFERENCES essays(id),
                  status TEXT NOT NULL,
                  provider TEXT NOT NULL,
                  model TEXT NOT NULL,
                  started_at TEXT NOT NULL,
                  finished_at TEXT,
                  latency_ms INTEGER NOT NULL DEFAULT 0,
                  error TEXT
                );

                CREATE TABLE IF NOT EXISTS reports (
                  id TEXT PRIMARY KEY,
                  essay_id TEXT NOT NULL REFERENCES essays(id),
                  job_id TEXT NOT NULL REFERENCES analysis_jobs(id),
                  data_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS teacher_reviews (
                  id TEXT PRIMARY KEY,
                  essay_id TEXT UNIQUE NOT NULL REFERENCES essays(id),
                  teacher_id TEXT NOT NULL REFERENCES users(id),
                  score REAL NOT NULL,
                  comment TEXT NOT NULL,
                  annotations_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS examples (
                  id TEXT PRIMARY KEY,
                  title TEXT NOT NULL,
                  prompt TEXT NOT NULL,
                  content TEXT NOT NULL,
                  theme TEXT NOT NULL,
                  highlights_json TEXT NOT NULL
                );
                """
            )
            self._ensure_column(conn, "essays", "prompt_id", "TEXT")
            self._seed(conn)

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
        columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if not any(row["name"] == column for row in columns):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    def _seed(self, conn: sqlite3.Connection) -> None:
        count = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        if count == 0:
            now = utc_now()
            rows = [
                (
                    "student-1",
                    "student@example.com",
                    password_hash("student123"),
                    "学生演示账号",
                    "student",
                    now,
                ),
                (
                    "teacher-1",
                    "teacher@example.com",
                    password_hash("teacher123"),
                    "教师演示账号",
                    "teacher",
                    now,
                ),
            ]
            conn.executemany(
                """
                INSERT INTO users(id, username, password_hash, display_name, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

        class_count = conn.execute("SELECT COUNT(*) AS count FROM classes").fetchone()["count"]
        teacher_exists = conn.execute("SELECT id FROM users WHERE id = ?", ("teacher-1",)).fetchone() is not None
        student_exists = conn.execute("SELECT id FROM users WHERE id = ?", ("student-1",)).fetchone() is not None
        if class_count == 0 and teacher_exists:
            now = utc_now()
            conn.execute(
                """
                INSERT INTO classes(id, name, invite_code, teacher_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("class-demo-1", "演示班级", "CLASS2026", "teacher-1", now, now),
            )

        member_count = conn.execute("SELECT COUNT(*) AS count FROM class_members").fetchone()["count"]
        demo_class_exists = conn.execute("SELECT id FROM classes WHERE id = ?", ("class-demo-1",)).fetchone() is not None
        if member_count == 0 and demo_class_exists and student_exists:
            now = utc_now()
            conn.execute(
                """
                INSERT INTO class_members(id, class_id, student_id, joined_at)
                VALUES (?, ?, ?, ?)
                """,
                ("class-member-demo-1", "class-demo-1", "student-1", now),
            )

        prompt_count = conn.execute("SELECT COUNT(*) AS count FROM writing_prompts").fetchone()["count"]
        if prompt_count == 0:
            now = utc_now()
            prompts = [
                (
                    "prompt-growth-choice",
                    "一次选择",
                    "请以成长中的一次选择为题写一篇作文。",
                    "teacher-1",
                    now,
                    now,
                ),
                (
                    "prompt-family-responsibility",
                    "亲情与责任",
                    "请围绕亲情与责任写一篇记叙文。",
                    "teacher-1",
                    now,
                    now,
                ),
            ]
            conn.executemany(
                """
                INSERT INTO writing_prompts(id, title, prompt, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                prompts,
            )

        example_count = conn.execute("SELECT COUNT(*) AS count FROM examples").fetchone()["count"]
        if example_count == 0:
            examples = [
                (
                    "example-1",
                    "把光留在心里",
                    "请以成长中的一次选择为题写一篇作文。",
                    "那天傍晚，我在教室门口停了很久。竞赛报名表只剩一张，我原本想把它留给自己，却想起同桌连续两周查资料到深夜。最后，我把报名表推到她面前。后来她获奖时，我忽然明白，成长并不是每次都站到聚光灯下，而是在能够成全别人时，仍然感到心里有光。",
                    "成长",
                    json.dumps(["细节具体", "立意清楚", "结尾点题"], ensure_ascii=False),
                ),
                (
                    "example-2",
                    "旧伞下的新路",
                    "请围绕亲情与责任写一篇记叙文。",
                    "雨落得很急，外婆撑着那把旧伞来接我。伞骨已经弯了，她却总把伞面偏向我这边。回家的路上，我第一次接过伞柄，把伞往她肩上移了移。那一刻我才发现，责任不是一句响亮的话，而是愿意在细小处替爱你的人多想一步。",
                    "亲情",
                    json.dumps(["动作描写自然", "情感递进", "主题集中"], ensure_ascii=False),
                ),
            ]
            conn.executemany(
                """
                INSERT INTO examples(id, title, prompt, content, theme, highlights_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                examples,
            )

    def one(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(query, tuple(params)).fetchone()

    def all(self, query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(query, tuple(params)).fetchall())

    def execute(self, query: str, params: Iterable[Any] = ()) -> None:
        with self.connect() as conn:
            conn.execute(query, tuple(params))

    def new_id(self) -> str:
        return str(uuid.uuid4())
