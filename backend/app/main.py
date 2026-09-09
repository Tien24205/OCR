"""Diem vao cua backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.requests import Request

from app.config import get_settings
from app.db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Business Card to Partner Profile",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ApiError(Exception):
    """Loi nghiep vu, tra ve theo dung mot dang thong nhat cho frontend."""

    def __init__(self, code: str, message: str, status: int = 400, retryable: bool = False):
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            }
        },
    )


@app.get("/api/health")
def health() -> dict:
    """Kiem tra ung dung song va cau hinh da san sang chua.

    `readiness()` chi tra ve True/False - khong bao gio lo gia tri khoa.
    """
    return {"status": "ok", "env": settings.app_env, "config": settings.readiness()}
