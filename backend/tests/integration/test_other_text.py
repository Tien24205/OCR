"""Phan con lai cua the phai den duoc giao dien qua API that.

Phep tru duoc kiem ky o test_unclaimed.py; test nay chi khoa mot thu: no co
duoc NOI vao `GET /api/scans/{id}` khong. Mot phep tru dung ma khong ai goi
thi nguoi dung van khong thay gi.
"""

from __future__ import annotations

from test_pipeline_day4 import system, send, providers      # noqa: F401


def test_api_tra_ve_phan_quet_duoc_ngoai_cac_truong(system, monkeypatch):
    providers(monkeypatch)
    scan_id = send(system)
    scan = system.client.get(f"/api/scans/{scan_id}").json()

    assert "other_text" in scan, "giao dien khong co duong nao lay phan con lai"
    for dong in scan["other_text"]:
        assert set(dong) == {"line", "text"}
        assert dong["text"] in (scan["raw_text"] or "")   # nguyen van, khong bia
        assert dong["text"].strip()


def test_phan_con_lai_khong_lap_lai_gia_tri_da_co_trong_ban_nhap(system, monkeypatch):
    providers(monkeypatch)
    scan_id = send(system)
    scan = system.client.get(f"/api/scans/{scan_id}").json()

    da_co = {item["value"]
             for muc in (scan["draft"] or {}).get("fields", {}).values()
             for item in muc}
    con_lai = {d["text"] for d in scan["other_text"]}
    assert not (da_co & con_lai)
