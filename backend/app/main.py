from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .analysis import build_provider
from .config import Settings, load_settings
from .db import Database
from .routes import auth, classes, essays, examples, teacher


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or load_settings()
    db = Database(app_settings.database_path)
    db.init()

    app = FastAPI(title="Essay Correction API", version="0.1.0")
    app.state.settings = app_settings
    app.state.db = db
    app.state.analysis_provider = build_provider(app_settings)
    app.state.analysis_providers = {app_settings.ai_provider: app.state.analysis_provider}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(classes.router)
    app.include_router(essays.router)
    app.include_router(examples.router)
    app.include_router(teacher.router)
    return app


app = create_app()
