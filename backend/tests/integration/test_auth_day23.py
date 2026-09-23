"""Ngay 23-24: dang nhap, va nguoi nay khong doc duoc du lieu cua nguoi kia.

Bo test nay tra loi MOT cau hoi ma phan con lai cua bo test khong tra loi
duoc: khi hai nguoi cung dung mot ban cai dat, du lieu cua ho co that su
tach roi khong. Moi test o day deu co dang "A tao mot thu, B di tim thu do".
"""

from __future__ import annotations

import pytest

from app.models import Contact, Scan, User
from test_draft_day5 import request_body
from test_pipeline_day4 import system, send, providers      # noqa: F401


MAT_KHAU = "matkhaudaiday12"


def tao_tai_khoan(system, email: str) -> dict:
    r = system.client.post("/api/auth/register",
                           json={"email": email, "password": MAT_KHAU})
    assert r.status_code == 201, r.text
    return r.json()


def dau(phieu: dict) -> dict:
    return {"Authorization": "Bearer " + phieu["token"]}


# --------------------------------------------------------------------------
# Tai khoan
# --------------------------------------------------------------------------

def test_nguoi_dau_tien_la_quan_tri_nguoi_sau_thi_khong(system):
    """Khong co nhanh nay thi khong ai la quan tri bao gio."""
    assert tao_tai_khoan(system, "sep@cty.vn")["user"]["role"] == "admin"
    assert tao_tai_khoan(system, "nv@cty.vn")["user"]["role"] == "user"


def test_email_khac_hoa_thuong_van_la_mot_nguoi(system):
    tao_tai_khoan(system, "An@Cty.vn")

    trung = system.client.post("/api/auth/register",
                               json={"email": "an@cty.vn", "password": MAT_KHAU})
    assert trung.status_code == 409

    vao = system.client.post("/api/auth/login",
                             json={"email": "AN@CTY.VN", "password": MAT_KHAU})
    assert vao.status_code == 200


def test_mat_khau_khong_bao_gio_ra_khoi_backend(system):
    """Ke ca dang bam. Mot ban bam bi lo van la thu de do ngoai tuyen."""
    phieu = tao_tai_khoan(system, "an@cty.vn")
    assert "password" not in str(phieu).lower() or "password_hash" not in str(phieu)
    assert "hash" not in phieu["user"]

    me = system.client.get("/api/auth/me", headers=dau(phieu)).json()
    assert set(me["user"]) == {"id", "email", "display_name", "role", "created_at"}


def test_sai_mat_khau_va_khong_co_tai_khoan_tra_ve_giong_het_nhau(system):
    """Khac cau la bien trang dang nhap thanh cong cu do email nao co that."""
    tao_tai_khoan(system, "an@cty.vn")

    sai_mk = system.client.post("/api/auth/login",
                                json={"email": "an@cty.vn", "password": "saibetroi123"})
    khong_co = system.client.post("/api/auth/login",
                                  json={"email": "khongton@cty.vn", "password": MAT_KHAU})

    assert sai_mk.status_code == khong_co.status_code == 401
    assert sai_mk.json() == khong_co.json()


def test_phieu_bi_sua_thi_khong_dung_duoc(system):
    """Doi mot ky tu trong phan chu ky la ca phieu phai hong."""
    phieu = tao_tai_khoan(system, "an@cty.vn")
    hong = dict(phieu)
    hong["token"] = phieu["token"][:-2] + ("ab" if phieu["token"][-2:] != "ab" else "cd")

    assert system.client.get("/api/auth/me", headers=dau(hong)).status_code == 401


