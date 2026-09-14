"""Editable scan drafts are separate from OCR/extraction/grounding evidence."""
from copy import deepcopy
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.services.normalize import FIELDS, normalize_draft, normalize_item


class DraftRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default="", max_length=80)
    value: str = Field(max_length=4096)
    label: Literal["", "tel", "fax", "mobile"] = ""
    extension: str = Field(default="", max_length=32)


Rows = Annotated[list[DraftRow], Field(max_length=100)]


class DraftFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_names: Rows
    company_names: Rows
    job_titles: Rows
    departments: Rows
    emails: Rows
    phones: Rows
    websites: Rows
    addresses: Rows


class DraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    fields: DraftFields


def current_draft(grounding: dict) -> dict | None:
    if "reviewed_draft" in grounding:
        return deepcopy(grounding["reviewed_draft"])
    if "agent_selected_draft" in grounding:
        return with_confidence(deepcopy(grounding["agent_selected_draft"]),
                               grounding)
    if "fields" in grounding:
        # Read older Day 4 scans with the current rules without mutating evidence.
        return with_confidence(normalize_draft(grounding), grounding)
    return None


def with_confidence(draft: dict, grounding: dict) -> dict:
    """Gan diem tin cay da luu vao tung dong cua ban nhap.

    VI SAO KHONG DOC THANG `grounding["draft"]`: ban nhap da luu co the loi
    thoi so voi `grounding["fields"]` - `fields` moi la nguon su that. Vi vay
    van dung lai ban nhap tu `fields`, roi gan diem vao sau.

    VI SAO DOI CHIEU THEO GIA TRI CHU KHONG THEO VI TRI: neu so luong dong
    thay doi giua hai lan, doi chieu theo chi so se gan nham diem cua dong nay
    sang dong khac - sai ma khong he bao loi.
    """
    scores = (grounding.get("confidence") or {}).get("field_scores") or {}
    for field, items in (draft.get("fields") or {}).items():
        saved = {
            entry["value"]: entry
            for entry in (scores.get(field) or [])
            if isinstance(entry, dict) and entry.get("value")
        }
        for item in items:
            entry = saved.get(item.get("value"))
            if entry and isinstance(entry.get("score"), (int, float)):
                item["confidence_score"] = entry["score"]
                item["confidence_reasons"] = entry.get("reasons") or []
    return draft


def apply_edit(current: dict, fields: DraftFields) -> dict:
    edited = deepcopy(current)
    for field in FIELDS:
        before = {item["id"]: item for item in current["fields"][field]}
        seen = set()
        edited["fields"][field] = []
        for row in getattr(fields, field):
            if row.id and (row.id not in before or row.id in seen):
                raise ValueError("Dòng dữ liệu không hợp lệ hoặc bị lặp. Tải lại bản nháp.")
            seen.add(row.id)
            if not row.value.strip():
                continue
            old = before.get(row.id)
            same = old is not None and row.value == old["value"]
            if field == "phones" and old:
                same = same and row.label == old.get("label", "") and row.extension == old.get("extension", "")
            if same:
                edited["fields"][field].append(deepcopy(old))
            else:
                item = {"id": row.id or str(uuid4()), "value": row.value, "value_raw": row.value,
                        "source": "user", "source_text": "", "needs_review": False,
                        "grounding_verdict": "user"}
                if field == "phones":
                    item.update(label=row.label, extension=row.extension)
                edited["fields"][field].append(normalize_item(field, item))
    return edited
