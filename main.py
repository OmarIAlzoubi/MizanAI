from pathlib import Path

from fastapi import (
    FastAPI,
)
from fastapi.staticfiles import (
    StaticFiles,
)

from app.api.routes import (
    router,
)
from app.core.config import (
    BASE_DIR,
    get_settings,
)
from app.infrastructure.database.schema import (
    initialize_database,
)


settings = get_settings()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)


@app.on_event(
    "startup"
)
def startup():
    initialize_database()


@app.get(
    "/health"
)
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
    }


# API routes must come before
# the frontend mount.
app.include_router(
    router
)


frontend_path = (
    BASE_DIR
    / "frontend"
)


app.mount(
    "/",
    StaticFiles(
        directory=frontend_path,
        html=True,
    ),
    name="frontend",
)