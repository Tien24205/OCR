from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base


@event.listens_for(Engine, "connect")
def _pragma(dbapi_connection, connection_record) -> None:
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


@pytest.fixture(autouse=True)
def _xoa_han_muc_dang_nhap():
    """Tra bo dem chong do mat khau ve 0 truoc moi test.

    `user_routes._chan_dang_nhap` la mot doi tuong cap module, nen no khong
    bi tao lai giua cac test. TestClient lai luon goi tu cung mot dia chi,
    nen sau vai test la ca file do voi 429. Xoa o day de moi test bat dau
    voi han muc day - dung y cua bo chan la chong do mat khau tu ben ngoai,
    khong phai chong bo test.
    """
    from app.user_routes import _chan_dang_nhap

    _chan_dang_nhap.xoa_het()
    yield


@pytest.fixture()
def db() -> Session:
    """DB trong bo nho, tao moi cho tung test."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
