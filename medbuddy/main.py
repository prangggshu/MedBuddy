"""FastAPI app for the MedBuddy browser chat."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from medbuddy.config import get_settings
from medbuddy.db import init_db
from medbuddy.logging_config import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MedBuddy", version="0.1.0", lifespan=lifespan)
_origins = [origin.strip() for origin in get_settings().cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=_origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

from medbuddy.api_web import router as web_router

app.include_router(web_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "medbuddy", "note": "proof-of-concept, not for clinical use"}
