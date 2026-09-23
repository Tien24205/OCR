"""Ngay 25: kho anh - mot giao dien, hai cach hien thuc.

Bo test nay khong goi GCS that. No kiem hai thu ma mot lan goi that cung
khong kiem duoc nhanh hon: kho cuc bo co giu dung hop dong khong, va khi
cau hinh cloud hong thi ung dung co con chay khong.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import Settings
from app.services.images import PreparedImage
from app.services.storage import KhoTepLocal, doc_anh, kho_anh


@pytest.fixture()
def anh() -> PreparedImage:
    return PreparedImage(b"\x89PNG\r\n\x1a\n gia dinh la anh", "image/png")


@pytest.fixture()
def kho(tmp_path) -> KhoTepLocal:
    return KhoTepLocal(tmp_path / "anh")


def test_luu_roi_doc_lai_duoc(kho, anh):
    ref = kho.luu(anh)

    assert ref == anh.digest
    assert kho.doc(ref) == anh.data


def test_luu_hai_lan_cung_noi_dung_chi_ton_mot_tep(kho, anh):
    """Ma tham chieu la ma bam NOI DUNG, nen hai lan gui cung tam the phai
    dung chung mot tep - khong thi mot lo 10 anh giong nhau ton 10 cho."""
    kho.luu(anh)
    kho.luu(anh)

    assert len(list(kho.thu_muc.iterdir())) == 1


def test_doc_anh_khong_co_thi_tra_None(kho):
    assert kho.doc("a" * 64) is None


def test_xoa_anh_khong_co_van_coi_la_xong(kho):
    """Xoa mot thu da khong con phai thanh cong, khong phai loi.

    Duong xoa du lieu goi ham nay sau khi da xoa dong trong CSDL. Neu no bao
    loi khi tep da mat tu truoc, mot thao tac xoa hoan toan binh thuong se
    bao hong."""
    assert kho.xoa("a" * 64) is True


def test_kho_cuc_bo_khong_co_duong_ky(kho, anh):
    """Tra None, va do la cach `get_image` biet phai tu phuc vu bytes."""
    assert kho.duong_ky(kho.luu(anh), "image/png") is None


def test_ghi_dang_do_khong_de_lai_tep_mang_ten_that(kho, anh, monkeypatch):
    """Tep chi duoc xuat hien duoi ten that khi da ghi XONG.

    Khong vay thi mot tien trinh khac doc dung luc dang ghi se nhan duoc nua
    tam anh - va no se la mot anh "hong" khong ly do nao.
    """
    def vo_giua(*a, **k):
        raise OSError("dia day")

    monkeypatch.setattr("os.replace", vo_giua)
    with pytest.raises(OSError):
        kho.luu(anh)

    assert not (kho.thu_muc / anh.digest).exists()
    # Va khong bo lai rac: tep tam phai duoc don.
    assert list(kho.thu_muc.iterdir()) == []


def test_mac_dinh_la_dia_cuc_bo(tmp_path):
    config = Settings(_env_file=None, image_dir=tmp_path)

    assert kho_anh(config).ten == "local"


def test_cau_hinh_gcs_hong_thi_quay_ve_dia_cuc_bo(tmp_path, caplog):
    """Mot cau hinh cloud sai khong duoc bien mot cong cu dang chay thanh
    mot cong cu khong khoi dong duoc."""
    config = SimpleNamespace(storage_backend="gcs", gcs_bucket="",
                             gcs_prefix="", image_path=tmp_path)

    kho = kho_anh(config)

    assert kho.ten == "local"


def test_doc_anh_thieu_thi_nem_FileNotFoundError(tmp_path):
    """Hai noi goi (pipeline, agent_runner) von bat `FileNotFoundError`."""
    config = Settings(_env_file=None, image_dir=tmp_path)

    with pytest.raises(FileNotFoundError):
        doc_anh(config, "a" * 64)
