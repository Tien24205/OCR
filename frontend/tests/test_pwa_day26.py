"""Ngay 26: cac the PWA de trang cai duoc len man hinh chinh.

Bo test nay khong dung ca may chu Streamlit len. No kiem ba thu doc lap
duoc, va la ba thu ma neu sai thi trang khong cai duoc - trong khi trang
VAN chay binh thuong, nen khong co dau hieu gi bao rang co van de.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from asgi_app import CO_ICON, ChenTheVaoHead, _icon_png, _manifest


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------

def test_manifest_du_cac_truong_bat_buoc_de_cai_duoc():
    """Thieu bat ky truong nao trong so nay la Chrome khong moi cai dat, va
    no khong bao gi ca - nut "Cai ung dung" chi don gian khong hien ra."""
    m = _manifest()

    assert m["name"] and m["short_name"]
    assert m["start_url"] == "/"
    assert m["display"] == "standalone"
    assert m["icons"]


def test_manifest_co_du_hai_co_icon_android_doi():
    co = {i["sizes"] for i in _manifest()["icons"]}

    assert "192x192" in co and "512x512" in co


def test_icon_khai_maskable():
    """Khong khai thi Android dan mot o vuong trang len man hinh thay vi cat
    icon theo hinh dang cua may."""
    assert all("maskable" in i["purpose"] for i in _manifest()["icons"])


# --------------------------------------------------------------------------
# Icon
# --------------------------------------------------------------------------

@pytest.mark.parametrize("canh", CO_ICON)
def test_icon_sinh_dung_kich_thuoc_va_doc_duoc(canh):
    du_lieu = _icon_png(canh)

    with Image.open(BytesIO(du_lieu)) as anh:
        assert anh.size == (canh, canh)
        assert anh.format == "PNG"


def test_icon_khong_phai_mot_o_trong():
    """Mot icon toan mot mau van la PNG hop le va van qua moi phep kiem ky
    thuat - nhung tren man hinh no la mot o trong."""
    with Image.open(BytesIO(_icon_png(192))) as anh:
        mau = anh.convert("RGB").getcolors(maxcolors=1 << 16)

    assert mau is not None and len(mau) >= 3


# --------------------------------------------------------------------------
# Chen the vao <head>
# --------------------------------------------------------------------------

def _app_gia() -> TestClient:
    async def trang(request):
        return HTMLResponse("<html><head><title>x</title></head><body>ND</body></html>")

    async def du_lieu(request):
        return JSONResponse({"a": 1})

    return TestClient(Starlette(
        routes=[Route("/", trang), Route("/api", du_lieu)],
        middleware=[Middleware(ChenTheVaoHead)],
    ))


def test_the_nam_ben_trong_head_chu_khong_phai_trong_body():
    """The `<link rel="manifest">` nam trong `<body>` thi trinh duyet BO QUA
    no - trang van hien binh thuong, chi la khong cai duoc. Do la ly do phai
    kiem vi tri chu khong chi kiem su co mat."""
    html = _app_gia().get("/").text

    assert "</head>" in html
    truoc_head = html.split("</head>")[0]
    assert '<link rel="manifest" href="/manifest.webmanifest">' in truoc_head
    assert 'name="apple-mobile-web-app-capable"' in truoc_head
    assert '<link rel="apple-touch-icon" href="/icon-180.png">' in truoc_head
    assert "serviceWorker" in truoc_head


def test_do_dai_noi_dung_duoc_tinh_lai():
    """Giu nguyen `content-length` cu sau khi chen them byte thi trinh duyet
    cat mat phan duoi cua trang - va trieu chung se la mot trang trang."""
    r = _app_gia().get("/")

    assert int(r.headers["content-length"]) == len(r.content)
    assert r.text.endswith("</html>")


def test_khong_dong_vao_cau_tra_loi_khong_phai_html():
    """WebSocket cua Streamlit, tep tinh va anh deu di qua day."""
    r = _app_gia().get("/api")

    assert r.json() == {"a": 1}
    assert "manifest" not in r.text


# --------------------------------------------------------------------------
# Giao dien (Ngay 31)
# --------------------------------------------------------------------------

def test_css_di_kem_cac_the_pwa():
    """Mat khuc CSS thi trang van chay, chi xau di - nhung mat NO MA KHONG AI
    BIET thi moi lan sua giao dien sau nay deu sua vao cho khong con duoc
    nap."""
    from asgi_app import THE_HEAD

    assert b"<style>" in THE_HEAD
    assert b"stMainBlockContainer" in THE_HEAD


def test_mau_icon_trung_voi_mau_theme():
    """Mau nay nam o HAI tep: `MAU_NHAN` trong asgi_app.py ve icon PWA, va
    `primaryColor` trong .streamlit/config.toml to nut.

    Doi mot cai ma quen cai kia thi icon tren man hinh chinh mot mau, app mo
    ra mot mau khac - khong hong gi, nen khong ai phat hien ra.
    """
    import tomllib
    from pathlib import Path

    from asgi_app import MAU_NEN, MAU_NHAN

    goc = Path(__file__).resolve().parents[2]
    cau_hinh = tomllib.loads((goc / ".streamlit" / "config.toml").read_text("utf-8"))

    assert cau_hinh["theme"]["primaryColor"].lower() == MAU_NHAN.lower()
    assert cau_hinh["theme"]["backgroundColor"].lower() == MAU_NEN.lower()
