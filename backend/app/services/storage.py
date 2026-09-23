"""Kho anh: mot giao dien, hai cach hien thuc (Ngay 25).

VI SAO TEP NAY TON TAI: truoc no, bon cho trong ma nguon deu tu biet anh la
mot TEP tren dia - `(image_dir / ref).read_bytes()`, `.unlink()`,
`FileResponse(path)`. Mot he thong chay nhieu ban sao khong co "dia chung"
nao nhu vay: ban sao nhan anh len khong phai ban sao duoc hoi xin anh do.

Gom lai mot cho thi doi cho luu la doi MOT dong cau hinh, chu khong phai di
tim bon cho da quen mat.

HAI CACH HIEN THUC:

    KhoTepLocal - thu muc tren dia. MAC DINH, va la cach du an chay tu Ngay
                  3. Dung tot cho mot may; khong dung duoc cho nhieu ban sao.
    KhoGCS      - Google Cloud Storage. Chi bat khi co bucket that.

VI SAO GCS CHU KHONG PHAI S3: du an da noi chuyen voi Google o hai cho khac
(Vision cho OCR, Gemini cho trich xuat), nen nguoi van hanh nhieu kha nang
da co san mot du an Google Cloud va mot service account. Dung AWS thi phai
lap them mot tai khoan, mot he quyen, va mot khoa nua.

GOI `google-cloud-storage` LA TUY CHON, KHONG BAT BUOC. No KHONG di kem
`google-cloud-vision` (vision chi keo `google-api-core` va `google-auth`),
nen may chay mac dinh `local` khong phai tai no ve. Chi khi doi sang `gcs`
moi can:

    pip install google-cloud-storage

Thieu goi ma van dat STORAGE_BACKEND=gcs thi `kho_anh()` ghi log muc error
va QUAY VE dia cuc bo - xem cuoi tep.

VE DUONG KY TAM THOI (presigned URL): khi dung GCS, anh duoc tra ve bang
mot duong dan co chu ky, het han sau vai phut, de trinh duyet tai thang tu
Google thay vi di qua backend. MOT DIEU PHAI NHO: duong do, mot khi da cap,
KHONG con qua phep kiem quyen nao nua - ai cam duoc no la tai duoc anh cho
den luc het han. Do la ly do:

  - duong chi duoc cap SAU khi `lay_ban_quet()` da xac nhan quyen doc
  - han mac dinh ngan (5 phut), du de trinh duyet tai xong, khong du de
    chuyen cho nguoi khac dung lai
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from app.services.images import PreparedImage

logger = logging.getLogger(__name__)

# Han cua duong ky tam thoi. Ngan co chu dich - xem ghi chu dau tep.
HAN_DUONG_KY_GIAY = 300


class KhoTepLocal:
    """Anh nam trong mot thu muc tren dia."""

    ten = "local"

    def __init__(self, thu_muc: Path) -> None:
        self.thu_muc = thu_muc

    def luu(self, anh: PreparedImage) -> str:
        """Ghi anh, tra ve ma tham chieu (SHA-256 cua noi dung).

        Ghi qua tep tam roi `os.replace`: chi mot tep HOAN CHINH moi xuat
        hien duoi ten that. Khong lam vay thi mot tien trinh khac doc dung
        luc dang ghi se nhan duoc nua tam anh, va no se la mot anh "hong"
        khong ly do.
        """
        self.thu_muc.mkdir(parents=True, exist_ok=True)
        dich = self.thu_muc / anh.digest
        if dich.is_file():
            return anh.digest                 # cung noi dung = cung tep
        with tempfile.NamedTemporaryFile(dir=self.thu_muc, prefix=".upload-",
                                         delete=False) as luong:
            tam = Path(luong.name)
            try:
                luong.write(anh.data)
            except BaseException:
                luong.close()
                tam.unlink(missing_ok=True)
                raise
        try:
            os.replace(tam, dich)
        finally:
            tam.unlink(missing_ok=True)
        return anh.digest

    def doc(self, ref: str) -> bytes | None:
        duong = self.thu_muc / ref
        try:
            return duong.read_bytes()
        except OSError:
            return None

    def xoa(self, ref: str) -> bool:
        try:
            (self.thu_muc / ref).unlink(missing_ok=True)
            return True
        except OSError as loi:
            # Xoa duoc dong trong CSDL ma khong xoa duoc tep thi VAN la da
            # xoa du lieu; tep mo coi se bi lan don sau nhat.
            logger.warning("khong xoa duoc anh %s: %s", ref, loi)
            return False

    def duong_ky(self, ref: str, mime: str) -> str | None:
        """Dia cuc bo khong co duong ky. Backend tu phuc vu bytes."""
        return None


class KhoGCS:
    """Anh nam trong mot bucket Google Cloud Storage."""

    ten = "gcs"

    def __init__(self, bucket: str, tien_to: str = "") -> None:
        # Nap MUON, khong nap o dau tep: goi nay la tuy chon, va mot `import`
        # o dau tep se lam ca backend khong khoi dong duoc tren may chi chay
        # kho cuc bo.
        from google.cloud import storage

        if not bucket:
            raise ValueError("STORAGE_BACKEND=gcs nhung GCS_BUCKET de trong")

        self.bucket_name = bucket
        self.tien_to = tien_to.strip("/")
        self._client = storage.Client()
        self._bucket = self._client.bucket(bucket)

    def _blob(self, ref: str):
        return self._bucket.blob(f"{self.tien_to}/{ref}" if self.tien_to else ref)

    def luu(self, anh: PreparedImage) -> str:
        blob = self._blob(anh.digest)
        # `if_generation_match=0` = chi ghi khi vat the CHUA ton tai. Ma tham
        # chieu la ma bam noi dung, nen vat the da co chac chan giong het -
        # ghi de chi ton tien duong truyen.
        if not blob.exists():
            blob.upload_from_string(anh.data, content_type=anh.mime,
                                    if_generation_match=0)
        return anh.digest

    def doc(self, ref: str) -> bytes | None:
        from google.api_core import exceptions

        try:
            return self._blob(ref).download_as_bytes()
        except exceptions.NotFound:
            return None

    def xoa(self, ref: str) -> bool:
        from google.api_core import exceptions

        try:
            self._blob(ref).delete()
            return True
        except exceptions.NotFound:
            return True                          # da khong con: coi nhu xong
        except exceptions.GoogleAPIError as loi:
            logger.warning("khong xoa duoc anh %s tren GCS: %s", ref, loi)
            return False

    def duong_ky(self, ref: str, mime: str) -> str | None:
        """Duong tai thang tu Google, het han sau `HAN_DUONG_KY_GIAY`.

        Tra `None` khi khong ky duoc. Truong hop hay gap nhat: chay bang
        Application Default Credentials (vi du tren Cloud Run) - khong co
        khoa rieng trong tay thi khong ky duoc, va luc do backend tu phuc vu
        bytes nhu cu. Cham hon, nhung chay dung.
        """
        from datetime import timedelta

        try:
            return self._blob(ref).generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=HAN_DUONG_KY_GIAY),
                method="GET",
                response_type=mime,
            )
        except Exception as loi:                  # thu vien nem nhieu kieu
            logger.info("khong ky duoc duong cho %s (%s); se tu phuc vu bytes",
                        ref, loi)
            return None


def kho_anh(config):
    """Chon kho theo cau hinh. Mac dinh la dia cuc bo.

    GCS hong luc khoi tao (sai ten bucket, thieu quyen) thi QUAY VE dia cuc
    bo va ghi log muc error, chu khong lam chet ca ung dung: mot cau hinh
    cloud sai khong duoc bien mot cong cu dang chay thanh mot cong cu khong
    khoi dong duoc. Trang thai that hien ra o `/api/health`.
    """
    if getattr(config, "storage_backend", "local") == "gcs":
        try:
            return KhoGCS(config.gcs_bucket, config.gcs_prefix)
        except ImportError:
            logger.error(
                "STORAGE_BACKEND=gcs nhung thieu goi. Chay: "
                "pip install google-cloud-storage. Tam thoi dung dia cuc bo.")
        except Exception as loi:
            logger.error("Khong dung duoc GCS (%s). Quay ve dia cuc bo.", loi)
    return KhoTepLocal(config.image_path)


def doc_anh(config, ref: str) -> bytes:
    """Doc anh cua mot ban quet, hoac nem `FileNotFoundError`.

    NEM chu khong tra `None`: hai noi goi (pipeline va agent_runner) von
    dung `Path.read_bytes()`, von nem `FileNotFoundError` khi thieu tep, va
    ca hai deu da co duong xu ly loi do. Tra `None` se bien mot anh thieu
    thanh `AttributeError` o mot dong khac han - mot kieu hong te hon vi no
    chi ra sai cho.
    """
    du_lieu = kho_anh(config).doc(ref)
    if du_lieu is None:
        raise FileNotFoundError(f"khong doc duoc anh {ref}")
    return du_lieu
