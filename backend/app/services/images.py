"""Day 3: validate image bytes, apply EXIF orientation, store by content hash."""

from __future__ import annotations

import hashlib
import os
import tempfile
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_EDGE = 6000
MIMES = {"JPEG": "image/jpeg", "PNG": "image/png"}


class ImageInputError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    mime: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def prepare_image(data: bytes, max_bytes: int) -> PreparedImage:
    if len(data) > max_bytes:
        raise ImageInputError("IMAGE_TOO_LARGE", "Ảnh vượt quá dung lượng cho phép.", 413)
    if not data:
        raise ImageInputError("INVALID_IMAGE", "Tệp ảnh rỗng.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                fmt = source.format
                if fmt not in MIMES:
                    raise ImageInputError("UNSUPPORTED_IMAGE", "Chỉ nhận ảnh JPEG hoặc PNG.")
                if max(source.size) > MAX_EDGE:
                    raise ImageInputError("IMAGE_DIMENSIONS", "Cạnh ảnh không được vượt quá 6000 pixel.")
                if getattr(source, "n_frames", 1) != 1:
                    raise ImageInputError("UNSUPPORTED_IMAGE", "Vui lòng gửi ảnh tĩnh một khung hình.")
                source.verify()

            # verify() checks the file; reopen and fully decode to catch truncation.
            with Image.open(BytesIO(data)) as source:
                source.load()
                orientation = source.getexif().get(274, 1)
                if orientation in range(2, 9):
                    upright = ImageOps.exif_transpose(source)
                    out = BytesIO()
                    options = {"quality": 95, "subsampling": 0} if fmt == "JPEG" else {}
                    upright.save(out, format=fmt, **options)
                    data = out.getvalue()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageInputError("IMAGE_DIMENSIONS", "Kích thước ảnh quá lớn.") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise ImageInputError("INVALID_IMAGE", "Tệp không phải ảnh hợp lệ hoặc đã bị hỏng.") from exc

    # The stored image is also the future OCR input; keep the same size limit.
    if len(data) > max_bytes:
        raise ImageInputError("IMAGE_TOO_LARGE", "Ảnh sau khi xoay vượt quá dung lượng cho phép.", 413)
    return PreparedImage(data, MIMES[fmt])


def store_image(image: PreparedImage, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / image.digest
    if target.is_file():
        return target
    # Publish only a complete file, including when requests share the same hash.
    with tempfile.NamedTemporaryFile(dir=directory, prefix=".upload-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(image.data)
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target
