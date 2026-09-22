"""Dua anh chup that vao dung cho trong `datasets/`, va chan truoc nhung loi
khien so do tro nen vo nghia.

Chay:

    python backend/scripts/import_photos.py --split dev --lang ja --from <thu muc>
    # in ke hoach va cac canh bao; them --apply moi thuc su chep

VI SAO CAN (chuyen da xay ra 22/09): 18 tam anh dau tien gui vao
`datasets/print/` deu hong theo hai cach ma mat thuong khong thay:

  1. Chung la the cua MOT BO KHAC - `Marcus Feld / Halbrook Logistics`,
     `Priya Raman / Corvid Analytics`. Khong ten nao trong so do co trong
     `labels.jsonl`. Do chat luong tren chung la do may doc dung hay sai so
     voi mot dap an KHONG PHAI cua no.
  2. Chung chup ca TRANG CHUA CAT, nen mot tam co chu cua hai ba the. Ca duong
     ong duoc viet theo giao uoc "mot anh, mot the, mot mat", va grounding thi
     chap nhan moi thu co bang chung trong van ban OCR - ke ca dong cua the
     ben canh.

Khong co cong kiem nao bat duoc hai loi do; chung chi lo ra khi doc bao cao va
thay so vo ly. Cac phep kiem o day chay trong vai giay va tra ma thoat 1.

PHEP KIEM DOI CHIEU CAN RapidOCR (`pip install rapidocr onnxruntime`). Khong
co thi script van chay, chi bo qua muc do - va noi ro la da bo qua, chu khong
im lang tra ve "khong thay loi nao".
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "datasets"
LABELS = DATASETS / "labels.jsonl"
SUFFIXES = {".jpg", ".jpeg", ".png"}

# Duoi hai nguong nay thi chu tren the be hon tam anh 1000px roi - loi cua may
# anh chu khong phai loi cua OCR, va no keo so do xuong ma khong noi len gi.
MIN_CANH = 1600
# Do lech chuan cua anh bien - mot thuoc do do net tho nhung du de tach "mo
# han" khoi "chap nhan duoc". Do tren bo anh 22/09: tam mo nhat 13.7, net
# nhat 49.7.
MIN_NET = 12.0

# Ma the nam ngoai vien the, nen the CAT DUNG thi ma bi cat mat. Con nhin thay
# ma nghia la con dinh le trang hoac con ca the ben canh trong khung hinh.
MA_THE = re.compile(r"(?i)\b(?:en|ja|ko|zh)(?:-[de])?-\d{2}\b")


def thoi_diem_chup(path: Path) -> float:
    """Giay EXIF luc bam may, khong co thi lay thoi diem sua file.

    VI SAO THEO THOI GIAN: nguoi chup di lan luot tu the 01 den the 10, nen
    thu tu bam may CHINH LA thu tu nhan. Ten file cua may anh
    (`IMG_20260922_090257.jpg`) sap xep theo chuoi cung ra dung thu tu do,
    nhung chi dung khi ca lo chup trong mot ngay - EXIF thi luon dung.
    """
    try:
        with Image.open(path) as im:
            exif = im.getexif()
        # 36867 = DateTimeOriginal, 306 = DateTime.
        for tag in (36867, 306):
            gia_tri = exif.get(tag)
            if gia_tri:
                ngay, gio = str(gia_tri).split(" ")
                y, m, d = (int(x) for x in ngay.split(":"))
                hh, mm, ss = (int(x) for x in gio.split(":"))
                return ((y * 372 + m * 31 + d) * 24 + hh) * 3600 + mm * 60 + ss
    except (OSError, ValueError):
        pass
    return path.stat().st_mtime


def do_anh(path: Path) -> tuple[int, int, float]:
    with Image.open(path) as im:
        w, h = im.size
        xam = im.convert("L").resize((w // 4 or 1, h // 4 or 1))
    net = ImageStat.Stat(xam.filter(ImageFilter.FIND_EDGES)).stddev[0]
    return w, h, net


def nhan_cua(split: str, lang: str) -> list[dict]:
    rows = [json.loads(line) for line in LABELS.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    tien_to = f"{split}/{lang}/"
    return sorted((r for r in rows if r["image"].startswith(tien_to)),
                  key=lambda r: r["image"])


def _gon(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def doc_the(path: Path):
    """Van ban OCR cua mot tam, hoac None neu chua cai RapidOCR."""
    try:
        from rapidocr import RapidOCR
    except ImportError:
        return None
    global _ocr
    try:
        _ocr
    except NameError:
        _ocr = RapidOCR()
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((1600, 1600))
        ket_qua = _ocr(im)
    return " ".join(ket_qua.txts or ())


def kiem_mot_tam(path: Path, nhan: dict, doi_chieu: bool) -> tuple[list[str], list[str]]:
    loi: list[str] = []
    canh_bao: list[str] = []

    w, h, net = do_anh(path)
    if min(w, h) < MIN_CANH:
        loi.append(f"anh {w}x{h} - canh ngan hon {MIN_CANH}px, chu se qua nho")
    if net < MIN_NET:
        canh_bao.append(f"do net {net:.1f} - mo, chup lai neu duoc")

    if not doi_chieu:
        return loi, canh_bao

    text = doc_the(path)
    if text is None:
        return loi, canh_bao

    gon = _gon(text)
    ten = _gon(nhan.get("full_name") or "")
    cong_ty = _gon(nhan.get("company_name") or "")
    if not ((ten and ten in gon) or (cong_ty and cong_ty in gon)):
        loi.append(f"khong thay '{nhan.get('full_name')}' hay "
                   f"'{nhan.get('company_name')}' trong anh")
    if MA_THE.search(text):
        loi.append(f"con nhin thay ma the ({MA_THE.search(text).group()}) - "
                   f"day la trang chua cat, khong phai mot the roi")
    return loi, canh_bao


def main() -> int:
    p = argparse.ArgumentParser(description="Dua anh chup that vao datasets/")
    p.add_argument("--split", required=True, choices=["dev", "eval"])
    p.add_argument("--lang", required=True, choices=["en", "ja", "ko", "zh"])
    p.add_argument("--from", dest="nguon", required=True, type=Path,
                   help="thu muc chua anh vua chup, theo dung thu tu the 01..10")
    p.add_argument("--apply", action="store_true",
                   help="thuc su chep; khong co thi chi in ke hoach")
    p.add_argument("--bo-doi-chieu", action="store_true",
                   help="bo phep doi chieu noi dung the (nhanh hon, mu hon)")
    args = p.parse_args()

    nguon = args.nguon if args.nguon.is_absolute() else Path.cwd() / args.nguon
    if not nguon.is_dir():
        print(f"Khong tim thay thu muc {nguon}")
        return 1

    anh = sorted((f for f in nguon.iterdir() if f.suffix.lower() in SUFFIXES),
                 key=thoi_diem_chup)
    nhan = nhan_cua(args.split, args.lang)
    if not nhan:
        print(f"labels.jsonl khong co nhan nao cho {args.split}/{args.lang}")
        return 1

    print(f"{len(anh)} anh trong {nguon}")
    print(f"{len(nhan)} nhan cho {args.split}/{args.lang}\n")
    if len(anh) != len(nhan):
        print(f"LECH SO LUONG: {len(anh)} anh / {len(nhan)} nhan. Moi the mot "
              f"anh, chup dung thu tu the 01 den the {len(nhan):02d}.")
        return 1

    doi_chieu = not args.bo_doi_chieu and doc_the(anh[0]) is not None
    if not doi_chieu and not args.bo_doi_chieu:
        print("(!) Chua cai RapidOCR nen BO QUA phep doi chieu noi dung the.\n"
              "    Cai bang: pip install rapidocr onnxruntime\n")

    tong_loi = 0
    ke_hoach: list[tuple[Path, Path]] = []
    for i, (f, row) in enumerate(zip(anh, nhan), start=1):
        dich = DATASETS / args.split / args.lang / f"{i:03d}.jpg"
        loi, canh_bao = kiem_mot_tam(f, row, doi_chieu)
        tong_loi += len(loi)
        dau = "LOI " if loi else ("... " if canh_bao else "OK  ")
        print(f"{dau}{f.name} -> {dich.relative_to(ROOT)}  ({row.get('full_name')})")
        for m in loi:
            print(f"      x {m}")
        for m in canh_bao:
            print(f"      - {m}")
        ke_hoach.append((f, dich))

    if tong_loi:
        print(f"\n{tong_loi} loi. Khong chep gi ca - sua roi chay lai.")
        return 1

    if not args.apply:
        print("\nKhong loi nao. Chay lai kem --apply de chep.")
        return 0

    for f, dich in ke_hoach:
        dich.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dich)
    print(f"\nDa chep {len(ke_hoach)} anh vao {DATASETS / args.split / args.lang}")
    print("Buoc tiep: python backend/scripts/check_labels.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
