"""Cau hinh ung dung, doc tu bien moi truong / file .env.

Nguyen tac: moi khoa dich vu chi song o day va o backend. Khong bao gio
tra gia tri khoa ra API - xem `readiness()` ben duoi, no chi tra ve
True/False chu khong tra ve gia tri.
"""

from __future__ import annotations

import importlib.util
import shutil
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
    # Thoi han luu tru ban quet, tinh bang ngay. 0 = GIU MAI MAI.
    # Mac dinh 0 vi doi han luu tru la quyet dinh phap ly cua nguoi van hanh,
    # khong phai mac dinh ky thuat - tu dong xoa du lieu cua ai do vi ho chua
    # doc tai lieu thi te hon la giu lai. Xem `services/erasure.py`.
    retention_days: int = 0

    # --- Kho anh (Ngay 25) ---
    # local = thu muc tren dia (mac dinh, va la cach du an chay tu Ngay 3).
    # gcs   = Google Cloud Storage; can GCS_BUCKET va quyen tuong ung.
    #
    # Mac dinh `local` chu khong `gcs` vi cung ly do moi mac dinh khac o tep
    # nay: cai chay duoc ngay tren may vua tai ma nguon ve. Doi sang `gcs`
    # la doi MOT dong - xem `services/storage.py`.
    storage_backend: str = "local"
    gcs_bucket: str = ""
    gcs_prefix: str = "scans"
    webhook_enabled: bool = False
    webhook_timeout_s: int = 8
    webhook_max_attempts: int = 3
    cors_origins: str = "http://localhost:8501"

    # --- Xac thuc API ---
    # Danh sach khoa, ngan cach bang dau phay. DE TRONG = khong xac thuc.
    # Xem `auth.py` de biet vi sao che do tat ton tai.
    api_keys: str = ""
    rate_limit_per_minute: int = 60

    # --- Dang nhap nguoi dung (Ngay 23) ---
    # Bat buoc dang nhap moi goi duoc API. MAC DINH TAT vi cung ly do
    # API_KEYS mac dinh trong (xem auth.py): cong cu nay chay tren may ca
    # nhan la chinh, va mot mac dinh bat se khien nguoi ta dat mat khau cho
    # co. Bat khi chay that - Docker Compose bat san.
    auth_required: bool = False
    # Khoa ky phieu JWT. DE TRONG = sinh ngau nhien moi lan khoi dong, tuc
    # moi lan khoi dong lai la moi nguoi phai dang nhap lai. Chap nhan duoc
    # khi chay may ca nhan, KHONG chap nhan duoc khi chay that - nen
    # `readiness()` noi ro dang o trang thai nao.
    jwt_secret: str = ""
    # 12 tieng: du dai cho mot ngay lam viec ma khong phai dang nhap lai
    # giua chung, du ngan de mot phieu bi lo khong song mai.
    jwt_ttl_minutes: int = 12 * 60

    # Cho nguoi la tu tao tai khoan hay khong.
    #
    # MAC DINH MO, giong moi mac dinh khac o tep nay: cai chay duoc ngay tren
    # may vua tai ma nguon ve. Nhung khi trang duoc day ra Internet thi PHAI
    # dong, va day la lo hong nang nhat cua du an truoc khi co thiet lap nay:
    #
    #   dang ky mo  +  ban ghi `owner_id IS NULL` hien voi moi nguoi dang
    #   nhap  =  bat ky ai mo duoc dia chi deu tai ve duoc toan bo danh
    #   thiep, ke ca ANH da chup.
    #
    # Hai ve deu hop ly rieng le. Ve thu hai la co y, de du lieu cu khong
    # bien mat khi bat dang nhap len. Ghep lai thi thanh mot cua mo.
    #
    # DONG KHONG KHOA CHET HE THONG: khi CHUA CO tai khoan nao, `/register`
    # van nhan - nguoi dau tien phai vao duoc thi moi co quan tri. Sau do
    # chi quan tri tao duoc tai khoan moi. Xem `user_routes.dang_ky`.
    registration_open: bool = True

    @property
    def jwt_signing_key(self) -> str:
        """Khoa ky that su dung. Sinh mot lan cho ca tien trinh khi de trong.

        `lru_cache` tren `get_settings()` bao dam ca tien trinh dung CUNG mot
        doi tuong Settings, nen gia tri sinh ra o day on dinh den luc tat -
        khong phai moi loi goi mot khoa khac nhau, dieu se lam moi phieu vua
        cap da hong ngay.
        """
        if self.jwt_secret:
            return self.jwt_secret
        if not hasattr(self, "_khoa_tam"):
            import secrets
            object.__setattr__(self, "_khoa_tam", secrets.token_urlsafe(32))
        return self._khoa_tam

    # --- OCR ---
    ocr_provider: str = "mock"          # google | tesseract | rapidocr | mock
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
    def ocr_configured(self) -> bool:
        """Provider DANG CHON da du cau hinh chua - hoi rieng tung provider.

        LOI DA SUA (ra-soat-ngay-1-2.md, D1-02): giao dien lay
        `ocr_credentials_present` - tuc credentials Google - lam thuoc do cho
        MOI provider. Chay `tesseract`, thu khong dung credentials Google chut
        nao, van bi bao "chua du cau hinh" trong khi no dang doc anh binh thuong.

        Van chi la phep kiem SU CO MAT, khong phai lam that. Goi
        `get_tesseract_version()` o day se them mot tien trinh con vao MOI lan
        /api/health, ma healthcheck cua Docker goi 10 giay mot lan.
        """
        if self.ocr_provider == "mock":
            return True
        if self.ocr_provider == "tesseract":
            if self.tesseract_cmd:
                return Path(self.tesseract_cmd).is_file()
            # De trong nghia la "tim trong PATH" - trong image Docker thi co san.
            return shutil.which("tesseract") is not None
        if self.ocr_provider == "rapidocr":
            # Chay hoan toan trong Python, khong co phan mem he thong nao de
            # tim: cau hoi duy nhat la goi da duoc cai chua. `find_spec` khong
            # import goi nen khong keo theo vai giay nap ONNX Runtime vao moi
            # lan /api/health.
            return importlib.util.find_spec("rapidocr") is not None
        # google: tro toi mot file thi file do phai ton tai; de trong la ADC
        # (`gcloud auth application-default login`), mot cach cau hinh hop le
        # khong the xac minh tu cau hinh.
        if self.google_application_credentials:
            creds = self.credentials_path
            return bool(creds and creds.is_file())
        return True

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
            # Chi muc nay moi tra loi dung cau hoi "chay duoc chua" - xem
            # `ocr_configured`. Giu `ocr_credentials_present` vi no van la su
            # that rieng ve credentials Google.
            "ocr_configured": self.ocr_configured,
            "ocr_auth_mode": ("service_account_file" if creds
                              else "application_default"),
            "extractor": self.extractor,
            "retention_days": self.retention_days,
            # Bao ro anh dang nam o dau. Khi GCS duoc bat nhung khoi tao hong,
            # `kho_anh()` quay ve dia cuc bo - va nguoi van hanh phai thay
            # duoc dieu do o day chu khong phai doan.
            "storage_backend": self.storage_backend,
            "gemini_key_present": bool(self.gemini_api_key),
            "gemini_model_set": bool(self.gemini_model),
            "enrich_enabled": self.enrich_enabled,
            "agent_enabled": self.agent_enabled,
            # Bao ro API dang mo hay dong. KHONG bao gio tra ve gia tri
            # khoa - chi tra ve co, giong moi truong khac o day.
            "auth_enabled": bool(self.api_key_list),
            # Dang nhap nguoi dung, tach khoi khoa API o tren: hai co che
            # khac nhau, co the bat rieng.
            "login_required": self.auth_required,
        # Giao dien dung co nay de an hay hien o dang ky.
        "registration_open": self.registration_open,
            # False = khoa ky sinh ngau nhien luc khoi dong, tuc khoi dong
            # lai la moi nguoi mat phien. Bao ra de khong ai phai doan vi sao
            # tu nhien bi dang xuat.
            "jwt_secret_persistent": bool(self.jwt_secret),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
