"""Nhat ky kiem toan: moi thao tac quan trong de lai mot dong, dung nguoi
thay dung phan cua minh, va khong co duong nao sua hay xoa nhat ky."""

from __future__ import annotations

from sqlalchemy import select

from app.models import AuditLog
from test_export_log_day30 import MAT_KHAU, dau, luu_mot_ho_so, tai_khoan
from test_pipeline_day4 import system, send, providers      # noqa: F401


def hanh_dong(system) -> list[str]:
    with system.factory() as db:
        return [x.action for x in db.scalars(
            select(AuditLog).order_by(AuditLog.created_at, AuditLog.id))]


def test_ca_vong_doi_ho_so_deu_duoc_ghi(system, monkeypatch):
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")
    ma = luu_mot_ho_so(system, an)
    system.client.get("/api/export", params={"format": "csv"}, headers=dau(an))
    r = system.client.delete(f"/api/contacts/{ma}", headers=dau(an))
    assert r.status_code == 200, r.text

    ghi = hanh_dong(system)
    for can in ("tao_tai_khoan", "quet_the", "luu_ho_so", "xuat_du_lieu", "xoa_ho_so"):
        assert can in ghi, (can, ghi)


def test_dang_nhap_sai_cung_duoc_ghi_vao_tai_khoan_bi_nham(system):
    tai_khoan(system, "an@cty.vn")
    system.client.post("/api/auth/login", json={"email": "an@cty.vn", "password": "sai-mat-khau-roi"})
    ok = system.client.post("/api/auth/login", json={"email": "an@cty.vn", "password": MAT_KHAU})
    assert ok.status_code == 200

    d = system.client.get("/api/audit", headers=dau(ok.json())).json()
    ghi = [x["hanh_dong"] for x in d["items"]]
    assert "dang_nhap_that_bai" in ghi and "dang_nhap" in ghi


def test_nhat_ky_khong_giu_du_lieu_ca_nhan_cua_doi_tac(system, monkeypatch):
    """Xoa ho so thi nhat ky con lai khong duoc la ban sao cua ho so do."""
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")
    ma = luu_mot_ho_so(system, an)
    ten = system.client.get("/api/contacts", headers=dau(an)).json()["items"][0]["name"]
    system.client.delete(f"/api/contacts/{ma}", headers=dau(an))

    with system.factory() as db:
        tat_ca = " ".join(str(x.detail) for x in db.scalars(select(AuditLog)))
    assert ten and ten not in tat_ca


def test_nguoi_dung_chi_thay_phan_cua_minh_quan_tri_thay_het(system, monkeypatch):
    providers(monkeypatch)
    sep = tai_khoan(system, "sep@cty.vn")
    an, binh = tai_khoan(system, "an@cty.vn"), tai_khoan(system, "binh@cty.vn")
    luu_mot_ho_so(system, an)

    cua_binh = system.client.get("/api/audit", headers=dau(binh)).json()["items"]
    cua_sep = system.client.get("/api/audit", headers=dau(sep)).json()["items"]

    assert {x["ai"] for x in cua_binh} == {"binh@cty.vn"}
    assert {"an@cty.vn", "binh@cty.vn", "sep@cty.vn"} <= {x["ai"] for x in cua_sep}


def test_loc_theo_hanh_dong(system, monkeypatch):
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")
    luu_mot_ho_so(system, an)

    d = system.client.get("/api/audit", params={"action": "luu_ho_so"}, headers=dau(an)).json()

    assert [x["hanh_dong"] for x in d["items"]] == ["luu_ho_so"]


def test_loc_theo_moc_thoi_gian(system, monkeypatch):
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")
    luu_mot_ho_so(system, an)

    tuong_lai = system.client.get("/api/audit", params={"since": "2999-01-01"},
                                  headers=dau(an)).json()
    qua_khu = system.client.get("/api/audit", params={"since": "2000-01-01"},
                                headers=dau(an)).json()

    assert tuong_lai["items"] == []
    assert qua_khu["items"]


