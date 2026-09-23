"""Ngay 28: trang Mang luoi.

Hai thu duoc kiem o day. Thu nhat: trang co tra loi dung cau hoi no sinh ra
de tra loi - "cong ty nao toi da co nhieu hon mot dau moi". Thu hai, va
quan trong hon: nhan tren do thi den tu OCR cua tam the, tuc tu van ban
NGOAI he thong - nen mot ten cong ty co dau nhay kep khong duoc lam hong ca
hinh.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import lib.api as api

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")

SUC_KHOE = {"status": "ok", "env": "test", "config": {
    "ocr_provider": "mock", "ocr_credentials_present": False,
    "ocr_configured": True, "extractor": "heuristic",
    "gemini_key_present": False, "gemini_model_set": False,
    "enrich_enabled": True, "login_required": False}}


def ho_so(*cap: tuple[str, str]) -> dict:
    return {"items": [{"id": f"hs{i}", "name": ten, "company": cty,
                       "emails": [], "phones": [], "updated_at": "2026-09-28"}
                      for i, (ten, cty) in enumerate(cap)],
            "total": len(cap), "page": 1, "size": 100}


def chay(du_lieu: dict) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "health", lambda: SUC_KHOE)
        mp.setattr(api, "search_contacts",
                   lambda q="", page=1, size=20: du_lieu)
        at.switch_page("app_pages/graph.py")
        at.run()
    assert not at.exception, at.exception
    return at


def dot(at: AppTest) -> str:
    """Chuoi DOT that su duoc gui xuong trinh duyet.

    `graphviz_chart` khong co lop phan tu rieng trong AppTest, nen no ve
    duoi dang `UnknownElement` va `.value` la None; chuoi nam trong
    `.proto.spec`.
    """
    bieu_do = at.get("graphviz_chart")
    assert bieu_do, "khong ve duoc do thi nao"
    return bieu_do[0].proto.spec


def test_chua_co_ho_so_thi_huong_dan_chu_khong_ve_hinh_rong():
    at = chay({"items": [], "total": 0, "page": 1, "size": 100})

    assert at.info and "Quét một tấm thẻ" in at.info[0].value
    assert not at.get("graphviz_chart")


def test_moi_ho_so_va_cong_ty_deu_co_mat_tren_hinh():
    at = chay(ho_so(("An", "Công ty A"), ("Bình", "Công ty B")))
    hinh = dot(at)

    assert "An" in hinh and "Bình" in hinh
    assert "Công ty A" in hinh and "Công ty B" in hinh


def test_cong_ty_nhieu_dau_moi_duoc_dem_va_goi_ten():
    """Day la ca cau hoi ma trang nay sinh ra de tra loi."""
    at = chay(ho_so(("An", "Công ty A"), ("Bình", "Công ty A"),
                    ("Cường", "Công ty B")))

    assert "2 đầu mối" in dot(at)
    nhan = [m.value for m in at.expander[0].markdown]
    assert any("An" in x and "Bình" in x for x in nhan)


def test_ho_so_chua_ro_cong_ty_van_len_hinh():
    """Bo qua chung thi so tren hinh lech voi so o trang Ho so, va khong ai
    biet vi sao."""
    at = chay(ho_so(("An", ""), ("Bình", "Công ty B")))

    assert "chưa rõ công ty" in dot(at)
    assert "An" in dot(at)


def test_ten_cong_ty_co_dau_nhay_khong_lam_hong_chuoi_DOT():
    """Nhan den tu OCR cua tam the. Mot dau nhay kep trong ten - hay mot
    chuoi co chu dich - se cat doi chuoi DOT neu khong thoat, va ca hinh
    bien mat."""
    at = chay(ho_so(('An', 'Cty "Lớn" A'),
                    ('Bình', 'X"]; evil -> hack; ["')))
    hinh = dot(at)

    # Khong con dau nhay kep nao BEN TRONG nhan.
    assert 'label="Cty' in hinh
    assert "evil -> hack" not in hinh
    # Va hinh van la mot do thi hoan chinh.
    assert hinh.strip().startswith("digraph") and hinh.strip().endswith("}")


def test_so_lieu_tom_tat_khop_voi_du_lieu():
    at = chay(ho_so(("An", "Công ty A"), ("Bình", "Công ty A"),
                    ("Cường", "Công ty B")))
    so = {m.label: m.value for m in at.metric}

    assert so["Hồ sơ trên đồ thị"] == "3"
    assert so["Công ty"] == "2"
    assert so["Công ty nhiều đầu mối"] == "1"
