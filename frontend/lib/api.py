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
    return httpx.Client(base_url=API_BASE_URL, timeout=TIMEOUT_S)


def _request(method: str, path: str, **kwargs: Any) -> Any:
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
        return res.json()

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


def create_scan(filename: str, data: bytes, mime: str) -> dict[str, Any]:
    """Ngay 3: POST /api/scans."""
    return _request(
        "POST", "/api/scans", files={"file": (filename, data, mime)}
    )


def get_scan(scan_id: str) -> dict[str, Any]:
    """Ngay 4: trang thai + raw_text + ban nhap da chuan hoa."""
    return _request("GET", f"/api/scans/{scan_id}")


def search_contacts(q: str = "", page: int = 1, size: int = 20) -> dict[str, Any]:
    """Ngay 7."""
    return _request(
        "GET", "/api/contacts", params={"q": q, "page": page, "size": size}
    )


def get_image(image_ref: str) -> bytes:
    """Tai anh goc ve de hien thi. Anh khong duoc phuc vu truc tiep ra ngoai."""
    res = _client().get(f"/api/images/{image_ref}")
    res.raise_for_status()
    return res.content
