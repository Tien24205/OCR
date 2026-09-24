"""Nhat ky xuat du lieu.

Phan quyen chan duoc nguoi nay doc du lieu nguoi kia, nhung no KHONG chan
duoc chinh chu tai ca kho xuong roi mang di dau khong ai biet. Khong the
ngan viec do ma van giu ung dung dung duoc - nhung co the lam cho no de lai
dau vet.

Bo test nay canh dung mot dieu: sau moi lan du lieu roi khoi he thong, co
dung mot dong duoc ghi, va dong do khong ai xoa duoc tu ben ngoai.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import ExportLog
from test_pipeline_day4 import system, send, providers      # noqa: F401


MAT_KHAU = "matkhaudaiday12"


def tai_khoan(system, email: str) -> dict:
    r = system.client.post("/api/auth/register",
                           json={"email": email, "password": MAT_KHAU})
    assert r.status_code == 201, r.text
    return r.json()


def dau(p: dict) -> dict:
    return {"Authorization": "Bearer " + p["token"]}


def luu_mot_ho_so(system, p: dict) -> str:
    r = system.client.post("/api/scans", headers=dau(p),
                           files={"file": ("card.png", system.image, "image/png")})
    scan_id = r.json()["id"]
    r2 = system.client.post(
        "/api/contacts",
        headers={**dau(p), "Idempotency-Key": f"k-{scan_id}"},
        json={"scan_id": scan_id, "revision": 0, "duplicate_action": "new"})
    assert r2.status_code == 201, r2.text
    return r2.json()["id"]


# --------------------------------------------------------------------------
# Ghi nhat ky
# --------------------------------------------------------------------------

@pytest.mark.parametrize("dinh_dang", ["json", "csv", "vcf"])
def test_moi_lan_xuat_deu_de_lai_mot_dong(system, monkeypatch, dinh_dang):
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")
    luu_mot_ho_so(system, an)

    system.client.get("/api/export", params={"format": dinh_dang},
                      headers=dau(an))

    with system.factory() as db:
        dong = db.scalars(select(ExportLog)).all()
    assert len(dong) == 1
    assert dong[0].format == dinh_dang
    assert dong[0].contact_count == 1
    assert dong[0].byte_count > 0


def test_ghi_email_nguoi_xuat_chu_khong_chi_ghi_ma(system, monkeypatch):
    """Ma tai khoan khong tra loi duoc "ai" khi doc nhat ky sau mot nam."""
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")
    luu_mot_ho_so(system, an)

    system.client.get("/api/export", params={"format": "json"}, headers=dau(an))

    with system.factory() as db:
        assert db.scalars(select(ExportLog)).first().actor == "an@cty.vn"


def test_xuat_bang_khoa_api_cung_duoc_ghi(system, monkeypatch):
    """He thong tich hop mang du lieu ra ngoai cung nhieu nhu mot nguoi."""
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")
    luu_mot_ho_so(system, an)

    # Che do mo cua bo test: khong phieu, khong khoa.
    system.client.get("/api/export", params={"format": "json"})

    with system.factory() as db:
        dong = db.scalars(select(ExportLog)).all()
    assert len(dong) == 1


def test_khong_ghi_noi_dung_du_lieu(system, monkeypatch):
    """Mot ban sao thu hai cua du lieu ca nhan trong bang nhat ky lam van de
    te hon chu khong tot hon."""
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")
    luu_mot_ho_so(system, an)
    system.client.get("/api/export", params={"format": "json"}, headers=dau(an))

    cot = {c.name for c in ExportLog.__table__.columns}

    assert cot == {"id", "user_id", "actor", "format", "contact_count",
                   "byte_count", "created_at"}


# --------------------------------------------------------------------------
# Doc nhat ky
# --------------------------------------------------------------------------

def test_nguoi_dung_chi_thay_nhat_ky_cua_minh(system, monkeypatch):
    """Nhat ky xuat cua nguoi khac cho biet ho lam viec luc nao, nhieu bao
    nhieu - do cung la thong tin."""
    providers(monkeypatch)
    tai_khoan(system, "quantri@cty.vn")
    an, binh = tai_khoan(system, "an@cty.vn"), tai_khoan(system, "binh@cty.vn")
    luu_mot_ho_so(system, an)
    system.client.get("/api/export", params={"format": "json"}, headers=dau(an))

    cua_binh = system.client.get("/api/export/log", headers=dau(binh)).json()
    cua_an = system.client.get("/api/export/log", headers=dau(an)).json()

    assert cua_binh["items"] == []
    assert len(cua_an["items"]) == 1
    assert cua_an["items"][0]["ai"] == "an@cty.vn"


def test_quan_tri_thay_nhat_ky_cua_moi_nguoi(system, monkeypatch):
    providers(monkeypatch)
    sep = tai_khoan(system, "sep@cty.vn")
    nv = tai_khoan(system, "nv@cty.vn")
    luu_mot_ho_so(system, nv)
    system.client.get("/api/export", params={"format": "csv"}, headers=dau(nv))

    d = system.client.get("/api/export/log", headers=dau(sep)).json()

    assert len(d["items"]) == 1
    assert d["items"][0]["ai"] == "nv@cty.vn"


def test_moi_nhat_len_dau(system, monkeypatch):
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")
    luu_mot_ho_so(system, an)
    for dinh_dang in ("json", "csv", "vcf"):
        system.client.get("/api/export", params={"format": dinh_dang},
                          headers=dau(an))

    d = system.client.get("/api/export/log", headers=dau(an)).json()

    assert len(d["items"]) == 3
    assert [x["luc"] for x in d["items"]] == sorted(
        [x["luc"] for x in d["items"]], reverse=True)


def test_khong_co_duong_nao_xoa_mot_dong_nhat_ky():
    """Mot nhat ky ma nguoi bi ghi tu xoa duoc thi khong phai nhat ky.

    Soi THANG router chu khong soi `app.routes`: FastAPI ban nay giu cac
    router da include trong mot doi tuong `_IncludedRouter` long ben trong,
    nen `app.routes` khong he chua duong dan nao cua chung - va mot phep
    kiem duyet `app.routes` se xanh vi khong tim thay gi, khong phai vi
    khong co gi.
    """
    from app.contact_routes import router

    duong_export = [r for r in router.routes if "export" in r.path]

    assert duong_export, "khong thay endpoint export nao - phep kiem vo nghia"
    for r in duong_export:
        assert r.methods <= {"GET", "HEAD"}, f"{r.path} nhan {r.methods}"
