"""Danh sach ban quet gan day - duong quay lai mot the da quet.

VI SAO CAN: `current_scan_id` song trong phien trinh duyet. Tai lai trang la
mat duong vao, va ban quet da xu ly xong nam lai trong CSDL ma khong co cach
nao mo ra. Da tung co 9 ban quet `ocr_done` bi ket dung kieu do.
"""

from __future__ import annotations

from app.main import MAX_LIST_SCANS
from test_pipeline_day4 import system, send, providers      # noqa: F401


def test_ban_quet_moi_nhat_dung_dau(system, monkeypatch):
    providers(monkeypatch)
    ids = [send(system) for _ in range(3)]

    items = system.client.get("/api/scans").json()["items"]

    assert [x["id"] for x in items[:3]] == list(reversed(ids))


def test_kem_ten_va_cong_ty_de_nhan_ra_the(system, monkeypatch):
    """Mot luoi anh thu nho ma chi co ma UUID thi khong chon duoc the nao."""
    providers(monkeypatch)
    scan_id = send(system)

    item = next(x for x in system.client.get("/api/scans").json()["items"]
                if x["id"] == scan_id)

    assert item["image_ref"] and item["created_at"]
    assert item["full_name"] or item["company_name"]
    assert item["status"] == "ocr_done"


def test_limit_bi_chan_tren_va_chan_duoi(system, monkeypatch):
    """Giao dien tai mot anh cho MOI muc, nen `limit` do nguoi goi dat chinh
    la so loi goi tai anh. Khong chan thi `limit=1000` bien trang Kiem tra
    thanh mot tran tai anh."""
    providers(monkeypatch)
    send(system)

    assert len(system.client.get("/api/scans", params={"limit": 9999}).json()["items"]) <= MAX_LIST_SCANS
    assert len(system.client.get("/api/scans", params={"limit": 0}).json()["items"]) == 1


def test_khong_co_ban_quet_nao_thi_tra_ve_rong(system):
    assert system.client.get("/api/scans").json() == {"items": []}
