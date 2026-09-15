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
    batch_max_images: int = 10
    # So ban quet chay dong thoi trong mot lo. Dat 1 de chay tuan tu.
    batch_workers: int = 3
    # Webhook gui du lieu RA NGOAI toi URL do nguoi dung nhap. App chua
    # co xac thuc, nen mac dinh TAT - chi bat khi da co xac thuc hoac
    # chi chay trong mang noi bo.
    webhook_enabled: bool = False
    webhook_timeout_s: int = 8
    webhook_max_attempts: int = 3
    cors_origins: str = "http://localhost:8501"

    # --- Xac thuc API ---
    # Danh sach khoa, ngan cach bang dau phay. DE TRONG = khong xac thuc.
    # Xem `auth.py` de biet vi sao che do tat ton tai.
    api_keys: str = ""
    rate_limit_per_minute: int = 60

    # --- OCR ---
    ocr_provider: str = "mock"          # google | tesseract | mock
    google_application_credentials: str | None = None
    # Chi can khi Tesseract khong nam trong PATH (hay gap tren Windows).
    tesseract_cmd: str | None = None
    ocr_timeout_s: int = 20
    ocr_language_hints: str = "ja,en,ko,zh"

    # --- Trich xuat truong ---
    extractor: str = "heuristic"        # gemini | heuristic
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    gemini_temperature: float = 0.0
    extract_timeout_s: int = 30

    # Opt in: absent configuration preserves the existing pipeline.
    agent_enabled: bool = False
    agent_auto_enrich: bool = False

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
    def credentials_path(self) -> Path | None:
        if not self.google_application_credentials:
            return None
        path = Path(self.google_application_credentials)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def language_hint_list(self) -> list[str]:
        return [h.strip() for h in self.ocr_language_hints.split(",") if h.strip()]

    def readiness(self) -> dict[str, bool | str]:
        """Bao cao cau hinh da san sang chua, KHONG lo gia tri khoa."""
        creds = self.credentials_path
        return {
            "ocr_provider": self.ocr_provider,
            # None nghia la KHONG dat bien -> dung Application Default
            # Credentials. Do khong phai loi cau hinh, nen bao rieng thay vi
            # gop chung voi "thieu credentials".
            "ocr_credentials_present": bool(creds and creds.is_file()),
            "ocr_auth_mode": ("service_account_file" if creds
                              else "application_default"),
            "extractor": self.extractor,
            "gemini_key_present": bool(self.gemini_api_key),
            "gemini_model_set": bool(self.gemini_model),
            "enrich_enabled": self.enrich_enabled,
            "agent_enabled": self.agent_enabled,
            # Bao ro API dang mo hay dong. KHONG bao gio tra ve gia tri
            # khoa - chi tra ve co, giong moi truong khac o day.
            "auth_enabled": bool(self.api_key_list),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
