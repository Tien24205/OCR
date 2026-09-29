"""Vo ASGI cho giao dien: bien app Streamlit thanh mot PWA cai duoc (Ngay 26).

    streamlit run frontend/asgi_app.py

VI SAO CAN MOT VO RIENG: de "Them vao man hinh chinh" tren dien thoai hoat
dong, trang phai khai bao mot `manifest` trong the `<head>`. Streamlit dung
trang `index.html` cua rieng no va khong cho chen vao `<head>` - `st.markdown`
va `st.html` deu do noi dung vao THAN trang, ma the `<link rel="manifest">`
o trong than thi trinh duyet bo qua.

`st.App` la duong CHINH THUC de lam viec nay: no cho them route va middleware
quanh dung app Streamlit do, khong dung toi DOM bang JavaScript. Cach hay gap
tren mang - nhet mot iframe an roi `window.parent.document.head.appendChild`
- chay duoc, nhung no phu thuoc vao cau truc DOM ben trong cua Streamlit, va
cau truc do khong phai giao dien cong khai.

`streamlit_app.py` VAN chay thang duoc nhu cu (`streamlit run
frontend/streamlit_app.py`); khi do chi thieu phan cai len man hinh chinh.
Toan bo bo test dung `AppTest` tren tep do nen khong bi anh huong.
"""

from __future__ import annotations

import json
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.routing import Route

TEN_APP = "CardLens · Danh thiếp thành hồ sơ đối tác"
TEN_NGAN = "CardLens"          # hien duoi icon tren man hinh chinh
MAU_NEN = "#070C24"              # trung voi `backgroundColor` trong .streamlit/config.toml
MAU_NHAN = "#3D63F5"             # trung voi `primaryColor` - icon phai cung mau voi app

# Cac co icon can co. 192 va 512 la hai co Android doi; 180 la co cua
# `apple-touch-icon` tren iOS.
CO_ICON = (180, 192, 512)


# --------------------------------------------------------------------------
# Icon: sinh bang PIL thay vi cam san tep PNG
# --------------------------------------------------------------------------
#
# VI SAO SINH: ba tep PNG trong kho ma nguon la ba tep nhi phan khong ai doc
# duoc trong ban dif, va doi mau nhan la phai sinh lai ca ba bang tay. Sinh
# tu ma nguon thi icon la MA NGUON - sua mot hang so o tren la xong.
#
# `lru_cache`: sinh mot lan cho ca tien trinh. Trinh duyet xin icon vai lan
# trong doi mot phien.

