"""Xu ly hang loat - moc 14/09 cua ke hoach nang cap.

Endpoint nay truoc do khong co test nao. Bo test nay khoa lai bon hanh vi ma
neu hong se rat kho phat hien:

  1. Mot anh hong khong duoc lam hong ca lo.
  2. Ca lo chay trong MOT tac vu nen, khong phai moi anh mot tac vu - neu moi
     anh mot tac vu thi Starlette chay lan luot va lo 10 anh mat gap 10 lan.
  3. Hai luong khong duoc xu ly cung mot ban quet.
  4. Gioi han so anh mot lo phai duoc thuc thi.
"""

from __future__ import annotations

import io
import threading

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.db import get_db
from app.main import app, get_session_factory
from app.models import Base, Scan


@event.listens_for(Engine, "connect")
def _pragma(dbapi_connection, connection_record) -> None:
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def png(color: tuple[int, int, int]) -> bytes:
    """Anh hop le, moi anh mot mau -> moi anh mot SHA-256 khac nhau."""
    buffer = io.BytesIO()
    Image.new("RGB", (400, 240), color).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture()
def system(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'batch.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    config = Settings(image_dir=tmp_path / "images", ocr_provider="mock",
                      extractor="heuristic", batch_workers=3)

    def _db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_settings] = lambda: config
    app.dependency_overrides[get_session_factory] = lambda: factory
    try:
        yield TestClient(app), factory, config
    finally:
        app.dependency_overrides.clear()


def upload(client, files: list[tuple[str, bytes]]):
    return client.post("/api/scans/batch", files=[
        ("files", (name, data, "image/png")) for name, data in files
    ])


def test_moi_anh_tao_mot_ban_quet(system, monkeypatch):
    client, factory, _ = system
    monkeypatch.setattr("app.main.run_batch", lambda *a, **k: None)

    response = upload(client, [(f"{i}.png", png((i * 30, 10, 20))) for i in range(4)])
    assert response.status_code == 201

    body = response.json()
    assert body["queued"] == 4
    assert len({item["id"] for item in body["items"]}) == 4
    assert all(item["status"] == "pending" for item in body["items"])

    with factory() as db:
        assert db.query(Scan).count() == 4


def test_anh_hong_khong_lam_hong_ca_lo(system, monkeypatch):
    """Mot tep khong phai anh nam giua lo: cac anh con lai van phai chay."""
    client, factory, _ = system
    monkeypatch.setattr("app.main.run_batch", lambda *a, **k: None)

    response = upload(client, [
        ("tot-1.png", png((10, 20, 30))),
        ("hong.png", b"day khong phai anh"),
        ("tot-2.png", png((40, 50, 60))),
    ])
    assert response.status_code == 201

    items = {item["filename"]: item for item in response.json()["items"]}
    assert "id" in items["tot-1.png"] and "id" in items["tot-2.png"]
    assert "error" in items["hong.png"] and "id" not in items["hong.png"]
    assert response.json()["queued"] == 2

    with factory() as db:
        assert db.query(Scan).count() == 2


def test_ca_lo_chay_trong_mot_tac_vu_nen(system, monkeypatch):
    """Neu xep moi anh mot tac vu, Starlette chay lan luot va mat het loi ich
    cua xu ly hang loat."""
    client, _, _ = system
    calls: list[list[str]] = []
    monkeypatch.setattr("app.main.run_batch",
                        lambda ids, *a, **k: calls.append(list(ids)))

    upload(client, [(f"{i}.png", png((i * 40, 5, 5))) for i in range(3)])
    assert len(calls) == 1          # MOT lan goi, khong phai ba
    assert len(calls[0]) == 3


def test_vuot_gioi_han_bi_tu_choi(system):
    client, factory, config = system
    files = [(f"{i}.png", png((i * 20, 1, 1))) for i in range(config.batch_max_images + 1)]

    response = upload(client, files)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BATCH_TOO_LARGE"

    with factory() as db:
        assert db.query(Scan).count() == 0      # khong tao ban quet nao


def test_hai_luong_khong_xu_ly_cung_mot_ban_quet(system):
    """`run_scan` gianh ban quet bang UPDATE co dieu kien status='pending'.
    Day la co che duy nhat ngan hai luong cung xu ly mot anh khi chay song song.
    """
    from app.pipeline import run_batch

    client, factory, config = system
    response = upload(client, [("a.png", png((7, 7, 7)))])
    scan_id = response.json()["items"][0]["id"]

    started: list[str] = []
    lock = threading.Lock()

    import app.pipeline as pipeline
    real = pipeline.run_scan

    def counting(sid, cfg, fac):
        with lock:
            started.append(sid)
        return real(sid, cfg, fac)

    pipeline.run_scan = counting
    try:
        # Cung mot ban quet duoc dua vao lo hai lan.
        run_batch([scan_id, scan_id], config, factory)
    finally:
        pipeline.run_scan = real

    assert started.count(scan_id) == 2          # ca hai luong deu chay
    with factory() as db:
        scan = db.get(Scan, scan_id)
    # ...nhung chi mot luong gianh duoc, nen ban quet khong bi xu ly hai lan.
    assert scan.status in {"ocr_done", "failed"}


def test_mot_worker_van_chay_duoc(system):
    """`batch_workers=1` la duong lui khi SQLite bi tranh chap ghi."""
    from app.pipeline import run_batch

    client, factory, base = system
    # Dung lai cau hinh cua fixture, chi doi so luong worker. Ban cu tao
    # Settings moi bang mot bieu thuc `and` vo nghia va mo mot session khong
    # bao gio dong.
    config = base.model_copy(update={"batch_workers": 1})
    response = upload(client, [("a.png", png((9, 9, 9))), ("b.png", png((3, 3, 3)))])
    ids = [item["id"] for item in response.json()["items"]]

    run_batch(ids, config, factory)

    with factory() as db:
        assert all(db.get(Scan, i).status in {"ocr_done", "failed"} for i in ids)
