"""Nha cung cap OCR gia lap: doc lai phan hoi da luu tu dia.

Vi sao can: bo kiem thu KHONG duoc goi mang that. Vua ton tien, vua khien
test that bai vi ly do khong lien quan den ma nguon (mat mang, het quota).
Fixture duoc sinh boi `scripts/try_ocr.py` tu lan goi THAT o Ngay 2, nen du
lieu trong test van la du lieu thuc te chu khong phai bia ra.

Fixture duoc dat ten theo SHA-256 cua anh, nen cung mot anh luon cho cung
mot ket qua.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.ocr.base import OcrBlock, OcrError, OcrResult

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "ocr"


class MockOcrProvider:
    name = "mock"

    def __init__(self, fixture_dir: Path | None = None) -> None:
        self._dir = fixture_dir or FIXTURE_DIR

    def recognize(self, image: bytes, mime: str) -> OcrResult:
        digest = hashlib.sha256(image).hexdigest()
        path = self._dir / f"{digest}.json"
        if not path.is_file():
            raise OcrError(
                "FIXTURE_MISSING",
                f"Chua co fixture cho anh {digest[:12]}. Chay "
                f"`python backend/scripts/try_ocr.py <anh>` de sinh.",
            )

        data = json.loads(path.read_text(encoding="utf-8"))
        return OcrResult(
            raw_text=data["raw_text"],
            provider=f"mock:{data.get('provider', 'unknown')}",
            provider_version=data.get("provider_version", "fixture"),
            blocks=[
                OcrBlock(
                    text=b["text"],
                    bbox=tuple(b["bbox"]),
                    confidence=b.get("confidence"),
                    languages=tuple(b.get("languages", ())),
                )
                for b in data.get("blocks", [])
            ],
            detected_languages=data.get("detected_languages", []),
            payload=data.get("payload", {}),
            ms=0,
        )
