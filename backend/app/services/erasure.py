"""Xoa du lieu ca nhan, va don nhung gi qua han luu tru.

VI SAO CAN (san-sang-thuong-mai.md, C2): trong 27 endpoint, `DELETE` duy nhat
danh cho webhook. Khong co cach nao xoa mot ho so, mot ban quet, hay anh goc -
anh nam vo thoi han trong volume `ocr-data`. Nghi dinh 13/2023/ND-CP va GDPR
deu doi quyen xoa va thoi han luu tru. Day la rui ro phap ly, khong phai thieu
tien ich.

BAY PHAI TRANH - ANH DUNG CHUNG. Anh luu theo SHA-256 cua noi dung, nen quet
cung mot tam the hai lan chi tao MOT tep. Xoa ban quet roi xoa luon tep la lay
mat anh cua ban quet khac, va no khong hong ngay: giao dien van chay, chi den
luc ai do mo ban quet cu thi anh bao 404. Vi vay moi lan xoa deu hoi lai CSDL
"con ban quet nao tro toi ma bam nay khong" - SAU khi cac dong da bi xoa.

GIOI HAN CUA THOI HAN LUU TRU: no xoa BAN QUET (anh goc + van ban OCR), khong
xoa ho so da luu. Ho so la thu nguoi dung co y giu lai; anh danh thiep moi la
thu nam do vi chua ai don. Muon xoa ca ho so thi dung duong xoa rieng, vi do
la mot quyet dinh cua nguoi dung chu khong phai cua dong ho.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Contact, Scan
from app.services.storage import kho_anh

logger = logging.getLogger(__name__)

# Khoang cach toi thieu giua hai lan don. Xem `maybe_purge`.
GIAN_CACH_DON_S = 3600
# None = CHUA CHAY LAN NAO, khac han voi 0.0. `time.monotonic()` dem tu luc
# may khoi dong, nen tren mot container vua len no chi vai tram giay: lay 0.0
# lam moc "chua chay" thi phep tru ra so nho hon mot gio va lan don DAU TIEN
# bi bo qua. CI bat duoc dieu nay, may phat trien thi khong - may do da chay
# lien nhieu ngay.
_lan_don_gan_nhat: float | None = None


def _xoa_anh_neu_khong_ai_dung(db: Session, refs: set[str], kho) -> int:
    """Xoa tep anh cua nhung ma bam KHONG con ban quet nao tro toi.

    Phai goi SAU khi cac dong `scans` da bi xoa va `flush()`, khong thi phep
    dem van thay chinh ban quet vua xoa va khong tep nao duoc don.
    """
    da_xoa = 0
    for ref in refs:
        if not ref:
            continue
        con_dung = db.scalar(select(func.count()).select_from(Scan)
                             .where(Scan.image_ref == ref))
        if con_dung:
            continue
        # Kho tu nuot loi va ghi log: xoa duoc dong trong CSDL ma khong
        # xoa duoc anh thi VAN la da xoa du lieu, va mot tep bi khoa khong
        # duoc lam hong ca thao tac xoa.
        if kho.xoa(ref):
            da_xoa += 1
    return da_xoa


def delete_scan(db: Session, scan: Scan, kho) -> dict:
    """Xoa mot ban quet va anh goc cua no neu khong ai con dung."""
    ref = scan.image_ref
    db.delete(scan)
    db.flush()
    anh = _xoa_anh_neu_khong_ai_dung(db, {ref}, kho)
    db.commit()
    return {"scans": 1, "images": anh}


def delete_contact(db: Session, contact: Contact, kho) -> dict:
    """Xoa mot ho so: ban ghi, cac ban quet cua no, va anh goc.

    Email/dien thoai/dia chi/ho so mo rong di theo `ON DELETE CASCADE` da khai
    trong `models.py`, nen khong liet ke lai o day - liet ke lai la tao ra mot
    ban sao thu hai cua so do quan he, va ban sao do se lech.

    KHONG xoa `Organization`: doanh nghiep dung chung cho nhieu ho so va khong
    phai du lieu ca nhan cua ai.
    """
    scans = db.scalars(select(Scan).where(Scan.contact_id == contact.id)).all()
    refs = {s.image_ref for s in scans}
    so_ban_quet = len(scans)

    if scans:
        db.execute(delete(Scan).where(Scan.contact_id == contact.id))
    db.delete(contact)
    db.flush()
    anh = _xoa_anh_neu_khong_ai_dung(db, refs, kho)
    db.commit()
    return {"contacts": 1, "scans": so_ban_quet, "images": anh}


def purge_expired(db: Session, kho, days: int) -> dict:
    """Xoa ban quet cu hon `days` ngay. `days <= 0` la tat.

    SO SANH CHUOI, CO Y: `created_at` luu duoi dang chuoi ISO-8601 co mui gio,
    va `utcnow()` luon sinh ra gio UTC, nen thu tu chu cai CHINH LA thu tu
    thoi gian. Doi sang `datetime` de so se phai doc ca bang ra bo nho.
    """
    if days <= 0:
        return {"skipped": True, "scans": 0, "images": 0}

    moc = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    scans = db.scalars(select(Scan).where(Scan.created_at < moc)).all()
    if not scans:
        return {"skipped": False, "scans": 0, "images": 0}

    refs = {s.image_ref for s in scans}
    db.execute(delete(Scan).where(Scan.id.in_([s.id for s in scans])))
    db.flush()
    anh = _xoa_anh_neu_khong_ai_dung(db, refs, kho)
    db.commit()
    logger.info("don qua han: xoa %d ban quet, %d anh (qua %d ngay)",
                len(scans), anh, days)
    return {"skipped": False, "scans": len(scans), "images": anh}


def maybe_purge(config, session_factory) -> None:
    """Don qua han, nhieu nhat mot lan moi gio.

    VI SAO GAN VAO LUONG QUET chu khong dung bo hen gio: them mot bo hen gio
    la them mot tien trinh phai theo doi, phai tat dung cach khi dung app, va
    phai tu no chay dung trong ca ba cach chay (dev, Docker, test). Duong quet
    thi da co san va chay dung luc du lieu moi sinh ra - han luu tru chi co y
    nghia khi co du lieu chay qua.

    ponytail: khong don khi may nam khong. Mot container chay lien mot thang
    ma khong ai quet the se khong don gi - nhung no cung khong nhan them anh
    nao. Can chac chan hon thi goi `purge_expired` tu cron.
    """
    global _lan_don_gan_nhat
    if config.retention_days <= 0:
        return
    bay_gio = time.monotonic()
    if _lan_don_gan_nhat is not None and bay_gio - _lan_don_gan_nhat < GIAN_CACH_DON_S:
        return
    _lan_don_gan_nhat = bay_gio
    try:
        with session_factory() as db:
            purge_expired(db, kho_anh(config), config.retention_days)
    except Exception as exc:  # don dep hong khong duoc lam hong duong quet
        logger.warning("don qua han that bai: %s", exc)
