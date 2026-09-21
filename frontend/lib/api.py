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


def _request(method: str, path: str, *, raw: bool = False, **kwargs: Any) -> Any:
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
    raise ApiError(
        err.get("code", "UNKNOWN"),
        err.get("message", f"Loi {res.status_code}"),
        bool(err.get("retryable", False)),
        res.status_code,
    )


# --- Cac loi goi cu the -----------------------------------------------------

def health() -> dict[str, Any]:
    return _request("GET", "/api/health")


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


def export_contacts(format: str) -> bytes:
    return _request("GET", "/api/export", params={"format": format}, raw=True)


def get_image(image_ref: str) -> bytes:
    """Tai anh goc ve de hien thi. Anh khong duoc phuc vu truc tiep ra ngoai."""
    res = _client().get(f"/api/images/{image_ref}")
    res.raise_for_status()
    return res.content


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
