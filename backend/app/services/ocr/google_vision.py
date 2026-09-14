"""Nha cung cap OCR: Google Cloud Vision, feature DOCUMENT_TEXT_DETECTION.

Vi sao DOCUMENT_TEXT_DETECTION chu khong phai TEXT_DETECTION: feature nay
danh cho anh chu dac, tra ve cau truc trang/khoi/doan/tu kem toa do va ngon
ngu phat hien duoc cho tung phan. TEXT_DETECTION chi tra ve chu roi rac,
khong co cau truc de doi chieu.
"""

from __future__ import annotations

import time

from google.api_core import exceptions as gexc
from google.cloud import vision

from app.services.ocr.base import OcrBlock, OcrError, OcrResult

# Loi tam thoi: dang thu lai. Loi con lai (anh hong, sai quyen) thi khong.
_RETRYABLE = (
    gexc.ServiceUnavailable,
    gexc.DeadlineExceeded,
    gexc.TooManyRequests,
    gexc.InternalServerError,
)


def _bbox(vertices) -> tuple[int, int, int, int]:
    xs = [v.x for v in vertices] or [0]
    ys = [v.y for v in vertices] or [0]
    return (min(xs), min(ys), max(xs), max(ys))


def _paragraph_text(paragraph) -> str:
    """Ghep chu tu cau truc symbol cua Vision.

    Vision tra ve tung ky tu roi; `detected_break` cho biet sau ky tu do co
    khoang trang hay xuong dong. Phai ton trong dau ngat nay, neu khong dia
    chi tieng Nhat nhieu dong se bi dinh lien thanh mot chuoi.
    """
    break_type = vision.TextAnnotation.DetectedBreak.BreakType
    out: list[str] = []
    for word in paragraph.words:
        for symbol in word.symbols:
            out.append(symbol.text)
            brk = symbol.property.detected_break
            if brk.type_ in (break_type.SPACE, break_type.SURE_SPACE):
                out.append(" ")
            elif brk.type_ in (break_type.EOL_SURE_SPACE, break_type.LINE_BREAK):
                out.append("\n")
            elif brk.type_ == break_type.HYPHEN:
                out.append("-")
    return "".join(out).strip()


class GoogleVisionProvider:
    name = "google_vision"

    def __init__(self, language_hints: list[str], timeout_s: int = 20, credentials_path=None) -> None:
        self._hints = language_hints
        self._timeout = timeout_s
        try:
            self._client = (
                vision.ImageAnnotatorClient.from_service_account_file(str(credentials_path))
                if credentials_path else vision.ImageAnnotatorClient()
            )
        except Exception as exc:  # thieu credentials, sai duong dan JSON...
            # Co HAI cach xac thuc va thong bao phai neu ca hai. Nguoi dung
            # ADC ma chi duoc bao "kiem tra GOOGLE_APPLICATION_CREDENTIALS" se
            # di sai huong: ho khong can file nao ca.
            raise OcrError(
                "OCR_NOT_CONFIGURED",
                "Khong khoi tao duoc Vision client. Chon MOT trong hai cach:\n"
                "  (a) Dat GOOGLE_APPLICATION_CREDENTIALS tro toi file JSON "
                "service account (duong dan tuong doi tinh tu backend/), hoac\n"
                "  (b) De trong bien do va chay "
                "`gcloud auth application-default login`.",
            ) from exc

    def close(self) -> None:
        self._client.transport.close()

    def recognize(self, image: bytes, mime: str) -> OcrResult:
        request = vision.AnnotateImageRequest(
            image=vision.Image(content=image),
            features=[
                vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
            ],
            # Dat ca 'ja' va 'en' ngay tu dau. Khong doan ngon ngu truoc roi
            # moi goi - danh thiep song ngu la truong hop binh thuong.
            image_context=vision.ImageContext(language_hints=self._hints),
        )

        started = time.perf_counter()
        try:
            response = self._client.annotate_image(
                request=request, timeout=self._timeout, retry=None
            )
        except _RETRYABLE as exc:
            raise OcrError("OCR_UNAVAILABLE", "Vision tạm thời không phản hồi. Thử lại sau.", retryable=True) from exc
        except gexc.GoogleAPICallError as exc:
            raise OcrError("OCR_CALL_FAILED", "Vision từ chối lời gọi. Kiểm tra quyền và cấu hình API.") from exc
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        # Vision tra loi trong THAN phan hoi chu khong nem exception.
        if response.error.message:
            raise OcrError("OCR_REJECTED", "Vision không xử lý được ảnh này.")

        annotation = response.full_text_annotation
        blocks: list[OcrBlock] = []
        languages: list[str] = []

        for page in annotation.pages:
            for lang in page.property.detected_languages:
                if lang.language_code and lang.language_code not in languages:
                    languages.append(lang.language_code)
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    text = _paragraph_text(paragraph)
                    if not text:
                        continue
                    blocks.append(
                        OcrBlock(
                            text=text,
                            bbox=_bbox(paragraph.bounding_box.vertices),
                            confidence=paragraph.confidence or None,
                            languages=tuple(
                                lang.language_code
                                for lang in paragraph.property.detected_languages
                                if lang.language_code
                            ),
                        )
                    )

        return OcrResult(
            raw_text=annotation.text or "",
            provider=self.name,
            provider_version="v1",
            blocks=blocks,
            detected_languages=languages,
            payload={
                "block_count": len(blocks),
                "page_count": len(annotation.pages),
                "detected_languages": languages,
            },
            ms=elapsed_ms,
        )
