"""Mo hinh du lieu SQLAlchemy 2.0.

BA QUY TAC BAT BIEN (xem Document/2-ke-hoach/trien-khai-chi-tiet.md muc 3):

1. `Scan.raw_text` va `Scan.extraction_json` LA BAT BIEN. Nguoi dung sua gi
   thi sua o Contact/ContactEmail/..., ket qua goc cua may phai con nguyen
   de Ngay 9 do duoc chat luong "truoc khi sua tay".

2. So dien thoai LUON la chuoi. `value_raw` giu "+81 3-1234-5678" nguyen ban;
   `value_digits` chi dung de so khop trung lap.

3. Cac cot `*_norm` CHI dung de tim kiem va doi sanh, KHONG BAO GIO hien thi.
   Nguoi dung luon thay `*_raw` / `*_original`.
"""

from __future__ import annotations

import unicodedata
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# --------------------------------------------------------------------------
# Tien ich
# --------------------------------------------------------------------------

def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> str:
    """Moc thoi gian ISO-8601 co mui gio, luu duoi dang TEXT."""
    return datetime.now(timezone.utc).isoformat()


def norm_key(value: str | None) -> str:
    """Chuan hoa chuoi de SO KHOP (khong bao gio de hien thi).

    NFKC quan trong voi tieng Nhat: no dua ky tu full-width ve half-width,
    nen "ＴＥＬ：０３" khop duoc voi "TEL:03".
    """
    if not value:
        return ""
    s = unicodedata.normalize("NFKC", value).casefold()
    return "".join(s.split())


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------
# Nguoi dung (Ngay 23)
# --------------------------------------------------------------------------

