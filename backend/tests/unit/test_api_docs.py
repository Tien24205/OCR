"""Tai lieu OpenAPI - moc 17/09.

LOI DA MAC PHAI, HAI LAN, deu la loi im lang - tai lieu van sinh ra, chi la
thieu mot phan ma khong bao gi:

  1. Goi `apply()` ngay sau `include_router()` thay vi o CUOI file. Phan lon
     endpoint cua `main.py` khai bao sau do nen chua ton tai luc goi.
  2. Chi lap qua `app.routes`. FastAPI ban nay khong trai phang router duoc
     include - no dat mot `_IncludedRouter` vao do, nen toan bo endpoint cua
     `contact_routes.py` bi bo sot.
"""

from __future__ import annotations

from app.api_docs import ENDPOINTS, ERROR_CODES
from app.main import app


def schema() -> dict:
    return app.openapi()


def operations():
    for path, ops in schema()["paths"].items():
        for method, op in ops.items():
            yield method, path, op


def test_moi_endpoint_deu_co_mo_ta():
    """Neu quen goi apply() o dung cho, test nay that bai thay vi de tai lieu
    thieu mot nua ma khong ai biet."""
    missing = [f"{m.upper()} {p}" for m, p, op in operations()
               if not op.get("summary")]
    assert missing == []


def test_endpoint_cua_router_duoc_include_cung_co_mo_ta():
    """Khoa lai loi (2): bo sot toan bo contact_routes.py."""
    ops = {(m, p) for m, p, _ in operations()}
    assert ("post", "/api/contacts") in ops
    summaries = {p: op["summary"] for m, p, op in operations() if m == "post"}
    assert "hồ sơ" in summaries["/api/contacts"]


def test_endpoint_cua_main_cung_co_mo_ta():
    """Khoa lai loi (1): apply() chay truoc khi main.py khai bao xong route."""
    summaries = {p: op["summary"] for m, p, op in operations() if m == "post"}
    assert "danh thiếp" in summaries["/api/scans"]


def test_moi_endpoint_deu_duoc_phan_nhom():
    ungrouped = [f"{m.upper()} {p}" for m, p, op in operations()
                 if not op.get("tags")]
    assert ungrouped == []


def test_khong_co_mo_ta_thua_tro_toi_endpoint_khong_ton_tai():
    """Mo ta cho endpoint da bi xoa se am tham khong bao gio hien ra."""
    real = {(m, p) for m, p, _ in operations()}
    assert [k for k in ENDPOINTS if k not in real] == []


def test_bang_ma_loi_nam_trong_mo_ta_chung():
    description = schema()["info"]["description"]
    for code in ERROR_CODES:
        assert code in description


def test_mo_ta_neu_ro_chua_co_xac_thuc():
    """Bo qua diem nay khi mo API ra ngoai la loi nghiem trong."""
    assert "Xác thực" in schema()["info"]["description"]


def test_xuat_du_lieu_liet_ke_ca_ba_dinh_dang():
    export = next(op for m, p, op in operations() if p == "/api/export")
    for fmt in ("json", "csv", "vcf"):
        assert fmt in export["description"]
