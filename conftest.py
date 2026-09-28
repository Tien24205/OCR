"""Cau hinh chung cho ca bo test - chay TRUOC moi tep test.

VI SAO TEP NAY TON TAI

Bo test doc `backend/.env` cua may dang chay. Truoc ngay 15/09 dieu do khong
gay chuyen gi, vi `.env` cua moi nguoi deu gan giong gia tri mac dinh - nen
khong ai phat hien ra su phu thuoc nay.

Hom bat xac thuc API len, `API_KEYS` co gia tri that va **140 test do ngay**,
tat ca deu vi 401. Ban than ma nguon khong hong; chi la ket qua bo test phu
thuoc vao cau hinh ca nhan cua tung may.

Do la mot su phu thuoc an: cung mot ma nguon co the xanh o may nay va do o
may khac, ma khong ai doan duoc vi sao. Mot bo test nhu vay khong con tra loi
duoc cau hoi "ma nguon co dung khong".

CACH XU LY

Ep tat xac thuc cho toan bo bo test. Bien moi truong duoc uu tien hon tep
`.env` trong pydantic-settings, nen dat o day la du.

Nhung test CAN xac thuc thi tu dung app rieng cua chung va tu goi
`gan_xac_thuc(...)` - xem `backend/tests/unit/test_auth.py`. Cach do tot hon
la bat xac thuc toan cuc roi bat 140 test phai mang khoa: kien thuc ve xac
thuc nam gon mot cho, thay vi rai khap noi.

CHI EP NHUNG GI THAT SU CAN. Ep het moi bien se che mat nhung loi cau hinh
that ma bo test dang ra phai bat duoc.
"""

from __future__ import annotations

import os

# Phai dat TRUOC khi bat ky tep test nao import `app.main`, vi `main.py` goi
# `get_settings()` ngay luc import va gan middleware xac thuc tu day.
# conftest.py o goc du an duoc pytest nap som nhat, nen cho nay la dung.
os.environ["API_KEYS"] = ""

# CUNG MOT LY DO, cho cong dang nhap nguoi dung (Ngay 23).
#
# `AUTH_REQUIRED` ra doi SAU khi tep nay duoc viet, nen no khong duoc ep - va
# bay lai sap y nguyen: hom bat dang nhap len de thu tren may, `backend/.env`
# co `AUTH_REQUIRED=true`, va cac test webhook do voi 401 thay vi 400.
#
# Chung KHONG cuu duoc bang `dependency_overrides[get_settings]`, vi
# middleware xac thuc duoc gan MOT LAN luc `main.py` duoc import, tu
# `get_settings()` luc do. Doi dependency sau khi da gan thi khong voi toi
# middleware nua.
#
# CI khong lo ra loi nay vi `.env` nam trong .gitignore: tren may chay CI
# khong co tep do, nen mac dinh (tat) duoc dung. Nghia la bo test xanh tren
# CI va do tren may nguoi phat trien - dung kieu phu thuoc an ma tep nay
# sinh ra de dep bo.
os.environ["AUTH_REQUIRED"] = "false"

# CUNG MOT LY DO, cho khoa ky phieu dang nhap (Ngay 23).
#
# De trong thi `Settings.jwt_signing_key` sinh mot khoa NGAU NHIEN cho moi
# doi tuong Settings. Trong bo test co it nhat hai doi tuong nhu vay: mot cai
# `main.py` tao luc import de gan middleware, va mot cai moi fixture tu tao.
# Hai khoa khac nhau nghia la phieu do endpoint dang nhap cap ra KHONG BAO GIO
# giai ma duoc o middleware - va trieu chung se la "dang nhap thanh cong roi
# van bi 401", mot dieu rat kho lan ra.
#
# Dat mot gia tri co dinh o day de ca hai dung chung mot khoa. Gia tri nay
# CHI dung trong bo test; khi chay that, `.env` quyet dinh.
os.environ.setdefault("JWT_SECRET", "khoa-chi-dung-trong-bo-test-khong-dung-that")


import pytest


@pytest.fixture(autouse=True)
def _xoa_han_muc_dang_nhap():
    """Tra bo dem chong do mat khau ve 0 truoc MOI test, o MOI thu muc test.

    `user_routes._chan_dang_nhap` la mot doi tuong cap module: no khong bi
    tao lai giua cac test, va `TestClient` thi luon goi tu cung mot dia chi.
    Sau muoi lan dang nhap la cac test con lai do voi 429 - mot kieu do
    khong lien quan gi den thu dang kiem.

    VI SAO O CONFTEST GOC chu khong o `backend/tests/conftest.py`: bo dem do
    la trang thai cua CA TIEN TRINH, nen no vat qua ca ranh gioi thu muc
    test. Dat o backend thi `mcp_server/tests` - von cung dang nhap that -
    khong duoc bao ve, va do dung la cach loi nay da lo ra.
    """
    from app.user_routes import _chan_dang_nhap

    _chan_dang_nhap.xoa_het()
    yield