class User(Base):
    """Tai khoan nguoi dung.

    `email_norm` ton tai vi cung mot dia chi viet hoa khac nhau van la MOT
    nguoi: "An@Cty.vn" va "an@cty.vn" phai dung chung tai khoan, khong duoc
    dang ky thanh hai. Rang buoc duy nhat dat tren cot da chuan hoa chu khong
    tren `email` - dat tren `email` thi hai ban ghi tren deu lot qua.

    `email` van giu nguyen ban de hien thi va de gui thu: nguoi ta viet hoa
    ten minh trong dia chi la co chu y.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_norm: Mapped[str] = mapped_column(
        String(320), nullable=False, unique=True, index=True
    )
    display_name: Mapped[str | None] = mapped_column(Text)
    # Chuoi tu mo ta: "scrypt$n$r$p$salt_hex$hash_hex". Xem auth.py.
    # KHONG BAO GIO chua mat khau goc, va khong bao gio ra khoi backend.
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow, nullable=False)
    last_login_at: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (
        CheckConstraint("role IN ('admin','user')", name="ck_user_role"),
    )


# --------------------------------------------------------------------------
# Doanh nghiep
# --------------------------------------------------------------------------

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name_original: Mapped[str] = mapped_column(Text, nullable=False)
    # name_latin CHI dien khi ten Latin CO THAT tren the. Khong tu phien am.
    name_latin: Mapped[str | None] = mapped_column(Text)
    name_norm: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    website: Mapped[str | None] = mapped_column(Text)
    website_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow, nullable=False)
    updated_at: Mapped[str] = mapped_column(
        String(40), default=utcnow, onupdate=utcnow, nullable=False
    )

    contacts: Mapped[list[Contact]] = relationship(back_populates="organization")
    enrichments: Mapped[list[Enrichment]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    addresses: Mapped[list[Address]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


# --------------------------------------------------------------------------
# Nguoi lien he
# --------------------------------------------------------------------------

class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), index=True
    )

    # GIA TRI CHINH. Luon giu nguyen ban, ke ca "山田 太郎".
    full_name_original: Mapped[str] = mapped_column(Text, nullable=False)
    # given/family CHI dien khi co can cu ro rang. Khong ap thu tu ten
    # tieng Anh cho ten Nhat.
    given_name: Mapped[str | None] = mapped_column(Text)
    family_name: Mapped[str | None] = mapped_column(Text)
    name_norm: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    job_titles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    departments: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    # NULL = khong co chu: ban ghi tao truoc Ngay 23, hoac tao bang khoa API
    # (he thong tich hop, khong phai mot nguoi). ON DELETE SET NULL chu khong
    # CASCADE: xoa mot nhan vien khong duoc keo theo ho so doi tac cua cong ty.
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    review_status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    reviewed_at: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow, nullable=False)
    updated_at: Mapped[str] = mapped_column(
        String(40), default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("review_status IN ('draft','reviewed')", name="ck_contact_review"),
    )

    organization: Mapped[Organization | None] = relationship(back_populates="contacts")
    emails: Mapped[list[ContactEmail]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )
    phones: Mapped[list[ContactPhone]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )
    addresses: Mapped[list[Address]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )


# --------------------------------------------------------------------------
# Da gia tri: tach bang rieng de tim kiem va chong trung
# --------------------------------------------------------------------------

SOURCE_VALUES = "('ocr','user','enrichment')"


class ContactEmail(Base):
    __tablename__ = "contact_emails"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    contact_id: Mapped[str] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value_raw: Mapped[str] = mapped_column(Text, nullable=False)
    value_norm: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        CheckConstraint(f"source IN {SOURCE_VALUES}", name="ck_email_source"),
    )

    contact: Mapped[Contact] = relationship(back_populates="emails")


class ContactPhone(Base):
    __tablename__ = "contact_phones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    contact_id: Mapped[str] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # LUON la TEXT: co dau +, so 0 dau dong, dau cach, dau gach.
    value_raw: Mapped[str] = mapped_column(Text, nullable=False)
    value_digits: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    extension: Mapped[str | None] = mapped_column(String(16))
    label: Mapped[str | None] = mapped_column(String(16))  # tel | mobile | fax
    source: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        CheckConstraint(f"source IN {SOURCE_VALUES}", name="ck_phone_source"),
        CheckConstraint(
            "label IS NULL OR label IN ('tel','mobile','fax')", name="ck_phone_label"
        ),
    )

    contact: Mapped[Contact] = relationship(back_populates="phones")


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    contact_id: Mapped[str | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    # Giu nguyen ban, ke ca ky tu 〒 va xuong dong.
    value_raw: Mapped[str] = mapped_column(Text, nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(32))
    country_hint: Mapped[str | None] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "contact_id IS NOT NULL OR organization_id IS NOT NULL",
            name="ck_address_owner",
        ),
        CheckConstraint(f"source IN {SOURCE_VALUES}", name="ck_address_source"),
    )

    contact: Mapped[Contact | None] = relationship(back_populates="addresses")
    organization: Mapped[Organization | None] = relationship(back_populates="addresses")


# --------------------------------------------------------------------------
# Ban quet: BANG CHUNG GOC, khong bao gio bi ghi de boi chinh sua cua nguoi dung
# --------------------------------------------------------------------------

SCAN_STATUSES = ("pending", "processing", "ocr_done", "failed", "committed")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)

    image_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    image_mime: Mapped[str] = mapped_column(String(32), nullable=False)
    image_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Xem ghi chu o Contact.owner_id.
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    ocr_provider: Mapped[str | None] = mapped_column(String(32))
    ocr_version: Mapped[str | None] = mapped_column(String(32))
    raw_text: Mapped[str | None] = mapped_column(Text)          # BAT BIEN
    ocr_payload: Mapped[dict | None] = mapped_column(JSON)
    detected_langs: Mapped[list[str] | None] = mapped_column(JSON)

    extractor: Mapped[str | None] = mapped_column(String(32))
    extraction_json: Mapped[dict | None] = mapped_column(JSON)  # BAT BIEN
    grounding_json: Mapped[dict | None] = mapped_column(JSON)

    contact_id: Mapped[str | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )

    ms_ocr: Mapped[int | None] = mapped_column(Integer)
    ms_extract: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','ocr_done','failed','committed')",
            name="ck_scan_status",
        ),
    )


# --------------------------------------------------------------------------
# Thong tin bo sung: MOI DONG LA MOT KHANG DINH CO NGUON
# --------------------------------------------------------------------------

class Enrichment(Base):
    __tablename__ = "enrichments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attribute: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str | None] = mapped_column(Text)      # NULL khi status='not_found'
    source_url: Mapped[str | None] = mapped_column(Text)
    source_title: Mapped[str | None] = mapped_column(Text)
    # Doan trich NGUYEN VAN tu trang nguon. Validator o Ngay 6 bat buoc
    # doan nay phai la chuoi con cua trang da tai, neu khong thi loai bo.
    evidence_snippet: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewed: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('verified','unverified','conflicting','not_found')",
            name="ck_enrichment_status",
        ),
        Index("ix_enrich_org_attr", "organization_id", "attribute"),
    )

    organization: Mapped[Organization] = relationship(back_populates="enrichments")


# --------------------------------------------------------------------------
# Chong gui trung (FR-11)
# --------------------------------------------------------------------------

class EnrichmentJob(Base):
    """A research target for one saved scan revision, before Day 7 contact creation."""
    __tablename__ = "enrichment_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(64))
    result_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    decisions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    pages: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String(40))
    __table_args__ = (
        UniqueConstraint("scan_id", "draft_revision", name="uq_enrich_scan_revision"),
        CheckConstraint("status IN ('pending','processing','done')", name="ck_enrich_job_status"),
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow, nullable=False)


class ContactProfile(Base):
    """All reviewed values, including bilingual aliases, with optimistic versioning.

    Additive table: existing databases need no destructive column migration.
    Contact and its child tables are searchable projections, updated atomically.
    """
    __tablename__ = "contact_profiles"
    contact_id: Mapped[str] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True)
    draft: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    names_norm: Mapped[str] = mapped_column(Text, nullable=False)
    companies_norm: Mapped[str] = mapped_column(Text, nullable=False)
