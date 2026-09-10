"""Lop truu tuong cho tang OCR.

Vi sao can lop nay: Ngay 2 la ngay rui ro cao nhat vi phu thuoc dich vu ngoai.
Neu ma nguon goi thang google.cloud.vision o khap noi thi khi phai doi nha
cung cap se phai sua ca ung dung. `OcrProvider` giu cho phan con lai cua he
thong chi biet mot kieu du lieu duy nhat: `OcrResult`.

Ham `recognize` la HAM DONG BO, khong phai async. SDK cua Google Vision la
dong bo; boc no trong `async def` ma khong day sang thread pool se chan
event loop cua FastAPI. Backend goi ham nay tu BackgroundTasks, va FastAPI
tu chay ham dong bo trong thread pool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class OcrError(Exception):
    """Loi tu tang OCR.

    `retryable` phan biet loi tam thoi (mang, 429, 5xx) voi loi vinh vien
    (anh hong, sai dinh dang). Chi thu lai loai thu nhat - thu lai anh hong
    chi ton them tien.
    """

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class OcrBlock:
    """Mot khoi van ban kem toa do tren anh.

    Toa do de danh cho Ngay 5: khi nguoi dung bam vao mot truong trong form,
    co the to sang dung vung tren anh de doi chieu.
    """

    text: str
    bbox: tuple[int, int, int, int]          # (x_min, y_min, x_max, y_max)
    confidence: float | None = None
    languages: tuple[str, ...] = ()


@dataclass(frozen=True)
class OcrResult:
    raw_text: str
    provider: str
    provider_version: str
    blocks: list[OcrBlock] = field(default_factory=list)
    detected_languages: list[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)
    ms: int = 0


class OcrProvider(Protocol):
    name: str

    def recognize(self, image: bytes, mime: str) -> OcrResult: ...
