"""Webhook: bao cho he thong ben ngoai khi mot ban quet xu ly xong.

MOC 17/09. Day la tinh nang DUY NHAT trong du an gui du lieu RA NGOAI toi mot
dia chi do nguoi dung nhap, nen no doi xu ly can than hon phan con lai.

BA RUI RO VA CACH XU LY

1. SSRF. URL callback do nguoi dung cung cap - dung be mat ma buoc tra cuu
   doanh nghiep da phai dung bo chan rieng. Dung lai chinh bo do
   (`enrich/fetcher`), khong viet lai.

2. DNS rebinding. Ten mien co the tro toi dia chi cong khai luc dang ky roi
   doi sang dia chi noi bo luc gui. Vi vay phai kiem tra lai o TUNG LAN GUI,
   va gui thang toi dia chi IP da kiem chu khong de thu vien tu phan giai lai.

3. Chua co xac thuc. Bat ky ai goi duoc API deu co the dang ky mot URL va
   nhan toan bo du lieu ban quet. Vi vay tinh nang nay MAC DINH TAT
   (`WEBHOOK_ENABLED=false`). Truoc khi mo ra ngoai mang noi bo phai them
   xac thuc - xem phan "Xac thuc" trong tai lieu API.

Ben nhan xac minh yeu cau that su den tu day bang chu ky HMAC-SHA256 trong
header `X-Signature-256`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import Base, new_id, utcnow
from app.services.enrich.fetcher import FetchError, resolve_public, validate_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks")

SIGNATURE_HEADER = "X-Signature-256"
EVENT_SCAN_DONE = "scan.completed"


class WebhookTarget(Base):
    __tablename__ = "webhook_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # Bi mat dung de ky. KHONG BAO GIO tra ve trong phan hoi API sau lan tao.
    secret: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow, nullable=False)
    last_status: Mapped[str | None] = mapped_column(String(32))
    last_attempt_at: Mapped[str | None] = mapped_column(String(40))


class RegisterWebhook(BaseModel):
    url: str = Field(max_length=2048)


def sign(secret: str, payload: bytes) -> str:
    """Chu ky de ben nhan xac minh yeu cau den tu day."""
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _checked_url(url: str) -> tuple[str, str, int]:
    """Kiem tra URL bang dung bo chan cua buoc tra cuu doanh nghiep."""
    try:
        return validate_url(url)
    except FetchError as exc:
        raise ApiError(
            "WEBHOOK_URL_REJECTED",
            "URL không hợp lệ hoặc trỏ tới địa chỉ mạng nội bộ. "
            "Chỉ nhận http/https tới địa chỉ công khai.",
            400,
        ) from exc


def deliver(target: WebhookTarget, event: str, data: dict,
            config: Settings) -> tuple[bool, str]:
    """Gui mot su kien. Tra ve (thanh cong, mo ta trang thai).

    Thu lai co gioi han va co backoff. KHONG thu lai loi 4xx: ben nhan da tu
    choi noi dung, gui lai y het chi lam phien ho va khong bao gio thanh cong.
    """
    body = json.dumps(
        {"event": event, "sent_at": utcnow(), "data": data},
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        SIGNATURE_HEADER: sign(target.secret, body),
        "User-Agent": config.enrich_user_agent,
    }

    last = "chua gui"
    for attempt in range(config.webhook_max_attempts):
        if attempt:
            time.sleep(min(2 ** attempt, 8))

        # Kiem tra lai o TUNG LAN GUI. Ten mien co the da doi sang dia chi noi
        # bo ke tu luc dang ky; chi kiem mot lan luc dang ky la khong du.
        try:
            normalized, host, port = validate_url(target.url)
            # Gia tri tra ve khong dung den; goi ham nay la de no NEM
            # FetchError khi dia chi tro vao mang noi bo.
            resolve_public(host, port, config.webhook_timeout_s)
        except FetchError as exc:
            return False, f"dia chi bi chan: {exc}"

        try:
            with httpx.Client(
                timeout=config.webhook_timeout_s,
                # Khong di theo chuyen huong: mot lan chuyen huong co the dan
                # toi dia chi noi bo ma bo chan khong con co hoi kiem tra.
                follow_redirects=False,
                # Gui thang toi dia chi da kiem, khong de thu vien phan giai
                # lai ten mien (co the ra dia chi khac).
                transport=httpx.HTTPTransport(local_address=None),
            ) as client:
                response = client.post(normalized, content=body, headers=headers,
                                       extensions={"sni_hostname": host})
        except httpx.HTTPError as exc:
            last = f"loi mang: {type(exc).__name__}"
            continue

        if response.is_success:
            return True, f"HTTP {response.status_code}"
        last = f"HTTP {response.status_code}"
        if 400 <= response.status_code < 500 and response.status_code != 429:
            return False, last + " (khong thu lai)"

    return False, last


def dispatch_scan_completed(scan_id: str, payload: dict, config: Settings,
                            session_factory) -> None:
    """Bao cho moi dich da dang ky rang mot ban quet da xong.

    Loi gui webhook KHONG duoc anh huong toi ban quet - no da xu ly xong roi.
    Vi vay moi loi deu bi nuot lai va chi ghi log.
    """
    if not config.webhook_enabled:
        return

    with session_factory() as db:
        targets = list(db.scalars(
            select(WebhookTarget).where(WebhookTarget.enabled.is_(True))))
        for target in targets:
            ok, status = deliver(target, EVENT_SCAN_DONE,
                                 {"scan_id": scan_id, **payload}, config)
            target.last_status = status[:32]
            target.last_attempt_at = utcnow()
            if not ok:
                logger.warning("Webhook %s that bai: %s", target.id, status)
        db.commit()


def _public(target: WebhookTarget) -> dict:
    """Ban ghi tra ve cho nguoi dung - KHONG kem bi mat ky."""
    return {
        "id": target.id, "url": target.url, "enabled": target.enabled,
        "created_at": target.created_at, "last_status": target.last_status,
        "last_attempt_at": target.last_attempt_at,
    }


@router.post("", status_code=201)
def register(body: RegisterWebhook, db: Session = Depends(get_db),
             config: Settings = Depends(get_settings)) -> dict:
    if not config.webhook_enabled:
        raise ApiError(
            "WEBHOOK_DISABLED",
            "Webhook đang tắt. Bật bằng WEBHOOK_ENABLED=true trong backend/.env. "
            "Chỉ bật khi API đã có xác thực hoặc chỉ chạy trong mạng nội bộ.",
            409,
        )

    normalized, _, _ = _checked_url(body.url)
    if db.scalar(select(WebhookTarget).where(WebhookTarget.url == normalized)):
        raise ApiError("WEBHOOK_DUPLICATE", "URL này đã được đăng ký.", 409)

    target = WebhookTarget(url=normalized, secret=secrets.token_urlsafe(32))
    db.add(target)
    db.commit()

    # Bi mat ky chi duoc tra ve DUY NHAT lan nay. Cac lan doc sau khong co no.
    return {**_public(target), "secret": target.secret,
            "signature_header": SIGNATURE_HEADER,
            "note": "Lưu khóa bí mật ngay — nó không hiển thị lại lần nào nữa."}


@router.get("")
def list_targets(db: Session = Depends(get_db)) -> dict:
    targets = db.scalars(select(WebhookTarget).order_by(WebhookTarget.created_at))
    return {"items": [_public(t) for t in targets]}


@router.patch("/{target_id}")
def set_enabled(target_id: str, enabled: bool,
                db: Session = Depends(get_db)) -> dict:
    target = db.get(WebhookTarget, target_id)
    if target is None:
        raise ApiError("WEBHOOK_NOT_FOUND", "Không có webhook với mã này.", 404)
    target.enabled = enabled
    db.commit()
    return _public(target)


@router.delete("/{target_id}", status_code=204)
def remove(target_id: str, db: Session = Depends(get_db)) -> None:
    target = db.get(WebhookTarget, target_id)
    if target is None:
        raise ApiError("WEBHOOK_NOT_FOUND", "Không có webhook với mã này.", 404)
    db.delete(target)
    db.commit()
