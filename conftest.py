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
