from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..db import Database
from ..dependencies import get_db
from ..schemas import LoginRequest, LoginResponse, UserOut
from ..security import create_token, password_hash

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Database = Depends(get_db)) -> LoginResponse:
    row = db.one(
        "SELECT id, username, password_hash, display_name, role FROM users WHERE username = ?",
        (payload.username,),
    )
    if row is None or row["password_hash"] != password_hash(payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = create_token(
        user_id=row["id"],
        role=row["role"],
        secret=request.app.state.settings.jwt_secret,
        ttl_seconds=request.app.state.settings.token_ttl_seconds,
    )
    user = UserOut(id=row["id"], username=row["username"], display_name=row["display_name"], role=row["role"])
    return LoginResponse(token=token, user=user)