@lru_cache(maxsize=len(CO_ICON))
def _icon_png(canh: int) -> bytes:
    anh = Image.new("RGB", (canh, canh), MAU_NEN)
    but = ImageDraw.Draw(anh)

    # Mot tam the nam ngang, ti le 1.6:1 - dung ti le danh thiep that.
    rong = int(canh * 0.62)
    cao = int(rong / 1.6)
    trai = (canh - rong) // 2
    tren = (canh - cao) // 2
    but.rounded_rectangle([trai, tren, trai + rong, tren + cao],
                          radius=max(2, canh // 28), fill="#ffffff")

    # Ba dong chu gia tren the, va mot vach nhan.
    dem = max(1, canh // 40)
    day = max(2, canh // 48)
    y = tren + dem * 2
    but.rectangle([trai + dem * 2, y, trai + rong - dem * 6, y + day * 2],
                  fill=MAU_NHAN)
    for i in range(2):
        y += day * 4
        but.rectangle([trai + dem * 2, y, trai + rong - dem * (4 + i * 4), y + day],
                      fill="#9aa0a6")

    ra = BytesIO()
    anh.save(ra, format="PNG")
    return ra.getvalue()


def _manifest() -> dict:
    return {
        "name": TEN_APP,
        "short_name": TEN_NGAN,
        "description": "CardLens: chụp danh thiếp, nhận hồ sơ đối tác tin được.",
        "start_url": "/",
        "scope": "/",
        # `standalone` la thu bien trang web thanh mot thu trong nhu app:
        # khong thanh dia chi, khong nut back cua trinh duyet.
        "display": "standalone",
        "orientation": "portrait",
        "background_color": MAU_NEN,
        "theme_color": MAU_NEN,
        "lang": "vi",
        "icons": [
            {"src": f"/icon-{c}.png", "sizes": f"{c}x{c}", "type": "image/png",
             # `maskable` cho Android tu cat icon theo hinh dang cua may,
             # thay vi dan mot o vuong trang len man hinh.
             "purpose": "any maskable"}
            for c in (192, 512)
        ],
    }


# Service worker TOI THIEU, CO Y KHONG LUU DEM GI CA.
#
# Chrome doi trang phai co service worker dang ky thi moi moi cai dat. Nhung
# mot service worker CO luu dem tren ung dung nay se la mot loi bao mat: no
# se giu lai anh danh thiep va ho so doi tac trong bo nho dem cua trinh
# duyet, nam ngoai moi phep kiem quyen cua backend va song lau hon ca phien
# dang nhap.
#
# Nen no chi chuyen tiep. Duoc cai dat, khong giu gi.
SERVICE_WORKER = b"""// Khong luu dem CO Y - xem asgi_app.py.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (e) => e.respondWith(fetch(e.request)));
"""

# --------------------------------------------------------------------------
# Vai net CSS cho nhung thu `[theme]` khong noi duoc
# --------------------------------------------------------------------------
#
# Bang mau, bo chu va do bo goc nam trong `.streamlit/config.toml` - do la
# duong native, va no ap duoc ca cho nhung thanh phan ve bang canvas. Con lai
# duoi day CHI la nhung thu theme khong dien ta duoc: khoang cach, co chu
# theo be ngang man hinh, va vien ngoai khi go phim Tab.
#
# CHON BANG `data-testid` CHU KHONG PHAI TEN LOP: ten lop cua Streamlit la
# chuoi bam sinh ra luc dung, doi sau moi lan nang cap va khong bao truoc.
# `data-testid` la thu bo test chinh thuc cua Streamlit bam vao, nen no on
# dinh hon nhieu. Du vay day van la giao dien khong cam ket - nen moi net o
# duoi deu chi la TO THEM: mat het CSS nay thi trang xau di chu khong hong.
#
# KHONG dat trong `.format()` ben duoi, co y: CSS day dau ngoac nhon, ma
# `str.format` se doi doubling tung cai mot. Noi chuoi thi khong phai nghi.
KIEU_DANG = b"""
<style>
  /* Streamlit chua mot khoang trong rat rong tren dau trang. Tren dien thoai
     no day tieu de xuong gan nua man hinh, va nguoi dung phai cuon moi thay
     duoc noi dung dau tien. */
  [data-testid="stMainBlockContainer"] {
    padding-top: 2.25rem;
    padding-bottom: 3rem;
    max-width: 1200px;
  }

  /* Co chu tieu de chay theo be ngang: 2.1rem vua man hinh may tinh nhung
     tren dien thoai thi "Danh thiep -> Ho so doi tac" vo thanh ba dong. */
  h1 {
    font-size: clamp(1.45rem, 4.2vw, 2.1rem);
    letter-spacing: -0.015em;
  }

  /* Le hai ben mac dinh an mat gan mot phan tu be ngang dien thoai. */
  @media (max-width: 640px) {
    [data-testid="stMainBlockContainer"] {
      padding-left: 1rem;
      padding-right: 1rem;
    }
  }

  /* So lieu tren trang Tong quan troi tren nen trong, khong ro cai nao di
     voi cai nao. Bo chung vao the cho thanh tung khoi doc duoc. */
  [data-testid="stMetric"] {
    background: linear-gradient(160deg, rgba(61, 99, 245, 0.16), rgba(61, 99, 245, 0.04));
    border: 1px solid rgba(143, 168, 255, 0.22);
    border-radius: 0.7rem;
    padding: 0.85rem 1rem;
  }

  .stButton button:active,
  .stFormSubmitButton button:active,
  .stDownloadButton button:active {
    transform: translateY(1px);
  }

  /* KHONG BO DUOC: vien ngoai khi di chuyen bang phim Tab. Thieu no thi
     nguoi khong dung duoc chuot se khong biet minh dang dung o dau. */
  :focus-visible {
    outline: 2px solid #8FA8FF;
    outline-offset: 2px;
  }

  /* Email va dia chi dai tran ra ngoai khung tren dien thoai. */
  [data-testid="stMarkdownContainer"] {
    overflow-wrap: break-word;
  }
</style>
"""

THE_HEAD = ("""
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="{mau}">
<meta name="mobile-web-app-capable" content="yes">
<!-- iOS khong doc `display: standalone` trong manifest; no doc ba the duoi. -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="{ten}">
<link rel="apple-touch-icon" href="/icon-180.png">
<script>
  if ('serviceWorker' in navigator) {{
    window.addEventListener('load', function () {{
      navigator.serviceWorker.register('/sw.js').catch(function () {{}});
    }});
  }}
</script>
""").format(mau=MAU_NEN, ten=TEN_NGAN).encode("utf-8") + KIEU_DANG


async def _tra_manifest(request):
    return Response(json.dumps(_manifest(), ensure_ascii=False),
                    media_type="application/manifest+json")


async def _tra_sw(request):
    # `Service-Worker-Allowed` cho phep pham vi `/` du tep duoc phuc vu o dau.
    return Response(SERVICE_WORKER, media_type="application/javascript",
                    headers={"Service-Worker-Allowed": "/",
                             "Cache-Control": "no-cache"})


async def _tra_icon(request):
    try:
        canh = int(request.path_params["canh"])
    except (KeyError, ValueError):
        return Response(status_code=404)
    if canh not in CO_ICON:
        return Response(status_code=404)
    return Response(_icon_png(canh), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


# --------------------------------------------------------------------------
# Ghi nho dang nhap: phieu nam trong cookie HttpOnly
# --------------------------------------------------------------------------
#
# `st.session_state` mat khi tai lai trang, nen "ghi nho dang nhap" can mot
# cho song lau hon phien. Luu PHIEU (co han, thu hoi duoc) chu KHONG luu mat
# khau, va luu trong cookie HttpOnly: JavaScript tren trang - ke ca mot doan
# ma doc bi chen vao - khong doc duoc no. Streamlit doc lai bang
# `st.context.cookies` luc mo trang.
TEN_COOKIE = "cardlens_phien"
NHO_TOI_DA_GIAY = 30 * 24 * 3600


def _cung_nguon(request) -> bool:
    """Chan dat cookie tu trang khac (login CSRF: ep nguoi dung vao tai
    khoan cua ke tan cong de ho nhap du lieu vao do)."""
    from urllib.parse import urlsplit

    nguon = request.headers.get("origin") or request.headers.get("referer") or ""
    return bool(nguon) and urlsplit(nguon).netloc == request.headers.get("host")


async def _phien(request):
    if not _cung_nguon(request):
        return Response(status_code=403)
    tra_loi = Response(status_code=204, headers={"Cache-Control": "no-store"})
    if request.method == "DELETE":
        tra_loi.delete_cookie(TEN_COOKIE, path="/")
        return tra_loi
    try:
        than = await request.json()
        phieu = str(than["token"])
        song = int(than.get("max_age") or 0)
    except (ValueError, KeyError, TypeError):
        return Response(status_code=400)
    if not phieu or len(phieu) > 4096 or song <= 0:
        return Response(status_code=400)
    # Sau Cloudflare Tunnel, ket noi toi day la http noi bo; trinh duyet thi
    # dang o https. Doc header cua proxy de cookie van duoc danh dau Secure.
    https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    tra_loi.set_cookie(TEN_COOKIE, phieu, max_age=min(song, NHO_TOI_DA_GIAY), path="/",
                       httponly=True, samesite="strict", secure=https)
    return tra_loi


class ChenTheVaoHead(BaseHTTPMiddleware):
    """Chen cac the PWA vao `<head>` cua trang Streamlit.

    Chi dong vao cau tra loi HTML. Moi thu khac - WebSocket cua Streamlit,
    tep tinh, anh - di qua khong suy suyen.
    """

    async def dispatch(self, request, call_next):
        tra_loi = await call_next(request)
        if not tra_loi.headers.get("content-type", "").startswith("text/html"):
            return tra_loi

        than = b"".join([khuc async for khuc in tra_loi.body_iterator])
        if b"</head>" in than:
            than = than.replace(b"</head>", THE_HEAD + b"</head>", 1)

        dau = dict(tra_loi.headers)
        # Do dai da doi sau khi chen; de nguyen la trinh duyet cat mat phan
        # duoi cua trang.
        dau.pop("content-length", None)
        return Response(than, status_code=tra_loi.status_code, headers=dau,
                        media_type=tra_loi.media_type)


app = st.App(
    str(Path(__file__).parent / "streamlit_app.py"),
    routes=[
        Route("/manifest.webmanifest", _tra_manifest),
        Route("/sw.js", _tra_sw),
        Route("/icon-{canh}.png", _tra_icon),
        Route("/phien", _phien, methods=["POST", "DELETE"]),
    ],
    middleware=[Middleware(ChenTheVaoHead)],
)


if __name__ == "__main__":
    app.run()
