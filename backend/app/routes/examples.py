from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db import Database
from ..dependencies import current_user, get_db
from ..schemas import ExampleOut, UserOut
from ..serializers import example_from_row

router = APIRouter(prefix="/examples", tags=["examples"])


@router.get("", response_model=list[ExampleOut])
def list_examples(
    theme: str | None = None,
    db: Database = Depends(get_db),
    _: UserOut = Depends(current_user),
) -> list[ExampleOut]:
    if theme:
        rows = db.all("SELECT * FROM examples WHERE theme = ? ORDER BY title", (theme,))
    else:
        rows = db.all("SELECT * FROM examples ORDER BY theme, title")
    return [example_from_row(row) for row in rows]

