"""Ngay 25: duong tai anh khi kho co duong ky tam thoi.

Nhanh nay chi chay khi dung GCS, nen no la nhanh de khong ai thu bao gio -
va cung la nhanh ma neu sai thi anh khong hien duoc tren toan bo giao dien.
"""

from __future__ import annotations

from app.services import storage
from test_pipeline_day4 import system, send, providers      # noqa: F401


def test_khong_co_duong_ky_thi_backend_tu_tra_bytes(system, monkeypatch):
    """Mac dinh (dia cuc bo): giu dung hanh vi cu."""
    providers(monkeypatch)
    scan_id = send(system)

    r = system.client.get(f"/api/scans/{scan_id}/image")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")
    # Anh danh thiep khong duoc nam lai trong bo nho dem cua trinh duyet
    # hay cua may chu trung gian nao.
    assert r.headers["cache-control"] == "private, no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.content


def test_co_duong_ky_thi_chuyen_huong_thay_vi_bom_bytes(system, monkeypatch):
    """Trinh duyet tai thang tu nha cung cap; backend khong lam duong ong."""
    providers(monkeypatch)
    scan_id = send(system)
    duong = "https://storage.example.com/anh?chu-ky=abc&het-han=123"
    monkeypatch.setattr(storage.KhoTepLocal, "duong_ky",
                        lambda self, ref, mime: duong)

    r = system.client.get(f"/api/scans/{scan_id}/image", follow_redirects=False)

    assert r.status_code == 307
    assert r.headers["location"] == duong


def test_ban_quet_cua_nguoi_khac_khong_duoc_cap_duong_ky(system, monkeypatch):
    """Duong da cap thi KHONG con qua phep kiem quyen nao nua - nen phep
    kiem phai chay TRUOC khi ky, khong phai sau."""
    providers(monkeypatch)
    da_ky = []
    monkeypatch.setattr(storage.KhoTepLocal, "duong_ky",
                        lambda self, ref, mime: da_ky.append(ref))
    scan_id = send(system)

    a = system.client.post("/api/auth/register",
                           json={"email": "a@cty.vn", "password": "matkhaudai12"}).json()
    b = system.client.post("/api/auth/register",
                           json={"email": "b@cty.vn", "password": "matkhaudai12"}).json()
    cua_a = system.client.post(
        "/api/scans", headers={"Authorization": "Bearer " + a["token"]},
        files={"file": ("card.png", system.image, "image/png")}).json()["id"]
    da_ky.clear()

    r = system.client.get(f"/api/scans/{cua_a}/image",
                          headers={"Authorization": "Bearer " + b["token"]},
                          follow_redirects=False)

    assert r.status_code == 404
    assert da_ky == [], "da ky duong cho ban quet cua nguoi khac"
    assert scan_id                      # ban quet khong chu van ton tai
