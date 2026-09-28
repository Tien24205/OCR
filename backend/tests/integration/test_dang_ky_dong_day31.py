"""Dong cua dang ky (Ngay 31).

VI SAO CO BO TEST NAY: truoc khi co `REGISTRATION_OPEN`, mot nguoi la vua
dang ky tren trang cong khai lay duoc TOAN BO du lieu - danh sach ban quet,
noi dung, ANH da chup, danh sach ho so, va ca mot ban xuat day du. Khong
phai vi phan quyen sai, ma vi hai quy tac dung rieng le ghep lai thanh mot
cua mo:

    dang ky mo  +  ban ghi `owner_id IS NULL` hien voi moi nguoi dang nhap

Test cuoi tep dung lai DUNG kich ban khai thac do, va no phai that bai.
"""

from __future__ import annotations

from test_pipeline_day4 import system, send, providers      # noqa: F401


MK = "matkhaudaiday12"


def dang_ky(system, email, dau=None):
    return system.client.post("/api/auth/register",
                              headers=dau or {},
                              json={"email": email, "password": MK})


def phieu(r):
    return {"Authorization": "Bearer " + r.json()["token"]}


# --------------------------------------------------------------------------
# Cua mo - hanh vi cu khong doi
# --------------------------------------------------------------------------

def test_cua_mo_thi_ai_cung_dang_ky_duoc(system):
    assert system.config.registration_open is True
    dang_ky(system, "chu@cty.vn")

    assert dang_ky(system, "nguoila@ngoaikia.com").status_code == 201


# --------------------------------------------------------------------------
# Cua dong
# --------------------------------------------------------------------------

def test_cua_dong_nhung_chua_co_ai_thi_van_nhan(system):
    """Khong co ngoai le nay thi he thong tu khoa chet minh: khong ai dang ky
    duoc -> khong bao gio co quan tri -> khong bao gio mo lai duoc cua."""
    system.config.registration_open = False

    r = dang_ky(system, "chu@cty.vn")

    assert r.status_code == 201
    assert r.json()["user"]["role"] == "admin"


def test_cua_dong_thi_nguoi_la_bi_tu_choi(system):
    dang_ky(system, "chu@cty.vn")
    system.config.registration_open = False

    r = dang_ky(system, "nguoila@ngoaikia.com")

    assert r.status_code == 403
    assert r.json()["error"]["code"] == "REGISTRATION_CLOSED"


def test_quan_tri_van_tao_duoc_tai_khoan_cho_nguoi_khac(system):
    quan_tri = phieu(dang_ky(system, "chu@cty.vn"))
    system.config.registration_open = False

    r = dang_ky(system, "nhanvien@cty.vn", dau=quan_tri)

    assert r.status_code == 201
    assert r.json()["user"]["role"] == "user"


def test_nguoi_dung_thuong_KHONG_tao_duoc_tai_khoan(system):
    """Neu khong thi dong cua vo nghia: mot tai khoan lot vao la mo lai duoc
    cua cho ca the gioi."""
    dang_ky(system, "chu@cty.vn")
    thuong = phieu(dang_ky(system, "nv@cty.vn"))
    system.config.registration_open = False

    r = dang_ky(system, "bancuatoi@ngoaikia.com", dau=thuong)

    assert r.status_code == 403


def test_phieu_bia_khong_qua_duoc(system):
    dang_ky(system, "chu@cty.vn")
    system.config.registration_open = False

    r = dang_ky(system, "ke@gian.com",
                dau={"Authorization": "Bearer khong-phai-phieu-that"})

    assert r.status_code == 403


# --------------------------------------------------------------------------
# Chinh kich ban khai thac, dung lai
# --------------------------------------------------------------------------

def test_NGUOI_LA_KHONG_CON_LAY_DUOC_DU_LIEU(system, monkeypatch):
    """Truoc khi sua, nguoi la lay duoc: danh sach ban quet, noi dung, anh
    da chup, danh sach ho so, va mot ban xuat 3112 byte."""
    providers(monkeypatch)
    r = system.client.post("/api/scans",
                           files={"file": ("card.png", system.image, "image/png")})
    ma = r.json()["id"]
    system.client.post("/api/contacts", headers={"Idempotency-Key": "k1"},
                       json={"scan_id": ma, "revision": 0,
                             "duplicate_action": "new"})

    dang_ky(system, "chu@cty.vn")
    system.config.registration_open = False

    assert dang_ky(system, "nguoila@ngoaikia.com").status_code == 403


# --------------------------------------------------------------------------
# Endpoint giao dien hoi truoc khi ve trang dang nhap
# --------------------------------------------------------------------------

def test_bao_mo_khi_cua_mo(system):
    assert system.client.get("/api/auth/registration").json()["open"] is True


def test_bao_DONG_khi_da_co_tai_khoan(system):
    dang_ky(system, "chu@cty.vn")
    system.config.registration_open = False

    assert system.client.get("/api/auth/registration").json()["open"] is False


def test_van_bao_MO_khi_cua_dong_ma_chua_co_ai(system):
    """Tra ve ket qua DA TINH chu khong phai co cau hinh tho: neu tra co tho
    thi giao dien phai tu suy lai luat "chua co ai thi van cho vao", va hai
    ban sao cua mot luat som muon lech nhau."""
    system.config.registration_open = False

    assert system.client.get("/api/auth/registration").json()["open"] is True


def test_goi_duoc_khi_chua_dang_nhap(system):
    """Trang dang nhap goi no TRUOC khi co phieu. Khong nam trong
    PUBLIC_PATHS thi no tra 401 va giao dien se luon tuong cua da dong."""
    from app.auth import PUBLIC_PATHS

    assert "/api/auth/registration" in PUBLIC_PATHS
