from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status

from ..db import Database, utc_now
from ..dependencies import current_user, get_db, teacher_user
from ..schemas import ClassCreate, ClassJoinRequest, ClassMemberOut, ClassOut, UserOut
from ..serializers import class_from_row, class_member_from_row

router = APIRouter(prefix="/classes", tags=["classes"])


def _new_invite_code(db: Database) -> str:
    for _ in range(8):
        code = secrets.token_hex(3).upper()
        if db.one("SELECT id FROM classes WHERE invite_code = ?", (code,)) is None:
            return code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invite code generation failed")


def _class_with_count(db: Database, class_id: str) -> ClassOut:
    row = db.one(
        """
        SELECT c.*, COUNT(cm.id) AS student_count
        FROM classes c
        LEFT JOIN class_members cm ON cm.class_id = c.id
        WHERE c.id = ?
        GROUP BY c.id
        """,
        (class_id,),
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return class_from_row(row)


@router.get("", response_model=list[ClassOut])
def list_classes(
    db: Database = Depends(get_db),
    user: UserOut = Depends(current_user),
) -> list[ClassOut]:
    if user.role == "teacher":
        rows = db.all(
            """
            SELECT c.*, COUNT(cm.id) AS student_count
            FROM classes c
            LEFT JOIN class_members cm ON cm.class_id = c.id
            WHERE c.teacher_id = ?
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """,
            (user.id,),
        )
    else:
        rows = db.all(
            """
            SELECT c.*, COUNT(cm_all.id) AS student_count
            FROM classes c
            JOIN class_members cm ON cm.class_id = c.id AND cm.student_id = ?
            LEFT JOIN class_members cm_all ON cm_all.class_id = c.id
            GROUP BY c.id
            ORDER BY cm.joined_at DESC
            """,
            (user.id,),
        )
    return [class_from_row(row) for row in rows]


@router.post("", response_model=ClassOut)
def create_class(
    payload: ClassCreate,
    db: Database = Depends(get_db),
    user: UserOut = Depends(teacher_user),
) -> ClassOut:
    now = utc_now()
    class_id = db.new_id()
    invite_code = _new_invite_code(db)
    db.execute(
        """
        INSERT INTO classes(id, name, invite_code, teacher_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (class_id, payload.name, invite_code, user.id, now, now),
    )
    return _class_with_count(db, class_id)


@router.get("/{class_id}/students", response_model=list[ClassMemberOut])
def list_class_students(
    class_id: str,
    db: Database = Depends(get_db),
    user: UserOut = Depends(teacher_user),
) -> list[ClassMemberOut]:
    class_row = db.one("SELECT id FROM classes WHERE id = ? AND teacher_id = ?", (class_id, user.id))
    if class_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    rows = db.all(
        """
        SELECT u.id, u.username, u.display_name, cm.joined_at
        FROM class_members cm
        JOIN users u ON u.id = cm.student_id
        WHERE cm.class_id = ?
        ORDER BY cm.joined_at DESC
        """,
        (class_id,),
    )
    return [class_member_from_row(row) for row in rows]


@router.post("/join", response_model=ClassOut)
def join_class(
    payload: ClassJoinRequest,
    db: Database = Depends(get_db),
    user: UserOut = Depends(current_user),
) -> ClassOut:
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can join classes")
    invite_code = payload.invite_code.strip().upper()
    class_row = db.one("SELECT id FROM classes WHERE invite_code = ?", (invite_code,))
    if class_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class invite code not found")
    class_id = class_row["id"]
    existing = db.one(
        "SELECT id FROM class_members WHERE class_id = ? AND student_id = ?",
        (class_id, user.id),
    )
    if existing is None:
        db.execute(
            """
            INSERT INTO class_members(id, class_id, student_id, joined_at)
            VALUES (?, ?, ?, ?)
            """,
            (db.new_id(), class_id, user.id, utc_now()),
        )
    return _class_with_count(db, class_id)
