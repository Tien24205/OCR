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
    assert system.client.get("/api/scans").json() == {"items": [], "total": 0, "page": 1, "size": 12}


# --- So thu tu va tim lai ban quet cu ---------------------------------------

def test_moi_ban_quet_co_so_thu_tu_tang_dan_khong_doi(system, monkeypatch):
    providers(monkeypatch)
    ids = [send(system) for _ in range(3)]

    so = {x["id"]: x["seq"] for x in system.client.get("/api/scans").json()["items"]}

    assert [so[i] for i in ids] == [1, 2, 3]
    assert system.client.get(f"/api/scans/{ids[1]}").json()["seq"] == 2


def test_xoa_mot_ban_quet_khong_don_so_lai(system, monkeypatch):
    """So da cap la ten goi cua ban quet: don lai thi "#3" hom qua thanh mot
    the khac hom nay."""
    providers(monkeypatch)
    ids = [send(system) for _ in range(3)]
    system.client.delete(f"/api/scans/{ids[1]}")
    moi = send(system)

    so = {x["id"]: x["seq"] for x in system.client.get("/api/scans").json()["items"]}

    assert so[ids[2]] == 3 and so[moi] == 4


def test_lat_trang_de_ve_ban_quet_cu_hon(system, monkeypatch):
    providers(monkeypatch)
    for _ in range(5):
        send(system)

    trang1 = system.client.get("/api/scans", params={"limit": 2, "page": 1}).json()
    trang3 = system.client.get("/api/scans", params={"limit": 2, "page": 3}).json()

    assert trang1["total"] == 5
    assert [x["seq"] for x in trang1["items"]] == [5, 4]
    assert [x["seq"] for x in trang3["items"]] == [1]


def test_tim_theo_so_thu_tu(system, monkeypatch):
    providers(monkeypatch)
    ids = [send(system) for _ in range(3)]

    d = system.client.get("/api/scans", params={"so": 2}).json()

    assert [x["id"] for x in d["items"]] == [ids[1]] and d["total"] == 1
    assert system.client.get("/api/scans", params={"so": 99}).json()["items"] == []