def test_phieu_khai_alg_none_bi_tu_choi(system):
    """`alg: none` la duong ma ke tan cong tu cap cho minh quyen quan tri.

    Phieu duoi day co dung `sub` va `role: admin`, chi thieu chu ky. Neu thu
    vien duoc goi ma khong ghi ro danh sach thuat toan, no se tin phan dau
    cua phieu va chap nhan.
    """
    import base64, json

    def b64(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    gia = f'{b64({"alg": "none", "typ": "JWT"})}.{b64({"sub": "ai-do", "role": "admin"})}.'

    r = system.client.get("/api/auth/me", headers={"Authorization": "Bearer " + gia})
    assert r.status_code == 401


# --------------------------------------------------------------------------
# Cach ly du lieu - phan quan trong nhat cua Ngay 23
# --------------------------------------------------------------------------

def test_ban_quet_cua_A_khong_hien_trong_danh_sach_cua_B(system, monkeypatch):
    providers(monkeypatch)
    a, b = tao_tai_khoan(system, "a@cty.vn"), tao_tai_khoan(system, "b@cty.vn")

    r = system.client.post("/api/scans", headers=dau(a),
                           files={"file": ("card.png", system.image, "image/png")})
    cua_a = r.json()["id"]

    thay = system.client.get("/api/scans", headers=dau(b)).json()["items"]
    assert cua_a not in {x["id"] for x in thay}


@pytest.mark.parametrize("duong", [
    "/api/scans/{id}",
    "/api/scans/{id}/image",
])
def test_B_mo_thang_ban_quet_cua_A_thi_nhan_404(system, monkeypatch, duong):
    """404 chu khong phai 403: 403 xac nhan ban quet do CO THAT."""
    providers(monkeypatch)
    a, b = tao_tai_khoan(system, "a@cty.vn"), tao_tai_khoan(system, "b@cty.vn")
    cua_a = system.client.post("/api/scans", headers=dau(a),
                               files={"file": ("card.png", system.image, "image/png")}).json()["id"]

    # A doc duoc chinh ban quet cua minh - de 404 duoi day khong phai vi
    # ban quet khong ton tai.
    assert system.client.get(duong.format(id=cua_a), headers=dau(a)).status_code == 200

    assert system.client.get(duong.format(id=cua_a), headers=dau(b)).status_code == 404


def test_B_khong_xoa_duoc_ban_quet_cua_A(system, monkeypatch):
    providers(monkeypatch)
    a, b = tao_tai_khoan(system, "a@cty.vn"), tao_tai_khoan(system, "b@cty.vn")
    cua_a = system.client.post("/api/scans", headers=dau(a),
                               files={"file": ("card.png", system.image, "image/png")}).json()["id"]

    assert system.client.delete(f"/api/scans/{cua_a}", headers=dau(b)).status_code == 404

    with system.factory() as db:
        assert db.get(Scan, cua_a) is not None      # van con nguyen


def test_trang_thai_ca_lo_khong_ro_ri_ban_quet_cua_nguoi_khac(system, monkeypatch):
    """`/api/scans/status` nhan mot danh sach ma - de nhat de quen loc."""
    providers(monkeypatch)
    a, b = tao_tai_khoan(system, "a@cty.vn"), tao_tai_khoan(system, "b@cty.vn")
    cua_a = system.client.post("/api/scans", headers=dau(a),
                               files={"file": ("card.png", system.image, "image/png")}).json()["id"]

    items = system.client.get("/api/scans/status", params={"ids": cua_a},
                              headers=dau(b)).json()["items"]
    assert items == []


def test_quan_tri_thay_ban_quet_cua_moi_nguoi(system, monkeypatch):
    providers(monkeypatch)
    sep = tao_tai_khoan(system, "sep@cty.vn")          # nguoi dau tien = admin
    nv = tao_tai_khoan(system, "nv@cty.vn")
    cua_nv = system.client.post("/api/scans", headers=dau(nv),
                                files={"file": ("card.png", system.image, "image/png")}).json()["id"]

    assert system.client.get(f"/api/scans/{cua_nv}", headers=dau(sep)).status_code == 200


def test_ban_quet_khong_co_chu_van_hien_voi_moi_nguoi(system, monkeypatch):
    """Du lieu tao truoc Ngay 23 khong duoc bien mat khi bat dang nhap len.

    Giau chung di nghia la nguoi van hanh bat xac thuc len mot buoi sang va
    ca kho cu tro nen vo hinh - khong bao loi, khong dau vet.
    """
    providers(monkeypatch)
    cu = send(system)                                   # gui khong kem phieu
    ai_do = tao_tai_khoan(system, "an@cty.vn")

    assert system.client.get(f"/api/scans/{cu}", headers=dau(ai_do)).status_code == 200
    assert cu in {x["id"] for x in
                  system.client.get("/api/scans", headers=dau(ai_do)).json()["items"]}


# --------------------------------------------------------------------------
# Ho so lien he
# --------------------------------------------------------------------------

def luu_ho_so(system, phieu, scan_id: str) -> str:
    r = system.client.post(
        "/api/contacts", headers={**dau(phieu), "Idempotency-Key": "k-" + scan_id},
        json={"scan_id": scan_id, "revision": 0, "duplicate_action": "new"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_ho_so_cua_A_khong_hien_khi_B_tim_kiem_hay_xuat_du_lieu(system, monkeypatch):
    """Xuat du lieu la duong de nhat de mang ca kho ra bang mot loi goi."""
    providers(monkeypatch)
    a, b = tao_tai_khoan(system, "a@cty.vn"), tao_tai_khoan(system, "b@cty.vn")
    scan_a = system.client.post("/api/scans", headers=dau(a),
                                files={"file": ("card.png", system.image, "image/png")}).json()["id"]
    ho_so_a = luu_ho_so(system, a, scan_a)

    tim = system.client.get("/api/contacts", headers=dau(b)).json()
    assert ho_so_a not in {x["id"] for x in tim["items"]}
    assert tim["total"] == 0

    assert system.client.get(f"/api/contacts/{ho_so_a}", headers=dau(b)).status_code == 404

    xuat = system.client.get("/api/export", params={"format": "json"}, headers=dau(b))
    assert ho_so_a not in xuat.text

    # Va A thi van thay ho so cua chinh minh - de ba phep tren khong phai
    # xanh chi vi ho so khong duoc tao ra.
    assert system.client.get(f"/api/contacts/{ho_so_a}", headers=dau(a)).status_code == 200
    assert ho_so_a in system.client.get("/api/export", params={"format": "json"},
                                        headers=dau(a)).text


def test_B_khong_sua_duoc_ho_so_cua_A(system, monkeypatch):
    providers(monkeypatch)
    a, b = tao_tai_khoan(system, "a@cty.vn"), tao_tai_khoan(system, "b@cty.vn")
    scan_a = system.client.post("/api/scans", headers=dau(a),
                                files={"file": ("card.png", system.image, "image/png")}).json()["id"]
    ho_so_a = luu_ho_so(system, a, scan_a)

    # Dung mot than request HOP LE HOAN TOAN: A doc ho so cua chinh minh va
    # dung nen than request tu do. Neu gui mot than request hong thi 404 co
    # the chi la loi dinh dang, va phep kiem nay se xanh ma khong chung minh
    # duoc gi ve quyen.
    cua_a = system.client.get(f"/api/contacts/{ho_so_a}", headers=dau(a)).json()
    than = {
        "version": cua_a["version"],
        "fields": request_body({"draft_revision": 0, "draft": cua_a["draft"]})["fields"],
        "note": cua_a["note"] or "",
        "organization": {"mode": "link", "id": cua_a["organization"]["id"]},
    }
    than["fields"]["full_names"] = [{"value": "Ke La"}]

    # A gui chinh than request nay thi duoc - chung to no hop le.
    assert system.client.patch(f"/api/contacts/{ho_so_a}", headers=dau(a),
                               json=than).status_code == 200

    than["version"] = cua_a["version"] + 1               # theo kip ban moi
    sua = system.client.patch(f"/api/contacts/{ho_so_a}", headers=dau(b), json=than)
    assert sua.status_code == 404

    with system.factory() as db:
        # A da doi thanh "Ke La" o tren, nen phep kiem phai la B KHONG doi
        # duoc lan thu hai - kiem tra so phien ban dung lai.
        assert db.get(Contact, ho_so_a).full_name_original == "Ke La"
    assert system.client.get(f"/api/contacts/{ho_so_a}",
                             headers=dau(a)).json()["version"] == cua_a["version"] + 1


def test_ho_so_duoc_ghi_dung_chu(system, monkeypatch):
    providers(monkeypatch)
    a = tao_tai_khoan(system, "a@cty.vn")
    scan_a = system.client.post("/api/scans", headers=dau(a),
                                files={"file": ("card.png", system.image, "image/png")}).json()["id"]
    ho_so_a = luu_ho_so(system, a, scan_a)

    with system.factory() as db:
        nguoi = db.scalar(__import__("sqlalchemy").select(User)
                          .where(User.email_norm == "a@cty.vn"))
        assert db.get(Scan, scan_a).owner_id == nguoi.id
        assert db.get(Contact, ho_so_a).owner_id == nguoi.id