def test_dang_nhap_sai_vao_email_khong_ton_tai_chi_quan_tri_thay(system):
    """Khong gan duoc vao tai khoan nao thi khong nguoi dung thuong nao duoc
    thay - nhung quan tri van phai thay de phat hien do tai khoan hang loat."""
    sep = tai_khoan(system, "sep@cty.vn")
    an = tai_khoan(system, "an@cty.vn")
    system.client.post("/api/auth/login", json={"email": "ma@cty.vn", "password": "doan-bua-thoi"})

    cua_an = system.client.get("/api/audit", headers=dau(an)).json()["items"]
    cua_sep = system.client.get("/api/audit", headers=dau(sep)).json()["items"]

    assert "ma@cty.vn" not in {x["ai"] for x in cua_an}
    assert any(x["ai"] == "ma@cty.vn" and x["hanh_dong"] == "dang_nhap_that_bai"
               for x in cua_sep)


def test_khong_co_duong_nao_sua_hay_xoa_nhat_ky():
    from app.audit import router

    assert router.routes
    for r in router.routes:
        assert r.methods <= {"GET", "HEAD"}, f"{r.path} nhan {r.methods}"


# --- Chi tiet: nguon, truong da sua, ten doi tuong luc doc --------------------

def test_ghi_ip_va_trinh_duyet_nguoi_dung_ma_giao_dien_chuyen_tiep(system):
    tai_khoan(system, "an@cty.vn")
    system.client.post("/api/auth/login", json={"email": "an@cty.vn", "password": MAT_KHAU},
                       headers={"X-Client-IP": "203.0.113.7",
                                "X-Client-UA": "Mozilla/5.0 (Windows NT 10.0) Chrome/130"})
    with system.factory() as db:
        dong = db.scalars(select(AuditLog).where(AuditLog.action == "dang_nhap")).one()
    assert dong.ip == "203.0.113.7" and "Chrome/130" in dong.thiet_bi


def test_ly_do_dang_nhap_that_bai(system):
    tai_khoan(system, "an@cty.vn")
    system.client.post("/api/auth/login", json={"email": "an@cty.vn", "password": "sai-roi-sai-roi"})
    system.client.post("/api/auth/login", json={"email": "ma@cty.vn", "password": "sai-roi-sai-roi"})
    with system.factory() as db:
        ly_do = {x.actor: x.detail["ly_do"] for x in db.scalars(
            select(AuditLog).where(AuditLog.action == "dang_nhap_that_bai"))}
    assert ly_do == {"an@cty.vn": "sai_mat_khau", "ma@cty.vn": "khong_co_tai_khoan"}


def test_sua_ho_so_ghi_ten_truong_khong_ghi_gia_tri(system, monkeypatch):
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")
    ma = luu_mot_ho_so(system, an)
    hs = system.client.get(f"/api/contacts/{ma}", headers=dau(an)).json()
    from test_contacts_day7 import edit_body
    than = edit_body(hs)
    than["fields"]["emails"] = [{"value": "bi-mat@doi-tac.vn"}]
    r = system.client.patch(f"/api/contacts/{ma}", json=than, headers=dau(an))
    assert r.status_code == 200, r.text

    with system.factory() as db:
        dong = db.scalars(select(AuditLog).where(AuditLog.action == "sua_ho_so")).one()
    assert dong.detail["truong_sua"] == ["emails"]
    assert "bi-mat@doi-tac.vn" not in str(dong.detail)


def test_luc_doc_hien_ten_doi_tuong_va_bao_da_xoa(system, monkeypatch):
    providers(monkeypatch)
    an = tai_khoan(system, "an@cty.vn")
    ma = luu_mot_ho_so(system, an)

    truoc = system.client.get("/api/audit", params={"action": "luu_ho_so"}, headers=dau(an)).json()["items"][0]
    assert truoc["doi_tuong"]["con"] is True and truoc["doi_tuong"]["ten"]

    system.client.delete(f"/api/contacts/{ma}", headers=dau(an))
    sau = system.client.get("/api/audit", params={"action": "luu_ho_so"}, headers=dau(an)).json()["items"][0]
    xoa = system.client.get("/api/audit", params={"action": "xoa_ho_so"}, headers=dau(an)).json()["items"][0]

    assert sau["doi_tuong"] == {"ten": "(đã xoá)", "con": False}
    assert xoa["chi_tiet"]["so_ban_quet_xoa_theo"] == 1
