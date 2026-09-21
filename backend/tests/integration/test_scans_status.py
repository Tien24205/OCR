"""Trang thai ca lo trong mot loi goi - chan lai loi tu gay nghen tan suat.

Giao dien theo doi lo bang cach hoi lai vai giay mot lan. Hoi tung ban quet
mot thi so loi goi nhan theo so anh: lo 3 anh moi 2 giay la 90 loi goi mot
phut, trong khi gioi han la 60. Nguoi dung thay "Vuot qua 60 loi goi moi phut"
o dung cho dang ra phai thay trang thai.
"""

from __future__ import annotations

from app.main import MAX_STATUS_IDS
from test_pipeline_day4 import system, send, providers      # noqa: F401


def test_mot_loi_goi_tra_ve_trang_thai_cua_ca_lo(system, monkeypatch):
    providers(monkeypatch)
    ids = [send(system) for _ in range(3)]

    res = system.client.get("/api/scans/status", params={"ids": ",".join(ids)})

    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert [x["id"] for x in items] == ids          # dung thu tu da hoi
    assert all(x["status"] for x in items)


def test_ma_khong_ton_tai_bi_bo_qua_chu_khong_lam_hong_ca_lo(system, monkeypatch):
    providers(monkeypatch)
    that = send(system)

    res = system.client.get("/api/scans/status",
                            params={"ids": f"khong-co-that,{that}"})

    assert res.status_code == 200, res.text
    assert [x["id"] for x in res.json()["items"]] == [that]


def test_route_status_khong_bi_nuot_boi_route_ma_ban_quet(system, monkeypatch):
    """BAY THU TU ROUTE: neu `/api/scans/{scan_id}` khai bao truoc thi "status"
    bi hieu la mot ma ban quet, va endpoint nay khong bao gio chay - loi im
    lang, chi lo ra duoi dang 404 "khong tim thay ban quet"."""
    providers(monkeypatch)

    res = system.client.get("/api/scans/status", params={"ids": ""})

    assert res.status_code == 200, res.text
    assert res.json() == {"items": []}


def test_chuoi_ids_dai_bat_thuong_bi_cat_theo_chan_tren(system, monkeypatch):
    providers(monkeypatch)
    that = send(system)
    thua = ",".join(["khong-co-that"] * (MAX_STATUS_IDS + 20))

    res = system.client.get("/api/scans/status",
                            params={"ids": f"{thua},{that}"})

    assert res.status_code == 200, res.text
    # `that` nam ngoai chan tren nen bi cat - dung nhu thiet ke, va quan trong
    # hon la truy van khong quet ca bang theo mot chuoi do nguoi goi tu dat.
    assert res.json()["items"] == []
