"""Ket noi co so du lieu.

Hai PRAGMA duoi day bat buoc phai bat cho SQLite:

- `foreign_keys=ON`: SQLite MAC DINH TAT rang buoc khoa ngoai. Khong bat
  thi cac quan he ON DELETE CASCADE trong models.py khong chay, va du lieu
  se tro nen mo coi ma khong bao loi.
- `journal_mode=WAL`: cho phep doc va ghi dong thoi, tranh loi
  "database is locked" khi tac vu nen chay OCR trong luc nguoi dung
  dang xem danh sach.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import BACKEND_DIR, get_settings
from app.models import Base

settings = get_settings()

# sqlite:///./data/app.db  ->  duong dan tuyet doi, khong phu thuoc thu muc chay
_url = settings.database_url
if _url.startswith("sqlite:///./"):
    db_path = (BACKEND_DIR / _url.removeprefix("sqlite:///./")).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _url = f"sqlite:///{db_path}"

engine = create_engine(
    _url,
    # FastAPI chay handler tren nhieu thread; SQLite mac dinh cam dieu do.
    connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {},
    echo=False,
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Tao bang neu chua co. Du cho pham vi 10 ngay; neu sau nay can doi
    schema tren du lieu that thi chuyen sang Alembic."""
    settings.image_path.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """Dependency cua FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
