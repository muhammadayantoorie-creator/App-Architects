"""FastAPI application factory and application entry point."""

from __future__ import annotations

import importlib
import pkgutil

from fastapi import FastAPI
from sqlalchemy import inspect, select, text

from backend.core.db import Base, SessionLocal, create_all, engine
from backend.core.errors import install_exception_handlers
from backend.core.middleware import RequestBodyLimitMiddleware
from backend.core.ratelimit import RateLimitMiddleware
from backend.core.registry import clear_database, run_reset_hooks
from backend.core.state import baseline_is_seeded, set_value


def _load_routers(app: FastAPI) -> None:
    packages = ["backend.modules", "backend.fixtures"]
    for package_name in packages:
        try:
            package = importlib.import_module(package_name)
        except ModuleNotFoundError as exc:
            if exc.name == package_name:
                continue
            raise
        if not hasattr(package, "__path__"):
            continue
        for module_info in pkgutil.walk_packages(
            package.__path__, package.__name__ + "."
        ):
            if module_info.name.endswith(".router"):
                module = importlib.import_module(module_info.name)
                router = getattr(module, "router", None)
                if router is not None:
                    app.include_router(router)


def _database_is_empty() -> bool:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if not tables:
        return True
    with SessionLocal() as session:
        for table in Base.metadata.sorted_tables:
            if table.name in tables and session.execute(
                select(1).select_from(table).limit(1)
            ).first():
                return False
    return True


def create_app() -> FastAPI:
    app = FastAPI(title="NaSCon '26 API")
    install_exception_handlers(app)
    app.add_middleware(RequestBodyLimitMiddleware)
    app.add_middleware(RateLimitMiddleware)
    _load_routers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        try:
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
                seeded = baseline_is_seeded(session)
        except Exception as exc:
            from fastapi import HTTPException

            raise HTTPException(status_code=503, detail="Database unavailable") from exc
        if not seeded:
            from fastapi import HTTPException

            raise HTTPException(status_code=503, detail="Baseline is not seeded")
        return {"status": "ok"}

    @app.on_event("startup")
    def initialize_database() -> None:
        create_all()
        with SessionLocal() as session:
            seeded = baseline_is_seeded(session)
        if not seeded:
            # Fresh volume or an interrupted seed: rebuild the baseline from scratch.
            with SessionLocal.begin() as session:
                clear_database(session)
                run_reset_hooks(session, 42, {})
                set_value(session, "last_reset_seed", "42")
        with SessionLocal() as session:
            app.state.baseline_seeded = baseline_is_seeded(session)

    return app


app = create_app()
