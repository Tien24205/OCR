"""Xac thuc API bang khoa, kem gioi han tan suat.

VI SAO CAN: truoc lop nay, mot lenh `curl http://host:8000/api/contacts` khong
kem gi ca tra ve HTTP 200 va toan bo kho ho so doi tac. Do la ly do webhook
phai tat mac dinh - khong the cho phep bat ky ai dat mot dia chi de he thong
gui du lieu toi.

VI SAO DUNG MIDDLEWARE CHU KHONG DUNG DEPENDENCY: `Depends(...)` phai gan vao
TUNG endpoint. Nguoi them endpoint moi co the quen, va khi quen thi khong co
gi bao - endpoint do lang le mo toang. Middleware chan moi duong dan, ke ca
duong dan viet sau lop nay, nen no HONG VE PHIA DONG thay vi hong ve phia mo.

VI SAO CO CHE DO TAT: cong cu nay chay tren may ca nhan la chinh. Bat buoc
dat khoa moi chay duoc se khien nguoi ta dat khoa "1234" cho xong - te hon la
khong co khoa ma biet ro minh khong co. Nen:

    API_KEYS trong        -> khong xac thuc, VA noi ro dieu do o /api/health
                             cung nhu o dong log khi khoi dong
    API_KEYS co gia tri   -> bat buoc, moi loi goi deu phai kem khoa

Cach nay khong bao gio "tuong la an toan ma khong phai": trang thai that luon
hien ra.
"""

from __future__ import annotations

import logging
import secrets
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Nhung duong dan KHONG doi khoa.
#
#   /api/health  - de he thong giam sat biet dich vu con song. No chi tra ve
#                  co true/false, khong bao gio tra ve gia tri khoa nao.
#   /docs, ...   - tai lieu API. Doc duoc tai lieu khong dong nghia goi duoc.
PUBLIC_PATHS = frozenset({
    "/api/health", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect",
})


def khoa_hop_le(trinh_ra: str, cho_phep: list[str]) -> bool:
    """So khoa bang phep so THOI GIAN KHONG DOI.

    VI SAO KHONG DUNG `in`: phep so chuoi thong thuong dung ngay khi gap ky tu
    khac nhau dau tien, nen thoi gian tra loi ro ri thong tin ve do dai tien to
    dung. Ke tan cong do thoi gian co the do tung ky tu mot.

    `compare_digest` luon chay het do dai, nen thoi gian khong noi len gi.
    """
    if not trinh_ra:
        return False
    # Duyet HET danh sach, khong dung som khi da khop - de so lan so sanh
    # khong phu thuoc vao vi tri khoa dung trong danh sach.
    khop = False
    for k in cho_phep:
        if secrets.compare_digest(trinh_ra, k):
            khop = True
    return khop


def doc_khoa(request: Request) -> str:
    """Lay khoa tu `X-API-Key`, hoac tu `Authorization: Bearer ...`."""
    key = request.headers.get("x-api-key")
    if key:
        return key.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


class GioiHanTanSuat:
    """Dem so loi goi cua tung khoa trong mot cua so thoi gian truot.

    GIOI HAN DA BIET, GHI RA DE KHONG AI TUONG NHAM: bo dem nay nam TRONG BO
    NHO cua mot tien trinh. Nghia la:

      - chay nhieu tien trinh (hoac nhieu ban sao) thi moi ban dem rieng,
        tong so loi goi thuc te se cao hon gioi han da dat
      - khoi dong lai la mat sach bo dem

    Voi mot cong cu chay mot tien trinh thi the la du. Muon dung that o moi
    truong nhieu ban sao thi phai chuyen bo dem ra Redis hoac tuong duong -
    ghi ro trong roadmap chu khong de nguoi ta tu phat hien.
    """

    def __init__(self, moi_phut: int) -> None:
        self._moi_phut = moi_phut
        self._lich_su: dict[str, deque[float]] = defaultdict(deque)

    def cho_phep(self, khoa: str, bay_gio: float | None = None) -> bool:
        if self._moi_phut <= 0:          # 0 hoac am = khong gioi han
            return True
        bay_gio = time.monotonic() if bay_gio is None else bay_gio
        moc = self._lich_su[khoa]
        while moc and bay_gio - moc[0] >= 60.0:
            moc.popleft()
        if len(moc) >= self._moi_phut:
            return False
        moc.append(bay_gio)
        return True


def _tu_choi(code: str, message: str, status: int) -> JSONResponse:
    """Tra loi theo DUNG dang loi ma phan con lai cua API dung.

    Neu dang khac, giao dien va cac he thong tich hop se phai xu ly rieng mot
    truong hop - va thuong thi ho quen.
    """
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message,
                           "retryable": status == 429}},
    )


def gan_xac_thuc(app, cac_khoa: list[str], moi_phut: int) -> None:
    """Gan middleware xac thuc vao app.

    Goi ham nay ngay sau khi tao app, TRUOC khi khai bao endpoint cung duoc -
    middleware trong Starlette chay cho moi request bat ke thu tu khai bao.
    """
    if not cac_khoa:
        logger.warning(
            "API_KEYS trong: API dang mo, bat ky ai goi duoc cung doc duoc "
            "toan bo ho so. Chi nen de vay khi chi chay tren may ca nhan."
        )
        return

    gioi_han = GioiHanTanSuat(moi_phut)
    logger.info("Xac thuc API: BAT (%d khoa, %d loi goi/phut moi khoa)",
                len(cac_khoa), moi_phut)

    @app.middleware("http")
    async def _kiem_tra(request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        khoa = doc_khoa(request)
        if not khoa_hop_le(khoa, cac_khoa):
            # KHONG ghi gia tri khoa vao log, ke ca khoa sai: nguoi dung hay
            # go nham khoa that vao cho khac, va log thuong duoc chia se rong
            # hon nguoi ta tuong.
            logger.warning("Tu choi %s %s: khoa %s", request.method,
                           request.url.path,
                           "khong hop le" if khoa else "khong duoc cung cap")
            return _tu_choi(
                "UNAUTHORIZED",
                "Thiếu hoặc sai khóa API. Gửi kèm header `X-API-Key`.",
                401,
            )

        if not gioi_han.cho_phep(khoa):
            return _tu_choi(
                "RATE_LIMITED",
                f"Vượt quá {moi_phut} lời gọi mỗi phút. Thử lại sau ít giây.",
                429,
            )

        return await call_next(request)
