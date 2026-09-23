"""Day 3 contract: real multipart requests, temporary disk and SQLite; no OCR."""

from io import BytesIO
import hashlib

import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app import main
from app.services import storage
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Base, Scan


def picture(fmt="PNG", size=(32, 20), orientation=None):
    image = Image.new("RGB", size, "white")
    image.putpixel((0, 0), (255, 0, 0))
    image.putpixel((size[0] - 1, 0), (0, 255, 0))
    out = BytesIO()
    options = {}
    if orientation:
        exif = Image.Exif()
        exif[274] = orientation
        options["exif"] = exif
    image.save(out, format=fmt, **options)
    return out.getvalue()


@pytest.fixture
def upload_app(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    config = Settings(_env_file=None, image_dir=tmp_path / "images")
    def database():
        with Session(engine, expire_on_commit=False) as db:
            yield db
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "run_scan", lambda *args: None)
    main.app.dependency_overrides[get_db] = database
    main.app.dependency_overrides[get_settings] = lambda: config
    with TestClient(main.app) as client:
        yield client, engine, config
    main.app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.parametrize("fmt,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_upload_persists_scan_and_actual_image(upload_app, fmt, mime):
    client, engine, config = upload_app
    data = picture(fmt)
    # Filename and declared MIME are untrusted; sniff the actual content.
    res = client.post("/api/scans", files={"file": ("../../outside.jpg", data, "text/plain")})
    assert res.status_code == 201
    assert res.json()["status"] == "pending"
    with Session(engine) as db:
        scan = db.get(Scan, res.json()["id"])
        assert scan.image_mime == mime
        assert scan.image_bytes == len(data)
        assert scan.image_ref == hashlib.sha256(data).hexdigest()
        assert (config.image_path / scan.image_ref).read_bytes() == data
        assert scan.raw_text is None and scan.extraction_json is None
    assert len(list(config.image_path.iterdir())) == 1


@pytest.mark.parametrize("data,code", [
    (b"", "INVALID_IMAGE"),
    (b"this is a text file renamed to jpg", "INVALID_IMAGE"),
    (picture("GIF"), "UNSUPPORTED_IMAGE"),
    (picture()[:45], "INVALID_IMAGE"),
    (picture(size=(6001, 1)), "IMAGE_DIMENSIONS"),
])
def test_rejected_file_creates_no_scan_or_image(upload_app, data, code):
    client, engine, config = upload_app
    res = client.post("/api/scans", files={"file": ("card.jpg", data, "image/jpeg")})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == code
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Scan)) == 0
    assert not config.image_path.exists()


def test_eight_mb_limit(upload_app):
    client, engine, config = upload_app
    res = client.post("/api/scans", files={"file": ("card.png", b"x" * (8 * 1024 * 1024 + 1), "image/png")})
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "IMAGE_TOO_LARGE"
    assert not config.image_path.exists()


def test_exact_byte_limit_is_accepted(upload_app):
    client, _, config = upload_app
    data = picture()
    config.max_upload_bytes = len(data)
    assert client.post("/api/scans", files={"file": ("card.png", data)}).status_code == 201


def test_exif_rotation_is_applied_once_and_hash_matches_saved_bytes(upload_app):
    client, engine, config = upload_app
    data = picture(size=(3, 2), orientation=6)
    res = client.post("/api/scans", files={"file": ("phone.png", data, "image/png")})
    assert res.status_code == 201
    with Session(engine) as db:
        scan = db.get(Scan, res.json()["id"])
        saved = (config.image_path / scan.image_ref).read_bytes()
        assert scan.image_ref == hashlib.sha256(saved).hexdigest()
        assert scan.image_bytes == len(saved)
    with Image.open(BytesIO(saved)) as image:
        assert image.size == (2, 3)
        assert image.getpixel((1, 0)) == (255, 0, 0)
        assert image.getpixel((1, 2)) == (0, 255, 0)
        assert image.getexif().get(274, 1) == 1
    second = client.post("/api/scans", files={"file": ("upright.png", saved)})
    with Session(engine) as db:
        assert db.get(Scan, second.json()["id"]).image_ref == hashlib.sha256(saved).hexdigest()


def test_repeat_upload_reuses_file_but_records_separate_scans(upload_app):
    client, engine, config = upload_app
    ids = [client.post("/api/scans", files={"file": ("card.png", picture())}).json()["id"] for _ in range(2)]
    assert ids[0] != ids[1]  # Record deduplication is a later-day feature.
    assert len(list(config.image_path.iterdir())) == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Scan)) == 2


def test_storage_failure_returns_actionable_error(upload_app, monkeypatch):
    client, engine, _ = upload_app
    def fail(*args, **kwargs):
        raise OSError("private storage path")
    # Kho anh duoc chon luc chay qua `kho_anh(config)`, nen chan o lop kho
    # chu khong o `main`: `main` khong con ham luu anh nao de chan.
    monkeypatch.setattr(storage.KhoTepLocal, "luu", fail)
    res = client.post("/api/scans", files={"file": ("card.png", picture())})
    assert res.status_code == 500
    assert res.json()["error"]["retryable"] is True
    assert "private storage path" not in res.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Scan)) == 0


def test_missing_file(upload_app):
    assert upload_app[0].post("/api/scans").status_code == 422


def test_jpeg_phone_orientation(upload_app):
    client, engine, config = upload_app
    res = client.post("/api/scans", files={"file": ("phone.jpg", picture("JPEG", (40, 20), 8))})
    assert res.status_code == 201
    with Session(engine) as db:
        scan = db.get(Scan, res.json()["id"])
        assert scan.image_mime == "image/jpeg"
        with Image.open(config.image_path / scan.image_ref) as image:
            assert image.size == (20, 40)
            assert image.getexif().get(274, 1) == 1


def test_database_failure_does_not_report_success(upload_app, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    client, engine, config = upload_app
    def fail(*args):
        raise SQLAlchemyError("database internal details")
    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail)
        res = client.post("/api/scans", files={"file": ("card.png", picture())})
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "SCAN_SAVE_FAILED"
    assert "database internal details" not in res.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Scan)) == 0
    # Disk is not a DB transaction: preserve the complete hash file for retries.
    assert len(list(config.image_path.iterdir())) == 1
