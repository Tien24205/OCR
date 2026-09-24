"""Lop goi API duy nhat cua frontend.

KHAC BIET QUAN TRONG SO VOI FRONTEND SPA:

Streamlit chay o phia may chu. Trinh duyet chi noi chuyen voi Streamlit;
Streamlit moi goi FastAPI bang httpx. Nghia la:

  - Khong co loi CORS (khong co request chéo nguon tu trinh duyet).
  - Khong co bien cau hinh nao bi nhung vao ma nguon gui xuong trinh duyet.
  - Anh danh thiep khong bao gio duoc phuc vu truc tiep ra Internet; Streamlit
    tai bytes ve roi ve len trang.

Du vay khoa dich vu (Google Vision, Gemini) VAN nam o backend, khong nam o day.
Frontend chi biet mot thu: URL cua backend.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT_S = 30.0

# Khoa API, neu backend co bat xac thuc.
#
# VI SAO KHOA NAM O DAY LA AN TOAN: Streamlit chay PHIA MAY CHU. Trinh duyet
# chi nhan HTML da dung san, khong bao gio thay bien moi truong nay - dung
# nhu cach khoa Gemini khong bao gio roi khoi backend.
def _doc_khoa() -> str:
    """Khoa API, neu backend co bat xac thuc.

    Nhan CA HAI ten bien vi hai cach chay dat ten khac nhau:

      API_KEY   - chay tay: nguoi dung dat rieng cho giao dien
      API_KEYS  - chay bang Docker Compose: giao dien doc chung
                  `backend/.env` voi backend, va o do bien ten la API_KEYS

    Lay khoa DAU TIEN khi co nhieu khoa. Cac khoa con lai danh cho he thong
    tich hop ben ngoai, de thu hoi rieng tung cai ma khong lam hong giao dien.
    """
    khoa = os.environ.get("API_KEY", "").strip()
    if khoa:
        return khoa
    nhieu = os.environ.get("API_KEYS", "")
    return next((k.strip() for k in nhieu.split(",") if k.strip()), "")


API_KEY = _doc_khoa()


class ApiError(Exception):
    def __init__(self, code: str, message: str, retryable: bool, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status = status


@st.cache_resource
def _client() -> httpx.Client:
    """Mot client dung chung cho ca tien trinh (giu ket noi, khong tao lai
    moi lan Streamlit chay lai script)."""
    # Dat khoa o muc CLIENT chu khong o tung loi goi: dat o tung loi goi thi
    # chi can quen mot cho la loi goi do hong, va no se hong am tham cho den
    # khi ai do bat xac thuc len.
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    return httpx.Client(base_url=API_BASE_URL, timeout=TIMEOUT_S,
                        headers=headers)


def _phieu() -> str:
    """Phieu dang nhap cua PHIEN TRINH DUYET HIEN TAI, neu co.

    VI SAO KHONG DAT PHIEU VAO `_client()` NHU DA LAM VOI KHOA API: `_client`
    duoc boc bang `@st.cache_resource`, nghia la MOT doi tuong dung chung cho
    CA TIEN TRINH - moi phien trinh duyet, moi nguoi dung. Dat phieu cua
    nguoi A vao do thi nguoi B mo trang ngay sau se goi API bang danh tinh
    cua A. Do la ro ri tai khoan, va no se khong bao gio lo ra trong luc thu
    mot minh.

    Khoa API thi dat o client duoc, vi no giong nhau cho moi nguoi.
    """
    try:
        return st.session_state.get("phieu_dang_nhap") or ""
    except Exception:
        # Ngoai mot lan chay script cua Streamlit (vi du trong bo test goi
        # thang), session_state khong ton tai. Khong co phien thi khong co
        # phieu - khong phai loi.
        return ""


def _dau_xac_thuc(kwargs: dict) -> dict:
    """Ghep dung MOT danh tinh vao loi goi.

    Backend doc `X-API-Key` TRUOC roi moi doc `Authorization`. Nen neu gui ca
    hai, phieu nguoi dung bi bo qua va moi nguoi deu hien ra la "he thong" -
    thay duoc du lieu cua nhau. Do la ly do phai XOA khoa API khi da dang
    nhap, chu khong phai chi them phieu vao.
    """
    phieu = _phieu()
    if not phieu:
        return kwargs
    dau = dict(kwargs.get("headers") or {})
    dau["Authorization"] = f"Bearer {phieu}"
    dau["X-API-Key"] = ""            # chuoi rong => backend bo qua, doc phieu
    return {**kwargs, "headers": dau}


def _request(method: str, path: str, *, raw: bool = False, **kwargs: Any) -> Any:
    kwargs = _dau_xac_thuc(kwargs)
    try:
        res = _client().request(method, path, **kwargs)
    except httpx.RequestError as exc:
        raise ApiError(
            "BACKEND_UNREACHABLE",
            f"Khong ket noi duoc backend tai {API_BASE_URL}.",
            retryable=True,
            status=0,
        ) from exc

    if res.is_success:
        return res.content if raw else res.json()

    body: dict[str, Any] = {}
    try:
        body = res.json()
    except ValueError:
        pass
    err = body.get("error", {}) if isinstance(body, dict) else {}

    # PHIEU HET HAN hoac bi thu hoi. Xoa ngay tai day - day la cho DUY NHAT
    # moi loi goi deu di qua, nen khong co duong nao giu lai mot phieu da
    # chet. Khong xoa thi nguoi dung ket o mot man hinh bao 401 lien tuc ma
    # khong co nut nao dua ho ve trang dang nhap.
    #
    # Chi xoa khi loi goi NAY co mang phieu: 401 tu mot loi goi khong mang
    # phieu noi len chuyen khac (vi du thieu khoa API), khong phai phien hong.
    if res.status_code == 401 and _phieu():
        try:
            st.session_state.pop("phieu_dang_nhap", None)
            st.session_state.pop("nguoi_dung", None)
        except Exception:
            pass

    raise ApiError(
        err.get("code", "UNKNOWN"),
        err.get("message", f"Loi {res.status_code}"),
        bool(err.get("retryable", False)),
        res.status_code,
    )


# --- Cac loi goi cu the -----------------------------------------------------

def health() -> dict[str, Any]:
    return _request("GET", "/api/health")


# --- Dang nhap (Ngay 23) -----------------------------------------------------

def dang_ky(email: str, mat_khau: str, ten: str = "") -> dict[str, Any]:
    return _request("POST", "/api/auth/register", json={
        "email": email, "password": mat_khau, "display_name": ten or None})


def dang_nhap(email: str, mat_khau: str) -> dict[str, Any]:
    return _request("POST", "/api/auth/login",
                    json={"email": email, "password": mat_khau})


def toi_la_ai() -> dict[str, Any]:
    return _request("GET", "/api/auth/me")


def verify_readiness() -> dict[str, Any]:
    """Xac minh dich vu bang loi goi that. TON HAN MUC - chi goi khi nguoi
    dung bam nut, khong bao gio goi tu dong theo moi lan ve lai giao dien."""
    return _request("POST", "/api/readiness/verify")


def create_scan(filename: str, data: bytes, mime: str) -> dict[str, Any]:
    """Ngay 3: POST /api/scans."""
    return _request(
        "POST", "/api/scans", files={"file": (filename, data, mime)}
    )


def get_scan(scan_id: str) -> dict[str, Any]:
    """Ngay 4: trang thai + raw_text + ban nhap da chuan hoa."""
    return _request("GET", f"/api/scans/{scan_id}", timeout=5.0)


def retry_scan(scan_id: str) -> dict[str, Any]:
    return _request("POST", f"/api/scans/{scan_id}/retry")


def save_draft(scan_id: str, fields: dict, revision: int) -> dict[str, Any]:
    return _request("PATCH", f"/api/scans/{scan_id}/draft", json={"fields": fields, "revision": revision})


def start_enrichment(scan_id: str, revision: int) -> dict:
    return _request("POST", f"/api/scans/{scan_id}/enrich", json={"revision": revision})


def get_research(organization_id: str) -> dict:
    return _request("GET", f"/api/organizations/{organization_id}", timeout=5.0)["research"]


def retry_enrichment(organization_id: str) -> dict:
    return _request("POST", f"/api/organizations/{organization_id}/enrich")


def review_enrichment(enrichment_id: str, decision: str) -> dict:
    return _request("PATCH", f"/api/enrichments/{enrichment_id}", json={"decision": decision})


def search_contacts(q: str = "", page: int = 1, size: int = 20) -> dict[str, Any]:
    """Ngay 7."""
    return _request(
        "GET", "/api/contacts", params={"q": q, "page": page, "size": size}
    )


def get_contact(contact_id: str) -> dict:
    return _request("GET", f"/api/contacts/{contact_id}")


def scan_duplicates(scan_id: str, organization_id: str | None = None) -> dict:
    return _request("GET", f"/api/scans/{scan_id}/duplicates",
                    params={"organization_id": organization_id} if organization_id else {})


def save_contact(body: dict, key: str) -> dict:
    return _request("POST", "/api/contacts", json=body, headers={"Idempotency-Key": key})


def edit_contact(contact_id: str, body: dict) -> dict:
    return _request("PATCH", f"/api/contacts/{contact_id}", json=body)


def organization_choices() -> dict:
    return _request("GET", "/api/organizations")


def nhat_ky_xuat(limit: int = 50) -> dict[str, Any]:
    """Nhung lan du lieu da roi khoi he thong (Ngay 30)."""
    return _request("GET", "/api/export/log", params={"limit": limit})


def export_contacts(format: str) -> bytes:
    return _request("GET", "/api/export", params={"format": format}, raw=True)


def get_image(scan_id: str) -> bytes:
    """Tai anh goc ve de hien thi. Anh khong duoc phuc vu truc tiep ra ngoai.

    Di qua `_request` chu khong goi thang `_client()` nua: goi thang thi loi
    goi nay la loi goi DUY NHAT khong mang phieu dang nhap, va anh se duoc
    tai bang danh tinh khac voi phan con lai cua trang.
    """
    return _request("GET", f"/api/scans/{scan_id}/image", raw=True)


def stats() -> dict[str, Any]:
    """So lieu tong quan cho trang Bang dieu khien."""
    return _request("GET", "/api/stats")


def list_scans(limit: int = 12) -> dict[str, Any]:
    """Cac ban quet gan day - de trang Kiem tra mo lai mot the cu."""
    return _request("GET", "/api/scans", params={"limit": limit})


def scans_status(ids: list[str]) -> dict[str, Any]:
    """Trang thai ca lo trong MOT loi goi.

    Hoi tung ban quet mot se nhan so loi goi theo so anh va dung gioi han tan
    suat (60/phut) - luc do chinh cai bang theo doi lam nguoi dung bi chan.
    """
    return _request("GET", "/api/scans/status", params={"ids": ",".join(ids)})


def create_batch(items: list[tuple[str, bytes, str]]) -> dict[str, Any]:
    """Gui nhieu anh trong mot yeu cau.

    Backend gioi han so anh moi lo va xu ly voi so luong dong thoi co gioi han.
    Mot anh hong khong lam hong ca lo: moi anh co muc ket qua rieng.
    """
    return _request("POST", "/api/scans/batch", files=[
        ("files", (name, data, mime)) for name, data, mime in items
    ])
