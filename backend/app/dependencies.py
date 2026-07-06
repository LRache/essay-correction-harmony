from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status

from .db import Database
from .schemas import UserOut
from .security import decode_token


def get_db(request: Request) -> Database:
    return request.app.state.db


def current_user(
    request: Request,
    db: Database = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> UserOut:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token, request.app.state.settings.jwt_secret)
    user_id = str(payload.get("sub", ""))
    row = db.one("SELECT id, username, display_name, role FROM users WHERE id = ?", (user_id,))
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return UserOut(id=row["id"], username=row["username"], display_name=row["display_name"], role=row["role"])


def teacher_user(user: UserOut = Depends(current_user)) -> UserOut:
    if user.role != "teacher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher role required")
    return user

