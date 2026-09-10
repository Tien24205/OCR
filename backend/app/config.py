"""Cau hinh ung dung, doc tu bien moi truong / file .env.

Nguyen tac: moi khoa dich vu chi song o day va o backend. Khong bao gio
tra gia tri khoa ra API - xem `readiness()` ben duoi, no chi tra ve
True/False chu khong tra ve gia tri.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Ung dung ---
    app_env: str = "development"
    database_url: str = "sqlite:///./data/app.db"
    image_dir: Path = BACKEND_DIR / "data" / "images"
    max_upload_bytes: int = 8 * 1024 * 1024
    cors_origins: str = "http://localhost:8501"

    # --- OCR ---
    ocr_provider: str = "mock"          # google | mock
    google_application_credentials: str | None = None
    ocr_timeout_s: int = 20
    ocr_language_hints: str = "ja,en"

    # --- Trich xuat truong ---
    extractor: str = "heuristic"        # gemini | heuristic
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    gemini_temperature: float = 0.0

    # --- Tra cuu ---
    enrich_enabled: bool = True
    enrich_max_pages: int = 5
    enrich_timeout_s: int = 8
    enrich_max_bytes: int = 2 * 1024 * 1024
    enrich_user_agent: str = "BusinessCardBot/0.1"

    @property
    def image_path(self) -> Path:
        """Thu muc anh, LUON tuyet doi.

        `.env` ghi duong dan tuong doi (`./data/images`) cho de doc, nhung
        duong dan tuong doi phu thuoc thu muc dang chay. Backend co the duoc
        khoi dong tu goc du an (`--app-dir backend`) hoac tu trong `backend/`,
        va hai cach do se tro toi hai thu muc khac nhau. Neo vao BACKEND_DIR
        de ket qua luon giong nhau.
        """
        p = Path(self.image_dir)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def language_hint_list(self) -> list[str]:
        return [h.strip() for h in self.ocr_language_hints.split(",") if h.strip()]

    def readiness(self) -> dict[str, bool | str]:
        """Bao cao cau hinh da san sang chua, KHONG lo gia tri khoa."""
        creds = self.google_application_credentials
        return {
            "ocr_provider": self.ocr_provider,
            "ocr_credentials_present": bool(creds and Path(creds).is_file()),
            "extractor": self.extractor,
            "gemini_key_present": bool(self.gemini_api_key),
            "gemini_model_set": bool(self.gemini_model),
            "enrich_enabled": self.enrich_enabled,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
