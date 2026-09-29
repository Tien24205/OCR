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
        "Chụp bằng camera", "Tải ảnh lên"]


def test_banner_trang_thai_hien_o_sidebar():
    at = _run()
    assert any("Backend đang chạy" in s.value for s in at.sidebar.success)


def test_trang_kiem_tra_khong_co_ban_quet():
    """Vao thang trang Kiem tra khi chua quet gi thi phai co huong dan,
    khong duoc nem KeyError."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "list_scans", lambda **kw: {"items": []})
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
        mp.setattr(api, "list_scans", lambda **kw: {"items": cu})
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
    at.session_state["capture_mode"] = "Tải ảnh lên"

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
    at.session_state["capture_mode"] = "Tải ảnh lên"
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
    at.session_state["capture_mode"] = "Tải ảnh lên"

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
    at.session_state["capture_mode"] = "Tải ảnh lên"

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "scans_status", lambda ids: {
            "items": [{"id": i, "status": "ocr_done"} for i in ids]})
        at.switch_page("app_pages/capture.py")
        at.run()

    assert not at.exception, at.exception
    trang_thai = at.dataframe[0].value.to_dict("records")[0]["Trạng thái"]
    assert "xong" in trang_thai


# --- Trang Nhat ky hoat dong (thay trang Tong quan) -----------------------

NHAT_KY = [
    {"luc": "2026-09-29T08:00:00+00:00", "ai": "an@cty.vn", "hanh_dong": "quet_the",
     "loai": "ban_quet", "ma": "scan-1", "chi_tiet": {"so_anh": 3, "hang_loat": True}},
    {"luc": "2026-09-29T08:05:00+00:00", "ai": "an@cty.vn", "hanh_dong": "luu_ho_so",
     "loai": "ho_so", "ma": "hs-1", "chi_tiet": {"kieu": "moi"}},
    {"luc": "2026-09-29T08:10:00+00:00", "ai": "an@cty.vn", "hanh_dong": "xuat_du_lieu",
     "loai": None, "ma": None, "chi_tiet": {"dinh_dang": "csv", "so_ho_so": 4}},
    {"luc": "2026-09-29T08:11:00+00:00", "ai": "an@cty.vn", "hanh_dong": "dang_nhap_that_bai",
     "loai": "tai_khoan", "ma": None, "chi_tiet": {}},
]


def test_nhat_ky_khi_chua_co_hoat_dong(monkeypatch):
    monkeypatch.setattr(api, "nhat_ky_kiem_toan", lambda **kw: {"items": []})
    at = _run("app_pages/audit.py")
    assert any("Chưa có hoạt động nào" in i.value for i in at.info)


def test_nhat_ky_hien_so_lieu_va_bang(monkeypatch):
    monkeypatch.setattr(api, "nhat_ky_kiem_toan", lambda **kw: {"items": NHAT_KY})
    at = _run("app_pages/audit.py")
    so = {m.label: m.value for m in at.metric}
    assert so["Hoạt động"] == "4"
    assert so["Thẻ đã quét"] == "3"
    assert so["Lần xuất dữ liệu"] == "1"
    assert so["Đăng nhập thất bại"] == "1"
    bang = at.dataframe[0].value.to_dict("records")
    assert {r["Hoạt động"] for r in bang} == {
        "Quét thẻ", "Lưu hồ sơ", "Xuất dữ liệu", "Đăng nhập thất bại"}
    assert any(r["Chi tiết"] == "CSV · 4 hồ sơ" for r in bang)


def test_nhat_ky_loc_theo_loai(monkeypatch):
    monkeypatch.setattr(api, "nhat_ky_kiem_toan", lambda **kw: {"items": NHAT_KY})
    at = _run("app_pages/audit.py")
    at.pills[0].set_value(["xuat_du_lieu"]).run()
    assert not at.exception, at.exception
    assert [r["Hoạt động"] for r in at.dataframe[0].value.to_dict("records")] == ["Xuất dữ liệu"]


def test_nhat_ky_bao_loi_khi_backend_chet(monkeypatch):
    def _down(**kw):
        raise api.ApiError("BACKEND_UNREACHABLE", "Khong ket noi duoc", True, 0)

    monkeypatch.setattr(api, "nhat_ky_kiem_toan", _down)
    at = AppTest.from_file(APP, default_timeout=30)
    at.switch_page("app_pages/audit.py")
    at.run()
    assert not at.exception, at.exception
    assert at.error


# --- Che do tai hang loat (IP-05) ----------------------------------------

def test_tai_hang_loat_co_trong_giao_dien(monkeypatch):
    """LOI DA SUA: endpoint /api/scans/batch ton tai tu moc 14/09 nhung khong
    co giao dien nao goi duoc no - mot tinh nang khong ai dung toi duoc."""
    at = _run()
    at.segmented_control[0].set_value("Tải ảnh lên").run()
    assert not at.exception, at.exception
    assert at.file_uploader, "khong co o chon nhieu tep"


def test_tai_hang_loat_bao_ro_gioi_han(monkeypatch):
    at = _run()
    at.segmented_control[0].set_value("Tải ảnh lên").run()
    assert any("10" in c.value for c in at.caption)


# --- Chon ban quet: so thu tu, lat trang, tim theo so --------------------

def _ban_quet(seq: int) -> dict:
    return {"id": f"scan-{seq}", "seq": seq, "status": "ocr_done", "image_ref": "a" * 64,
            "created_at": "2026-09-21T08:15:00", "contact_id": None,
            "full_name": f"Người {seq}", "company_name": None}


def test_chon_ban_quet_hien_so_thu_tu_va_lat_trang():
    goi = []

    def _list(limit=12, page=1, so=None):
        goi.append({"page": page, "so": so})
        if so:
            return {"items": [_ban_quet(so)], "total": 1, "page": 1, "size": limit}
        tren = 30 - (page - 1) * limit
        return {"items": [_ban_quet(s) for s in range(tren, max(tren - limit, 0), -1)],
                "total": 30, "page": page, "size": limit}

    at = AppTest.from_file(APP, default_timeout=30)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "list_scans", _list)
        mp.setattr(api, "get_image", lambda ref: b"")
        at.switch_page("app_pages/review.py")
        at.run()
        assert not at.exception, at.exception
        assert any("#30" in c.value for c in at.caption)
        assert any("Trang 1/3" in c.value for c in at.caption)

        next(b for b in at.button if b.label == "Cũ hơn").click().run()
        assert goi[-1]["page"] == 2
        assert any("#18" in c.value for c in at.caption)

        next(n for n in at.number_input if n.label == "Tìm theo số thứ tự").set_value(7).run()
        assert goi[-1]["so"] == 7
        assert any("#7" in c.value for c in at.caption)
        assert not any(b.label == "Cũ hơn" for b in at.button)


def test_phien_cu_con_nho_che_do_tai_hang_loat_khong_vo():
    """Che do "Tai hang loat" da gop vao "Tai anh len"; phien cu con nho gia
    tri cu thi phai duoc dua ve, khong duoc nem loi."""
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["capture_mode"] = "Tải hàng loạt"
    at.run()
    assert not at.exception, at.exception
    assert at.segmented_control[0].value == "Tải ảnh lên"
    assert at.file_uploader


def test_bam_mot_dong_nhat_ky_thi_hien_chi_tiet_day_du(monkeypatch):
    dong = [{"luc": "2026-09-29T08:05:00+00:00", "ai": "an@cty.vn", "hanh_dong": "sua_ho_so",
             "loai": "ho_so", "ma": "hs-1",
             "chi_tiet": {"phien_ban": 3, "truong_sua": ["emails", "phones"], "sua_ghi_chu": True},
             "ip": "203.0.113.7", "thiet_bi": "Mozilla/5.0 (Windows NT 10.0) Chrome/130",
             "doi_tuong": {"ten": "Nguyễn Minh An", "con": True}}]
    monkeypatch.setattr(api, "nhat_ky_kiem_toan", lambda **kw: {"items": dong})
    at = _run("app_pages/audit.py")
    bang = at.dataframe[0].value.to_dict("records")[0]
    assert bang["Đối tượng"] == "Hồ sơ: Nguyễn Minh An"
    assert bang["Chi tiết"] == "lên phiên bản 3 · sửa: email, điện thoại · sửa ghi chú"
    assert bang["IP"] == "203.0.113.7" and bang["Thiết bị"] == "Chrome · Windows"
