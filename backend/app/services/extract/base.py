"""Schema du lieu trich xuat tu danh thiep.

Schema nay dong THOI ba vai tro:
  1. `response_schema` ep Gemini tra ve dung cau truc.
  2. Lop validate dau ra truoc khi cham vao du lieu ung dung.
  3. Kieu du lieu chung cho ca bo trich xuat regex (khong can mang).

VI SAO MOI TRUONG DEU LA DANH SACH, khong dung `X | None`:

  a) Ve nghiep vu: danh thiep Nhat thuong in ten va ten cong ty bang HAI he
     chu (Kanji + romaji). Ca hai deu la gia tri that tren the, khong phai
     mot dung mot sai. Dac ta yeu cau `companyNames[]` chinh vi ly do nay.
  b) Ve ky thuat: JSON Schema cua Gemini xu ly danh sach on dinh hon kieu
     nullable. Tranh Optional la tranh mot loai loi kho chan doan.

VI SAO CO `source_text`: bat model chi ra doan chu NGUYEN VAN tren the ma no
lay gia tri ra. Doan nay se duoc doi chieu voi `raw_text` o buoc grounding.
Model bia du lieu thi cung phai bia ca `source_text`, va buoc doi chieu se
phat hien ngay.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class ExtractedValue(BaseModel):
    value: str = Field(description="Gia tri doc duoc, nguyen ban.")
    source_text: str = Field(
        default="",
        description="Doan chu nguyen van tren the chua gia tri nay.",
    )


class PhoneValue(BaseModel):
    value: str = Field(description="So dien thoai, chep y nguyen nhu tren the.")
    source_text: str = Field(default="")
    # Dung chuoi rong thay cho None de schema khong co kieu nullable.
    label: str = Field(default="", description="tel, mobile, hoac fax.")
    extension: str = Field(default="", description="So may le neu the co ghi.")


class CardExtraction(BaseModel):
    full_names: list[ExtractedValue] = Field(
        default_factory=list,
        description="Ho ten. Co the co hai muc neu the in ca ban dia va Latin.",
    )
    company_names: list[ExtractedValue] = Field(default_factory=list)
    job_titles: list[ExtractedValue] = Field(default_factory=list)
    departments: list[ExtractedValue] = Field(default_factory=list)
    emails: list[ExtractedValue] = Field(default_factory=list)
    phones: list[PhoneValue] = Field(default_factory=list)
    websites: list[ExtractedValue] = Field(default_factory=list)
    addresses: list[ExtractedValue] = Field(default_factory=list)
    card_language: str = Field(
        default="",
        description="en, ja, ko, zh, mixed, han (chu Han chua ro) hoac other.")


class ExtractionError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class FieldExtractor(Protocol):
    name: str

    def extract(self, image: bytes, mime: str, raw_text: str) -> CardExtraction: ...
