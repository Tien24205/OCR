"""Ngay 29: hoi quy tron hanh trinh sau khi them dang nhap (Ngay 23-28).

KHAC GI SO VOI `test_integration_e2e.py`: bo do kiem luong anh -> OCR ->
trich xuat -> ho so tren bon ngon ngu, va no co TU TRUOC khi co nguoi dung.
Bo nay kiem cung hanh trinh do nhung DI BANG MOT TAI KHOAN THAT tu dau den
cuoi, va kiem rang moi buoc deu giu dung ranh gioi chu so huu.

Ly do phai co rieng: phan quyen duoc them vao SAU, nen no duoc gan vao tung
endpoint. Mot endpoint bi bo sot se khong lam test nao do - no chi lang le
cho mot nguoi doc du lieu cua nguoi khac o dung buoc do. Bo nay di het ca
hanh trinh bang hai tai khoan song song de cho do lo ra.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Contact, Scan, User
from test_draft_day5 import request_body
from test_pipeline_day4 import system, send, providers      # noqa: F401


MAT_KHAU = "matkhaudaiday12"


def tai_khoan(system, email: str) -> dict:
    r = system.client.post("/api/auth/register",
                           json={"email": email, "password": MAT_KHAU})
    assert r.status_code == 201, r.text
    return r.json()


def dau(p: dict) -> dict:
    return {"Authorization": "Bearer " + p["token"]}


def quet(system, p: dict) -> str:
    r = system.client.post("/api/scans", headers=dau(p),
                           files={"file": ("card.png", system.image, "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def luu(system, p: dict, scan_id: str) -> str:
    r = system.client.post(
        "/api/contacts",
        headers={**dau(p), "Idempotency-Key": f"k-{scan_id}"},
        json={"scan_id": scan_id, "revision": 0, "duplicate_action": "new"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_tron_hanh_trinh_cua_mot_tai_khoan(system, monkeypatch):
    """Dang ky -> quet -> doc ban nhap -> sua -> luu ho so -> tim -> xuat."""
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")

    # 1. Quet
    scan_id = quet(system, an)
    ban_quet = system.client.get(f"/api/scans/{scan_id}", headers=dau(an)).json()
    assert ban_quet["status"] == "ocr_done"
    assert ban_quet["raw_text"]

    # 2. Anh doc lai duoc, va di qua ban quet chu khong qua ma bam
    anh = system.client.get(f"/api/scans/{scan_id}/image", headers=dau(an))
    assert anh.status_code == 200 and anh.content

    # 3. Luu thanh ho so
    ho_so_id = luu(system, an, scan_id)

    # 4. Ho so hien ra khi tim kiem
    tim = system.client.get("/api/contacts", headers=dau(an)).json()
    assert ho_so_id in {x["id"] for x in tim["items"]}

    # 5. Sua duoc
    chi_tiet = system.client.get(f"/api/contacts/{ho_so_id}",
                                 headers=dau(an)).json()
    than = {
        "version": chi_tiet["version"],
        "fields": request_body({"draft_revision": 0,
                                "draft": chi_tiet["draft"]})["fields"],
        "note": "ghi chu sau khi gap",
        "organization": {"mode": "link", "id": chi_tiet["organization"]["id"]},
    }
    sua = system.client.patch(f"/api/contacts/{ho_so_id}", headers=dau(an),
                              json=than)
    assert sua.status_code == 200, sua.text
    assert sua.json()["note"] == "ghi chu sau khi gap"

    # 6. Xuat du lieu o ca ba dinh dang
    for dinh_dang in ("json", "csv", "vcf"):
        ra = system.client.get("/api/export", params={"format": dinh_dang},
                               headers=dau(an))
        assert ra.status_code == 200 and ra.content, dinh_dang

    # 7. Chu so huu duoc ghi dung o CA HAI bang
    with system.factory() as db:
        nguoi = db.scalar(select(User).where(User.email_norm == "an@cty.vn"))
        assert db.get(Scan, scan_id).owner_id == nguoi.id
        assert db.get(Contact, ho_so_id).owner_id == nguoi.id


@pytest.mark.parametrize("duong,phuong_thuc", [
    ("/api/scans/{scan}", "GET"),
    ("/api/scans/{scan}/image", "GET"),
    ("/api/scans/{scan}", "DELETE"),
    ("/api/contacts/{ho_so}", "GET"),
    ("/api/contacts/{ho_so}", "DELETE"),
    ("/api/contacts/{ho_so}/duplicates", "GET"),
])
def test_khong_endpoint_nao_bi_bo_sot_phep_kiem_quyen(system, monkeypatch,
                                                      duong, phuong_thuc):
    """Di qua TUNG endpoint nhan mot ma ban ghi, bang tai khoan khong so huu.

    Danh sach nay la thu de lo nhat khi them endpoint moi: viet xong, chay
    thu bang tai khoan cua chinh minh, thay dung, va phep kiem quyen thi
    khong bao gio duoc goi toi.
    """
    providers(monkeypatch)
    an, binh = tai_khoan(system, "an@cty.vn"), tai_khoan(system, "binh@cty.vn")
    scan_id = quet(system, an)
    ho_so_id = luu(system, an, scan_id)

    dia_chi = duong.format(scan=scan_id, ho_so=ho_so_id)
    r = system.client.request(phuong_thuc, dia_chi, headers=dau(binh))

    assert r.status_code == 404, f"{phuong_thuc} {duong} -> {r.status_code}"


def test_hai_tai_khoan_lam_viec_song_song_khong_lan_sang_nhau(system, monkeypatch):
    """Ca hai cung quet, cung luu, va khong ai thay gi cua ai."""
    providers(monkeypatch)
    # Dang ky mot tai khoan BO DI truoc: nguoi dau tien tren he thong la
    # quan tri, va quan tri thi thay tat ca - neu An la nguoi dau tien thi
    # phep kiem duoi day do vi mot ly do dung dan, khong phai vi lo ri.
    tai_khoan(system, "quantri@cty.vn")
    an, binh = tai_khoan(system, "an@cty.vn"), tai_khoan(system, "binh@cty.vn")

    cua_an = luu(system, an, quet(system, an))
    cua_binh = luu(system, binh, quet(system, binh))

    thay_an = {x["id"] for x in
               system.client.get("/api/contacts", headers=dau(an)).json()["items"]}
    thay_binh = {x["id"] for x in
                 system.client.get("/api/contacts", headers=dau(binh)).json()["items"]}

    assert thay_an == {cua_an}
    assert thay_binh == {cua_binh}

    # Va so lieu tren trang Tong quan cung khong duoc gop chung.
    so_an = system.client.get("/api/stats", headers=dau(an)).json()
    so_binh = system.client.get("/api/stats", headers=dau(binh)).json()

    assert so_an["total_contacts"] == so_binh["total_contacts"] == 1
    assert so_an["total_scans"] == so_binh["total_scans"] == 1


def test_quan_tri_van_thay_toan_bo(system, monkeypatch):
    """Nguoi dau tien dang ky la quan tri - do la duong duy nhat co quan tri."""
    providers(monkeypatch)
    sep = tai_khoan(system, "sep@cty.vn")
    nv = tai_khoan(system, "nv@cty.vn")
    cua_nv = luu(system, nv, quet(system, nv))

    thay = {x["id"] for x in
            system.client.get("/api/contacts", headers=dau(sep)).json()["items"]}

    assert cua_nv in thay


def test_khoa_api_van_dung_duoc_sau_khi_them_dang_nhap(system, monkeypatch):
    """He thong tich hop CRM khong co tai khoan nguoi dung, va khong duoc
    hong chi vi nguoi dung gio co tai khoan."""
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")
    cua_an = luu(system, an, quet(system, an))

    # Khong mang phieu: che do mo cua bo test (khong khoa, khong bat buoc).
    thay = {x["id"] for x in
            system.client.get("/api/contacts").json()["items"]}

    assert cua_an in thay


def test_du_lieu_cu_khong_co_chu_van_dung_duoc_sau_khi_bat_dang_nhap(
        system, monkeypatch):
    """Ban quet tao truoc Ngay 23 phai van mo duoc, luu duoc thanh ho so.

    Giau chung di nghia la bat dang nhap len mot buoi sang va ca kho cu bien
    mat - khong bao loi, khong dau vet.
    """
    providers(monkeypatch)
    cu = send(system)                                   # gui khong kem phieu
    an = tai_khoan(system, "an@cty.vn")

    assert system.client.get(f"/api/scans/{cu}", headers=dau(an)).status_code == 200
    ho_so_id = luu(system, an, cu)

    # Va ho so tao ra tu no thi thuoc ve nguoi da luu.
    with system.factory() as db:
        nguoi = db.scalar(select(User).where(User.email_norm == "an@cty.vn"))
        assert db.get(Contact, ho_so_id).owner_id == nguoi.id


def test_bang_dieu_khien_khong_ro_ri_ten_cong_ty_cua_nguoi_khac(system, monkeypatch):
    """`/api/stats` khong nhan ma ban ghi nao, nen no la duong de quen nhat
    khi them phan quyen - va cai quen o do khong lo ra nhu mot loi, no lo ra
    duoi dang nhung con so va nhung cai ten.

    Ten cong ty la quan he lam an. Bang "doanh nghiep nhieu dau moi nhat"
    cua nguoi nay khong duoc chua doi tac cua nguoi kia.
    """
    # `raw` phai CHUA ten cong ty: buoc doi chieu loai bo gia tri khong tim
    # thay trong van ban OCR, va khi cong ty bi loai thi ho so khong duoc gan
    # doanh nghiep nao - luc do phep kiem duoi se xanh vi mot ly do sai.
    cong_ty = "Cong ty Rieng Cua An"
    providers(monkeypatch,
              raw="\n".join(["Jane Doe", cong_ty, "jane@example.com",
                             "Tel: 03-1234-5678"]),
              name="Jane Doe", company=cong_ty)
    tai_khoan(system, "quantri@cty.vn")          # nguoi dau tien = quan tri
    an = tai_khoan(system, "an@cty.vn")
    binh = tai_khoan(system, "binh@cty.vn")
    luu(system, an, quet(system, an))

    so_binh = system.client.get("/api/stats", headers=dau(binh)).json()

    assert so_binh["total_contacts"] == 0
    assert so_binh["total_organizations"] == 0
    ten = {x["organization"] for x in so_binh["top_organizations"]}
    assert cong_ty not in ten

    # Va An thi van thay cua chinh minh - de phep kiem tren khong xanh chi
    # vi khong co du lieu nao duoc tao ra.
    so_an = system.client.get("/api/stats", headers=dau(an)).json()
    assert so_an["total_contacts"] == 1
    assert cong_ty in {x["organization"] for x in so_an["top_organizations"]}
