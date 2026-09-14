"""Phan biet hai loai loi 429 cua Gemini.

VI SAO CAN: bac mien phi cua gemini-3.5-flash chi cho 20 luot MOI NGAY. Lan
chay thu duong do dau tien coi moi 429 la "thu lai duoc", nen no thu lai 3 lan
cho tung the - tieu 60 luot goi vao han muc 20 va khong thu duoc ket qua nao.

Hai loai 429 doi hoi hai cach xu ly nguoc nhau:
  - Goi qua nhanh trong mot phut -> cho vai giay la qua, NEN thu lai.
  - Het han muc ca ngay          -> cho bao lau cung khong qua, KHONG duoc
                                    thu lai, va nen dung han lan chay.

Cac dict duoi day chep tu phan hoi THAT cua Google ngay 14/09/2026.
"""

from __future__ import annotations

from google.genai import errors

from app.services.extract.gemini import _quota_het_trong_ngay


def loi(details) -> errors.APIError:
    """Dung APIError that cua SDK, khong dung doi tuong gia.

    Neu Google doi cau truc, test nay se do - dung y muon.
    """
    return errors.APIError(429, {"error": {
        "code": 429, "status": "RESOURCE_EXHAUSTED",
        "message": "You exceeded your current quota",
        "details": details,
    }})


HET_NGAY = [
    {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
     "violations": [{
         "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
         "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
         "quotaDimensions": {"location": "global", "model": "gemini-3.5-flash"},
         "quotaValue": "20"}]},
    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "17s"},
]

QUA_NHANH = [
    {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
     "violations": [{
         "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
         "quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
         "quotaValue": "15"}]},
    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "3s"},
]


def test_nhan_ra_het_han_muc_ca_ngay():
    assert _quota_het_trong_ngay(loi(HET_NGAY)) is True


def test_khong_nham_gioi_han_moi_phut_thanh_het_ngay():
    """Nham huong nay se lam dung ca lan chay khi that ra chi can cho 3 giay."""
    assert _quota_het_trong_ngay(loi(QUA_NHANH)) is False


def test_khong_no_khi_thieu_phan_chi_tiet():
    """Loi 429 khong kem QuotaFailure van phai xu ly duoc."""
    assert _quota_het_trong_ngay(loi([])) is False
    assert _quota_het_trong_ngay(errors.APIError(429, {"error": {}})) is False


def test_doc_phong_thu_khi_cau_truc_la():
    """Google doi cau truc thi coi nhu loi tam thoi, khong duoc nem exception.

    Doan sai theo huong nay chi ton them vai lan thu lai. Doan sai theo huong
    nguoc lai se dung ca lan chay khi that ra khong can dung.
    """
    assert _quota_het_trong_ngay(errors.APIError(429, {"error": {
        "details": "chuoi chu khong phai danh sach"}})) is False
    assert _quota_het_trong_ngay(errors.APIError(429, {})) is False


def test_loi_het_quota_KHONG_duoc_danh_dau_thu_lai_duoc():
    """Day la ca lop bao ve: thu lai khi het quota chi dot not phan con lai."""
    from app.services.extract.base import ExtractionError

    # Dung dung duong di ma gemini.py se chay: bat APIError roi doi thanh
    # ExtractionError voi ma rieng.
    exc = loi(HET_NGAY)
    assert _quota_het_trong_ngay(exc)

    chuyen = ExtractionError(
        "EXTRACT_QUOTA_EXCEEDED", "het han muc trong ngay", retryable=False)
    assert chuyen.retryable is False
    assert chuyen.code == "EXTRACT_QUOTA_EXCEEDED"
