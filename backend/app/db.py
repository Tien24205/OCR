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


# Cac cot them vao BANG DA TON TAI. `create_all` chi tao bang moi; no khong
# bao gio sua bang da co, nen cot them o Ngay 23 se khong xuat hien tren
# nhung CSDL da chay tu truoc - va loi se la "no such column: owner_id" giua
# luc dang dung, chu khong phai luc khoi dong.
#
# VI SAO KHONG DUNG ALEMBIC: toan bo nhu cau doi schema cua du an nay la
# "them cot cho phep NULL". Alembic keo theo mot thu muc phien ban, mot tep
# cau hinh va mot buoc chay rieng - nhieu hon han thu no giai quyet o day.
# Khi nao can doi kieu cot, doi ten hay chia bang thi chuyen sang Alembic,
# vi nhung viec do SQLite khong lam duoc bang ALTER TABLE.
_COT_THEM: tuple[tuple[str, str, str], ...] = (
    # (bang, ten cot, dinh nghia)
    ("scans", "owner_id", "VARCHAR(36) REFERENCES users(id)"),
    ("contacts", "owner_id", "VARCHAR(36) REFERENCES users(id)"),
)


def _va_cot_thieu() -> None:
    """Them cot con thieu vao bang da ton tai. Chay duoc nhieu lan.

    SQLite chi cho them cot co gia tri mac dinh NULL khi cot do co rang buoc
    khoa ngoai - dung y cua ta: ban ghi cu khong co chu, va `NULL = khong co
    chu` la dieu ma phan phan quyen o `access.py` da tinh den.
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        co_bang = {
            r[0] for r in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        for bang, cot, dinh_nghia in _COT_THEM:
            if bang not in co_bang:
                continue                     # create_all vua tao, da du cot
            dang_co = {
                r[1] for r in conn.execute(text(f"PRAGMA table_info({bang})"))
            }
            if cot in dang_co:
                continue
            conn.execute(text(f"ALTER TABLE {bang} ADD COLUMN {cot} {dinh_nghia}"))
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS ix_{bang}_{cot} ON {bang}({cot})"
            ))


def init_db() -> None:
    """Tao bang neu chua co, roi vá cot con thieu tren bang da co."""
    settings.image_path.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        _va_cot_thieu()


def get_db() -> Iterator[Session]:
    """Dependency cua FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
