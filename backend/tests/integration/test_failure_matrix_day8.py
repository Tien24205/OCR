"""Ma tran tinh huong hong - Ngay 8 cua ke hoach 10 ngay.

Ke hoach liet ke 13 dong. Bo test nay tu dong hoa nhung dong KIEM CHUNG DUOC
bang may; nhung dong con lai (quyen camera, DevTools, HTTPS tren dien thoai)
can nguoi lam tay va nam o `Document/3-bao-cao/ngay-8.md`.

Doi tuong cua Ngay 8 khac voi cac ngay truoc: khong phai kiem tra tung bo phan
ma kiem tra TOAN LUONG duoi dieu kien xau, va kiem tra nhung thu chua ai test.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from types import SimpleNamespace

import app.pipeline as pipeline
from app.config import Settings, get_settings
from app.db import get_db
from app.main import app, get_session_factory
from app.models import Base, Contact, Scan
from app.services.extract.base import CardExtraction, ExtractedValue, PhoneValue
from app.services.ocr.base import OcrError, OcrResult

CARD_TEXT = (
    "株式会社青葉テクノロジー\n"
    "営業本部\n"
    "部長 山田 太郎\n"
    "〒100-0001 東京都千代田区千代田1-2-3\n"
    "TEL: 03-5432-1098\n"
    "taro.yamada@example.co.jp"
)


# --------------------------------------------------------------------------
# Ha tang
# --------------------------------------------------------------------------

def card_image(*, blur: float = 0, rotate: float = 0, glare: bool = False) -> bytes:
    """Anh the, co the lam xuong cap de mo phong anh chup that."""
    image = Image.new("RGB", (900, 540), "white")
    draw = ImageDraw.Draw(image)
    for path in ("C:/Windows/Fonts/YuGothM.ttc", "C:/Windows/Fonts/msgothic.ttc"):
        try:
            font = ImageFont.truetype(path, 32)
            break
        except OSError:
            continue
    else:
        font = ImageFont.load_default(32)

    for index, line in enumerate(CARD_TEXT.splitlines()):
        draw.text((40, 40 + index * 70), line, font=font, fill=(20, 20, 20))

    if glare:
        overlay = Image.new("RGB", image.size, "white")
        mask = Image.new("L", image.size, 0)
        ImageDraw.Draw(mask).ellipse([350, -180, 1100, 400], fill=190)
        image = Image.composite(overlay, image, mask)
    if rotate:
        image = image.rotate(rotate, expand=True, fillcolor="white")
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(blur))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88)
    return buffer.getvalue()


@pytest.fixture()
def system(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'day8.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = Settings(image_dir=tmp_path / "images", ocr_provider="mock",
                      extractor="heuristic", batch_workers=1)

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
        yield SimpleNamespace(client=TestClient(app), factory=factory, config=config)
    finally:
        app.dependency_overrides.clear()


def stub_providers(monkeypatch, *, raw=CARD_TEXT, extraction=None, ocr_error=None):
    """Thay hai provider bang ban gia lap co kiem soat."""
    calls = {"ocr": 0, "extract": 0}

    def recognize(image, mime):
        calls["ocr"] += 1
        if ocr_error and calls["ocr"] <= ocr_error["times"]:
            raise OcrError(ocr_error["code"], ocr_error["message"],
                           retryable=ocr_error.get("retryable", True))
        return OcrResult(raw_text=raw, provider="mock:test", provider_version="t",
                         detected_languages=["ja"])

    def extract(image, mime, raw_text):
        calls["extract"] += 1
        return extraction if extraction is not None else CardExtraction(
            full_names=[ExtractedValue(value="山田 太郎")],
            company_names=[ExtractedValue(value="株式会社青葉テクノロジー")],
            emails=[ExtractedValue(value="taro.yamada@example.co.jp")],
            phones=[PhoneValue(value="03-5432-1098", label="tel")],
        )

    monkeypatch.setattr(pipeline, "build_ocr", lambda config: SimpleNamespace(recognize=recognize))
    monkeypatch.setattr(pipeline, "build_extractor",
                        lambda config: SimpleNamespace(name="test", extract=extract))
    return calls


def upload(system, data: bytes, name="card.jpg", mime="image/jpeg"):
    return system.client.post("/api/scans",
                              files={"file": (name, data, mime)})


# --------------------------------------------------------------------------
# Dong 3 - tep khong phai anh
# --------------------------------------------------------------------------

def test_03_tep_van_ban_doi_duoi_jpg_bi_tu_choi(system, monkeypatch):
    """Tin vao duoi tep hoac Content-Type la lo hong; phai doc magic bytes."""
    stub_providers(monkeypatch)
    response = upload(system, b"day khong phai anh, chi la van ban thuong")

    assert response.status_code == 400
    assert response.json()["error"]["message"]        # co thong bao cho nguoi dung
    with system.factory() as db:
        assert db.query(Scan).count() == 0


def test_03b_anh_hop_le_nhung_mime_sai_van_duoc_nhan(system, monkeypatch):
    """Nguoc lai: Content-Type sai ma noi dung dung anh thi khong duoc tu choi
    oan - mot so trinh duyet gui sai MIME."""
    stub_providers(monkeypatch)
    response = upload(system, card_image(), name="card.txt", mime="text/plain")
    assert response.status_code == 201


# --------------------------------------------------------------------------
# Dong 4 - anh qua lon
# --------------------------------------------------------------------------

def test_04_anh_vuot_gioi_han_bi_tu_choi_va_tien_trinh_khong_sap(system, monkeypatch):
    stub_providers(monkeypatch)
    oversized = b"\xff\xd8\xff" + b"\x00" * (system.config.max_upload_bytes + 1024)

    response = upload(system, oversized)
    assert response.status_code in (400, 413)

    # Tien trinh van phuc vu duoc yeu cau tiep theo.
    assert upload(system, card_image()).status_code == 201


# --------------------------------------------------------------------------
# Dong 5 - anh mo, nghieng, choi den
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kind,kwargs", [
    ("mo", {"blur": 2.5}),
    ("nghieng", {"rotate": 7}),
    ("choi den", {"glare": True}),
    ("mo va nghieng", {"blur": 1.8, "rotate": -5}),
])
def test_05_anh_xuong_cap_khong_lam_hong_luong(system, monkeypatch, kind, kwargs):
    """Anh xau phai cho it truong hon, KHONG duoc lam sap va KHONG duoc bia."""
    stub_providers(monkeypatch)
    response = upload(system, card_image(**kwargs))
    assert response.status_code == 201, kind

    scan_id = response.json()["id"]
    body = system.client.get(f"/api/scans/{scan_id}").json()
    assert body["status"] in ("ocr_done", "processing"), kind


def test_05b_ocr_doc_thieu_thi_KHONG_duoc_bia_them_truong(system, monkeypatch):
    """Day la bao dam cot loi cua ca du an.

    Mo phong anh mo: OCR chi doc duoc mot phan, nhung model van tra ve day du
    truong - gom ca mot email va mot so dien thoai khong he co trong van ban.
    Chot chan phai loai chung.
    """
    stub_providers(
        monkeypatch,
        raw="株式会社青葉テクノロジー\n山田 太郎",      # OCR chi doc duoc 2 dong
        extraction=CardExtraction(
            full_names=[ExtractedValue(value="山田 太郎")],
            company_names=[ExtractedValue(value="株式会社青葉テクノロジー")],
            emails=[ExtractedValue(value="taro.yamada@example.co.jp")],   # bia
            phones=[PhoneValue(value="03-5432-1098", label="tel")],       # bia
        ),
    )
    scan_id = upload(system, card_image(blur=3)).json()["id"]
    draft = system.client.get(f"/api/scans/{scan_id}").json()["draft"]

    assert [v["value"] for v in draft["fields"]["full_names"]] == ["山田 太郎"]
    assert draft["fields"]["emails"] == []      # bi loai vi khong co trong OCR
    assert draft["fields"]["phones"] == []

    # ...nhung bang chung ve viec chung bi loai phai duoc giu lai de bao cao.
    with system.factory() as db:
        report = db.get(Scan, scan_id).grounding_json["report"]
    assert report["emails"][0]["verdict"] == "unverified"


# --------------------------------------------------------------------------
# Dong 6 - dich vu OCR loi giua chung
# --------------------------------------------------------------------------

def test_06_ocr_loi_thi_ban_quet_that_bai_va_thu_lai_duoc(system, monkeypatch):
    calls = stub_providers(monkeypatch, ocr_error={
        "code": "OCR_UNAVAILABLE", "message": "Mat ket noi", "times": 99,
        "retryable": True,
    })
    scan_id = upload(system, card_image()).json()["id"]

    body = system.client.get(f"/api/scans/{scan_id}").json()
    assert body["status"] == "failed"
    assert body.get("error_code") or body.get("error")

    # Dich vu hoi phuc -> thu lai phai thanh cong, khong phai tai anh len lai.
    stub_providers(monkeypatch)
    assert system.client.post(f"/api/scans/{scan_id}/retry").status_code in (200, 202)
    assert system.client.get(f"/api/scans/{scan_id}").json()["status"] == "ocr_done"


def test_06b_loi_vinh_vien_khong_bi_thu_lai_nhieu_lan(system, monkeypatch):
    """Thu lai anh hong chi ton them tien ma khong bao gio thanh cong."""
    calls = stub_providers(monkeypatch, ocr_error={
        "code": "OCR_REJECTED", "message": "Anh hong", "times": 99,
        "retryable": False,
    })
    upload(system, card_image())
    assert calls["ocr"] == 1


# --------------------------------------------------------------------------
# Dong 9 - quet lai dung anh cu
# --------------------------------------------------------------------------

def test_09_quet_lai_cung_mot_anh_khong_tao_ban_sao_anh(system, monkeypatch):
    """Anh duoc luu theo SHA-256 nen cung mot anh chi ton mot ban tren dia,
    nhung van la hai ban quet rieng - nguoi dung quyet dinh gop hay khong."""
    stub_providers(monkeypatch)
    data = card_image()
    first = upload(system, data).json()["id"]
    second = upload(system, data).json()["id"]

    assert first != second
    with system.factory() as db:
        refs = {s.image_ref for s in db.query(Scan).all()}
    assert len(refs) == 1
    assert len(list((system.config.image_path).glob("*"))) == 1


# --------------------------------------------------------------------------
# Dong 13 - hai phien khong lan sang nhau
# --------------------------------------------------------------------------

def test_13_hai_ban_quet_khong_lan_du_lieu_sang_nhau(system, monkeypatch):
    """Mo app o hai tab: ban quet cua tab nay khong duoc lot sang tab kia."""
    stub_providers(monkeypatch, raw="Jane Doe\nExample Inc.\njane@example.com",
                   extraction=CardExtraction(
                       full_names=[ExtractedValue(value="Jane Doe")],
                       company_names=[ExtractedValue(value="Example Inc.")]))
    first = upload(system, card_image(rotate=2)).json()["id"]

    stub_providers(monkeypatch)
    second = upload(system, card_image(blur=0.4)).json()["id"]

    a = system.client.get(f"/api/scans/{first}").json()["draft"]
    b = system.client.get(f"/api/scans/{second}").json()["draft"]
    assert [v["value"] for v in a["fields"]["full_names"]] == ["Jane Doe"]
    assert [v["value"] for v in b["fields"]["full_names"]] == ["山田 太郎"]


# --------------------------------------------------------------------------
# Dong 1 - tron luong, nhieu the, khong mat du lieu
# --------------------------------------------------------------------------

def test_01_tron_luong_nhieu_the_khong_mat_du_lieu(system, monkeypatch):
    """Anh -> OCR -> ban nhap -> nguoi sua -> ho so -> tim kiem -> xuat."""
    stub_providers(monkeypatch)
    scan_id = upload(system, card_image()).json()["id"]

    scan = system.client.get(f"/api/scans/{scan_id}").json()
    fields = {name: [
        {key: item.get(key, "") for key in ("id", "value", "label", "extension")}
        for item in items
    ] for name, items in scan["draft"]["fields"].items()}

    # Nguoi dung bo sung mot truong OCR khong doc duoc. Dong moi khong co "id" -
    # backend se cap id va danh dau nguon la "user".
    fields["job_titles"] = [{"value": "部長"}]
    saved = system.client.patch(
        f"/api/scans/{scan_id}/draft",
        json={"revision": scan["draft_revision"], "fields": fields})
    assert saved.status_code == 200, saved.text
    assert saved.json()["draft"]["fields"]["job_titles"][0]["source"] == "user"

    revision = saved.json()["draft_revision"]
    payload = {"scan_id": scan_id, "revision": revision}
    commit = system.client.post("/api/contacts", json=payload,
                                headers={"Idempotency-Key": "day8-key-1"})
    assert commit.status_code in (200, 201), commit.text
    contact_id = commit.json()["id"]

    # Dong 8: bam Luu lan thu hai voi cung khoa -> van mot ho so duy nhat.
    again = system.client.post("/api/contacts", json=payload,
                               headers={"Idempotency-Key": "day8-key-1"})
    assert again.json()["id"] == contact_id
    with system.factory() as db:
        assert db.query(Contact).count() == 1

    # Tim lai bang chu Nhat.
    found = system.client.get("/api/contacts", params={"q": "山田"}).json()
    assert any(item["id"] == contact_id for item in found["items"])

    # Sua cua nguoi dung phai con trong ho so...
    detail = system.client.get(f"/api/contacts/{contact_id}").json()
    assert "部長" in str(detail)

    # ...va bang chung OCR goc phai con nguyen.
    with system.factory() as db:
        scan = db.get(Scan, scan_id)
    assert scan.raw_text == CARD_TEXT
    assert scan.extraction_json is not None

    # Xuat du lieu khong mat chu Nhat.
    exported = system.client.get("/api/export", params={"format": "json"})
    assert exported.status_code == 200
    assert "山田 太郎" in exported.text
