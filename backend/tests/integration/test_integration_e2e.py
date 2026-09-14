"""Tron hanh trinh: anh -> OCR -> trich xuat -> doi chieu -> ban nhap -> ho so.

Moc 16/09 cua ke hoach nang cap goi ten file nay.

KHAC GI SO VOI `test_failure_matrix_day8.py`: bo test do kiem luong chinh duoi
DIEU KIEN XAU (anh hong, dich vu loi, gui trung). Bo nay kiem luong chinh chay
DUNG cho CA BON NGON NGU cua de goc, va kiem nhung bat bien phai giu nguyen tu
dau den cuoi hanh trinh.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from types import SimpleNamespace

import app.pipeline as pipeline
from app.config import Settings, get_settings
from app.db import get_db
from app.main import app, get_session_factory
from app.models import Base, Contact, Scan
from app.services.extract.base import CardExtraction, ExtractedValue, PhoneValue

# Bon the, moi the mot ngon ngu cua de goc. Moi the deu co du: ten, cong ty,
# email, dien thoai - de kiem duoc tron bo truong tren moi ngon ngu.
CARDS = {
    "ja": {
        "raw": ("株式会社青葉テクノロジー\n営業本部\n部長 山田 太郎\n"
                "TEL: 03-5432-1098\ntaro.yamada@example.co.jp"),
        "name": "山田 太郎", "company": "株式会社青葉テクノロジー",
        "email": "taro.yamada@example.co.jp", "phone": "03-5432-1098",
        "search": "山田",
    },
    "ko": {
        "raw": ("주식회사 한빛소프트\n개발부\n대표이사 김민준\n"
                "TEL: 02-555-0142\nminjun.kim@example.co.kr"),
        "name": "김민준", "company": "주식회사 한빛소프트",
        "email": "minjun.kim@example.co.kr", "phone": "02-555-0142",
        "search": "김민준",
    },
    "zh": {
        "raw": ("北京科技有限公司\n研发部\n总经理 王小明\n"
                "TEL: 010-5555-0188\nxiaoming.wang@example.com.cn"),
        "name": "王小明", "company": "北京科技有限公司",
        "email": "xiaoming.wang@example.com.cn", "phone": "010-5555-0188",
        "search": "王小明",
    },
    "en": {
        "raw": ("Meridian Analytics Inc.\nClient Solutions\nJane Doe\n"
                "Tel: +1 (415) 555-0142\njane.doe@example.com"),
        "name": "Jane Doe", "company": "Meridian Analytics Inc.",
        "email": "jane.doe@example.com", "phone": "+1 (415) 555-0142",
        "search": "Meridian",
    },
}


def card_image(text: str) -> bytes:
    """Anh that de duong tiep nhan (magic bytes, EXIF, SHA-256) duoc chay."""
    image = Image.new("RGB", (900, 500), "white")
    draw = ImageDraw.Draw(image)
    for path in ("C:/Windows/Fonts/YuGothM.ttc", "C:/Windows/Fonts/msgothic.ttc"):
        try:
            font = ImageFont.truetype(path, 28)
            break
        except OSError:
            continue
    else:
        font = ImageFont.load_default(28)
    for index, line in enumerate(text.splitlines()):
        draw.text((40, 40 + index * 70), line, font=font, fill=(20, 20, 20))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture()
def system(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'e2e.db'}",
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


def stub(monkeypatch, card: dict, lang: str):
    def recognize(image, mime):
        from app.services.ocr.base import OcrResult
        return OcrResult(raw_text=card["raw"], provider="mock:test",
                         provider_version="t", detected_languages=[lang])

    def extract(image, mime, raw_text):
        return CardExtraction(
            full_names=[ExtractedValue(value=card["name"])],
            company_names=[ExtractedValue(value=card["company"])],
            emails=[ExtractedValue(value=card["email"])],
            phones=[PhoneValue(value=card["phone"], label="tel")],
        )

    monkeypatch.setattr(pipeline, "build_ocr",
                        lambda config: SimpleNamespace(recognize=recognize))
    monkeypatch.setattr(pipeline, "build_extractor",
                        lambda config: SimpleNamespace(name="t", extract=extract))


def journey(system, card: dict, lang: str, key: str) -> str:
    """Di het hanh trinh, tra ve ma ho so."""
    created = system.client.post(
        "/api/scans", files={"file": ("c.png", card_image(card["raw"]), "image/png")})
    assert created.status_code == 201
    scan_id = created.json()["id"]

    scan = system.client.get(f"/api/scans/{scan_id}").json()
    assert scan["status"] == "ocr_done"

    saved = system.client.post(
        "/api/contacts",
        json={"scan_id": scan_id, "revision": scan["draft_revision"]},
        headers={"Idempotency-Key": key})
    assert saved.status_code in (200, 201), saved.text
    return scan_id, saved.json()["id"]


# --- Tron hanh trinh cho tung ngon ngu ------------------------------------

@pytest.mark.parametrize("lang", list(CARDS))
def test_tron_hanh_trinh_cho_moi_ngon_ngu(system, monkeypatch, lang):
    """De goc neu bon ngon ngu: Anh, Han, Nhat, Trung."""
    card = CARDS[lang]
    stub(monkeypatch, card, lang)
    scan_id, contact_id = journey(system, card, lang, f"e2e-{lang}")

    detail = str(system.client.get(f"/api/contacts/{contact_id}").json())
    for field in ("name", "company", "email"):
        assert card[field] in detail, (lang, field)


@pytest.mark.parametrize("lang", list(CARDS))
def test_tim_lai_duoc_bang_chu_ban_dia(system, monkeypatch, lang):
    """Tim kiem phai chay voi Hangul va chu Han, khong chi voi Kana va Latin."""
    card = CARDS[lang]
    stub(monkeypatch, card, lang)
    _, contact_id = journey(system, card, lang, f"search-{lang}")

    found = system.client.get("/api/contacts", params={"q": card["search"]}).json()
    assert any(x["id"] == contact_id for x in found["items"]), lang


@pytest.mark.parametrize("lang", list(CARDS))
def test_bang_chung_OCR_goc_con_nguyen_sau_khi_luu(system, monkeypatch, lang):
    """Bat bien quan trong nhat cua du an: du lieu de do chat luong o Ngay 9
    khong duoc mat khi ho so duoc tao."""
    card = CARDS[lang]
    stub(monkeypatch, card, lang)
    scan_id, _ = journey(system, card, lang, f"evidence-{lang}")

    with system.factory() as db:
        scan = db.get(Scan, scan_id)
    assert scan.raw_text == card["raw"]
    assert scan.extraction_json is not None


# --- Bat bien xuyen suot hanh trinh ---------------------------------------

def test_xuat_du_lieu_giu_nguyen_moi_he_chu(system, monkeypatch):
    """Kana, Hangul va chu Han phai qua duoc ca ba dinh dang xuat."""
    for lang, card in CARDS.items():
        stub(monkeypatch, card, lang)
        journey(system, card, lang, f"export-{lang}")

    for fmt in ("json", "csv", "vcf"):
        response = system.client.get("/api/export", params={"format": fmt})
        assert response.status_code == 200, fmt
        text = response.content.decode("utf-8-sig")
        for card in CARDS.values():
            assert card["name"] in text, (fmt, card["name"])


def test_nhieu_the_khong_lan_du_lieu_sang_nhau(system, monkeypatch):
    ids = {}
    for lang, card in CARDS.items():
        stub(monkeypatch, card, lang)
        _, ids[lang] = journey(system, card, lang, f"isolate-{lang}")

    for lang, contact_id in ids.items():
        detail = str(system.client.get(f"/api/contacts/{contact_id}").json())
        assert CARDS[lang]["email"] in detail
        for other, card in CARDS.items():
            if other != lang:
                assert card["email"] not in detail, (lang, other)


def test_thong_ke_dem_dung_so_ngon_ngu(system, monkeypatch):
    """Bang dieu khien phai phan biet duoc bon ngon ngu, khong gop het vao mot."""
    for lang, card in CARDS.items():
        stub(monkeypatch, card, lang)
        journey(system, card, lang, f"stats-{lang}")

    stats = system.client.get("/api/stats").json()
    assert stats["totals"]["contacts"] == len(CARDS)
    # Moi the mot ngon ngu khac nhau -> khong duoc gop chung mot nhan.
    assert len(stats["languages"]) >= 3, stats["languages"]


def test_luu_hai_lan_cung_khoa_chi_tao_mot_ho_so(system, monkeypatch):
    card = CARDS["ja"]
    stub(monkeypatch, card, "ja")
    scan_id, first = journey(system, card, "ja", "same-key")

    scan = system.client.get(f"/api/scans/{scan_id}").json()
    again = system.client.post(
        "/api/contacts",
        json={"scan_id": scan_id, "revision": scan["draft_revision"]},
        headers={"Idempotency-Key": "same-key"})

    assert again.json()["id"] == first
    with system.factory() as db:
        assert db.query(Contact).count() == 1
