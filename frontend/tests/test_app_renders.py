"""Kiem tra ca ba trang Streamlit chay duoc, khong nem exception.

Dung `AppTest`: chay app headless ngay trong tien trinh pytest, khong can mo
trinh duyet cung khong can server. Backend duoc gia lap nen test KHONG goi mang.

Loi ma bo test nay bat duoc: sai ten icon Material Symbols, sai tham so widget,
loi chinh ta trong `st.session_state`, va truong hop backend chet.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import lib.api as api

# AppTest giai duong dan tuong doi theo FILE GOI no, khong theo thu muc dang
# chay - nen dung duong dan tuyet doi de test chay duoc tu bat ky dau.
APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Chan moi loi goi backend that."""
    monkeypatch.setattr(api, "health", lambda: {
        "status": "ok",
        "env": "test",
        "config": {
            "ocr_provider": "mock",
            "ocr_credentials_present": False,
            "ocr_configured": True,
            "extractor": "heuristic",
            "gemini_key_present": False,
            "gemini_model_set": False,
            "enrich_enabled": True,
        },
    })


def _run(page: str | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    if page:
        at.switch_page(page)
    at.run()
    assert not at.exception, at.exception
    return at


def test_trang_quet_the_chay_duoc():
    at = _run()
    # Nguoi dung phai chon duoc giua camera va tai anh (FR-01, FR-02:
    # camera bi tu choi van dung duoc duong tai anh), va co duong tai hang loat
    # de endpoint /api/scans/batch thuc su dung duoc tu giao dien.
    assert at.segmented_control[0].options == [
        "Chụp bằng camera", "Tải ảnh lên", "Tải hàng loạt"]


def test_banner_trang_thai_hien_o_sidebar():
    at = _run()
    assert any("Backend đang chạy" in s.value for s in at.sidebar.success)


def test_trang_kiem_tra_khong_co_ban_quet():
    """Vao thang trang Kiem tra khi chua quet gi thi phai co huong dan,
    khong duoc nem KeyError."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "list_scans", lambda limit=12: {"items": []})
        at = _run("app_pages/review.py")
    assert at.info[0].value.startswith("Chưa có bản quét nào")


def test_chon_lai_mot_ban_quet_cu_bang_luoi_anh():
    """LOI DA SUA: trang Kiem tra chi mo duoc ban quet vua gui. Tai lai trang
    la mat duong vao, va ban quet da xong nam lai trong CSDL khong mo ra
    duoc."""
    cu = [{"id": "scan-cu", "status": "ocr_done", "image_ref": "a" * 64,
           "created_at": "2026-09-21T08:15:00", "contact_id": None,
           "full_name": "山田 太郎", "company_name": "株式会社青葉"}]

    at = AppTest.from_file(APP, default_timeout=30)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "list_scans", lambda limit=12: {"items": cu})
        mp.setattr(api, "get_image", lambda ref: b"")
        at.switch_page("app_pages/review.py")
        at.run()
        assert not at.exception, at.exception
        # Ten tren the phai hien ra, khong the bat nguoi dung chon theo UUID.
        assert any("山田 太郎" in c.value for c in at.caption)

        nut = [b for b in at.button if b.label == "Mở"]
        assert nut, "khong co duong mo lai ban quet cu"
        nut[0].click().run()

    assert at.session_state["current_scan_id"] == "scan-cu"


def test_trang_ho_so_hien_loi_api_khong_vo_giao_dien():
    """Day 7 endpoint exists; unexpected API errors stay visible."""
    def _raise_404(*args, **kwargs):
        raise api.ApiError("NOT_FOUND", "Not Found", False, 404)

    at = AppTest.from_file(APP, default_timeout=30)
    at.switch_page("app_pages/contacts.py")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "search_contacts", _raise_404)
        at.run()
    assert not at.exception, at.exception
    assert at.error[0].value == "Not Found"


# --- Ba trang thai cua thanh ben ------------------------------------------

def _health(**thay_doi) -> dict:
    data = {
        "status": "ok", "env": "test",
        "config": {"ocr_provider": "tesseract", "ocr_credentials_present": False,
                   "ocr_configured": True, "extractor": "gemini",
                   "gemini_key_present": True, "gemini_model_set": True,
                   "enrich_enabled": True},
        "verified": None,
    }
    data.update(thay_doi)
    return data


def test_chua_xac_minh_thi_khong_duoc_noi_la_da_chay_duoc():
    """Da dien .env KHONG co nghia la dich vu chay duoc (D1-02)."""
    at = AppTest.from_file(APP, default_timeout=30)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "health", lambda: _health())
        at.run()
    dong = " ".join(m.value for m in at.sidebar.markdown)
    assert "chưa xác minh dịch vụ" in dong
    assert "đã xác minh" not in dong


def test_sau_khi_xac_minh_thi_hien_ket_qua_that_kem_gio():
    at = AppTest.from_file(APP, default_timeout=30)
    da_xac_minh = _health(verified={
        "checked_at": "2026-09-21T08:15:00+00:00", "service_calls": 1,
        "ready": True, "measurable": True,
        "checks": [
            {"component": "ocr", "provider": "tesseract", "state": "verified",
             "detail": "Tesseract 5.5.0, đủ gói ja+en.", "ms": None},
            {"component": "extract", "provider": "gemini", "state": "failed",
             "detail": "Model trả JSON sai schema.", "ms": None},
            {"component": "enrich", "provider": "bật", "state": "skipped",
             "detail": "Cần Gemini chạy được.", "ms": None},
        ],
    })
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "health", lambda: _health(**{"verified": da_xac_minh["verified"]}))
        at.run()
    dong = " ".join(m.value for m in at.sidebar.markdown)
    assert "✓ đã xác minh lúc 08:15 — Tesseract 5.5.0" in dong
    assert "✗ lỗi lúc 08:15 — Model trả JSON sai schema." in dong
    # Phep suy ra (skipped) khong duoc khoac ao "da xac minh".
    assert "Tra cứu — bật, cần Gemini" in dong


# --- Lo anh hang loat -----------------------------------------------------

LO = [{"filename": "a.jpg", "id": "scan-a"}, {"filename": "b.jpg", "id": "scan-b"}]


def test_lo_anh_van_con_sau_khi_doi_trang_va_quay_lai():
    """LOI DA SUA: bang ket qua nam trong khoi `if` cua nut Gui ca lo, nen bat
    ky lan chay lai nao - ke ca chi doi sang trang khac roi quay ve - cung xoa
    sach no. Cac ban quet van chay o backend nhung khong con duong mo lai, nen
    nguoi dung tuong mat va quet lai tu dau."""
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["batch_items"] = [dict(x) for x in LO]
    at.session_state["capture_mode"] = "Tải hàng loạt"

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "scans_status", lambda ids: {
            "items": [{"id": i, "status": "ocr_done"} for i in ids]})
        at.switch_page("app_pages/review.py")   # doi sang trang khac
        at.run()
        at.switch_page("app_pages/capture.py")  # roi quay lai
        at.run()

    assert not at.exception, at.exception
    assert at.session_state["batch_items"], "danh sach lo bi mat khi doi trang"
    assert any("Đã nhận 2/2 ảnh" in s.value for s in at.success)
    ten_tep = {row["Tệp"] for row in at.dataframe[0].value.to_dict("records")}
    assert ten_tep == {"a.jpg", "b.jpg"}


def test_ca_lo_chi_ton_mot_loi_goi_moi_lan_lam_moi():
    """LOI DA SUA: bang theo doi goi `get_scan` cho TUNG anh, moi 2 giay. Ba
    anh la 90 loi goi/phut, vuot gioi han 60 - chinh cai bang theo doi lam
    nguoi dung bi chan, va no hien "Vuot qua 60 loi goi moi phut" thay cho
    trang thai. Mot lo 10 anh la 300 loi goi/phut."""
    lo = [{"filename": f"{i}.jpg", "id": f"scan-{i}"} for i in range(10)]
    goi = []

    def _status(ids):
        goi.append(list(ids))
        return {"items": [{"id": i, "status": "processing"} for i in ids]}

    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["batch_items"] = lo
    at.session_state["capture_mode"] = "Tải hàng loạt"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "scans_status", _status)
        mp.setattr(api, "get_scan", _khong_duoc_goi)
        at.switch_page("app_pages/capture.py")
        at.run()

    assert not at.exception, at.exception
    assert len(goi) == 1, f"10 anh -> {len(goi)} loi goi, dang ra phai la 1"
    assert len(goi[0]) == 10


def _khong_duoc_goi(*args, **kwargs):
    raise AssertionError("hoi tung ban quet mot -> se dung gioi han tan suat")


def test_khong_hoi_lai_nhung_ban_quet_da_xong():
    """Trang thai ket thuc khong quay lai duoc, nen hoi lai la lang phi han
    muc. Lo xong hoan toan thi bang khong duoc goi mang lan nao nua."""
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["batch_items"] = [dict(x) for x in LO]
    at.session_state["batch_status"] = {"scan-a": "ocr_done", "scan-b": "failed"}
    at.session_state["capture_mode"] = "Tải hàng loạt"

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "scans_status", _khong_duoc_goi)
        mp.setattr(api, "get_scan", _khong_duoc_goi)
        at.switch_page("app_pages/capture.py")
        at.run()

    assert not at.exception, at.exception
    trang_thai = {r["Tệp"]: r["Trạng thái"]
                  for r in at.dataframe[0].value.to_dict("records")}
    assert trang_thai == {"a.jpg": "xong — mở để kiểm tra", "b.jpg": "lỗi"}


def test_lo_anh_doc_trang_thai_tu_backend_chu_khong_nho_trang_thai_cu():
    """Luc gui, moi anh deu `pending`. Neu giao dien nho lai trang thai do thi
    lo se mai mai hien 'dang cho' du backend da xong tu lau."""
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["batch_items"] = [{"filename": "a.jpg", "id": "scan-a",
                                        "status": "pending"}]
    at.session_state["capture_mode"] = "Tải hàng loạt"

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "scans_status", lambda ids: {
            "items": [{"id": i, "status": "ocr_done"} for i in ids]})
        at.switch_page("app_pages/capture.py")
        at.run()

    assert not at.exception, at.exception
    trang_thai = at.dataframe[0].value.to_dict("records")[0]["Trạng thái"]
    assert "xong" in trang_thai


# --- Trang Tong quan (Bang dieu khien) -----------------------------------

EMPTY_STATS = {
    "totals": {"scans": 0, "contacts": 0, "organizations": 0, "enrichments": 0},
    "scans_by_status": {}, "contacts_by_review": {}, "enrichments_by_status": {},
    "languages": {}, "agent_actions": {}, "missing_critical": {},
    "confidence": {"measured_scans": 0, "average": None, "below_half": 0},
    "contacts_per_day": [], "top_organizations": [],
}

FULL_STATS = {
    "totals": {"scans": 12, "contacts": 9, "organizations": 5, "enrichments": 7},
    "scans_by_status": {"committed": 9, "ocr_done": 2, "failed": 1},
    "contacts_by_review": {"reviewed": 9},
    "enrichments_by_status": {"verified": 5, "not_found": 2},
    "languages": {"ja": 7, "en": 5},
    "agent_actions": {"proceed": 20, "retry": 3, "escalate": 2},
    "missing_critical": {"missing_name": 1},
    "confidence": {"measured_scans": 12, "average": 0.82, "below_half": 1},
    "contacts_per_day": [{"date": "2026-09-13", "contacts": 4},
                         {"date": "2026-09-14", "contacts": 5}],
    "top_organizations": [{"organization": "株式会社青葉テクノロジー", "contacts": 3}],
}


def test_tong_quan_khi_kho_du_lieu_rong(monkeypatch):
    """Chua quet gi thi phai huong dan, khong duoc ve bieu do rong hay no."""
    monkeypatch.setattr(api, "stats", lambda: EMPTY_STATS)
    at = _run("app_pages/dashboard.py")
    assert any("Chưa có bản quét nào" in i.value for i in at.info)


def test_tong_quan_hien_day_du_so_lieu(monkeypatch):
    monkeypatch.setattr(api, "stats", lambda: FULL_STATS)
    at = _run("app_pages/dashboard.py")
    values = [m.value for m in at.metric]
    assert "12" in values and "9" in values
    assert any("82%" in str(v) for v in values)


def test_tong_quan_bao_loi_khi_backend_chet(monkeypatch):
    def _down():
        raise api.ApiError("BACKEND_UNREACHABLE", "Khong ket noi duoc", True, 0)

    monkeypatch.setattr(api, "stats", _down)
    at = AppTest.from_file(APP, default_timeout=30)
    at.switch_page("app_pages/dashboard.py")
    at.run()
    assert not at.exception, at.exception
    assert at.error


# --- Che do tai hang loat (IP-05) ----------------------------------------

def test_tai_hang_loat_co_trong_giao_dien(monkeypatch):
    """LOI DA SUA: endpoint /api/scans/batch ton tai tu moc 14/09 nhung khong
    co giao dien nao goi duoc no - mot tinh nang khong ai dung toi duoc."""
    at = _run()
    at.segmented_control[0].set_value("Tải hàng loạt").run()
    assert not at.exception, at.exception
    assert at.file_uploader, "khong co o chon nhieu tep"


def test_tai_hang_loat_bao_ro_gioi_han(monkeypatch):
    at = _run()
    at.segmented_control[0].set_value("Tải hàng loạt").run()
    assert any("10" in c.value for c in at.caption)
