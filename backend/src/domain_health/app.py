"""The HTTP surface. Phase 0 has the health route only; the API arrives in Phase 4."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"]


def create_app() -> FastAPI:
    app = FastAPI(title="domain-health", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    async def healthz() -> Health:
        return Health(status="ok")

    return app


app = create_app()
