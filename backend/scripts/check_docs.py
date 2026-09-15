"""Doi chieu cac con so trong tai lieu voi ma nguon that.

VI SAO CO CONG CU NAY: trong ba ngay, so test ghi trong tai lieu phai sua bang
tay nam lan (313 -> 402 -> 435 -> 449 -> 460 -> 462). Moi lan deu bo sot it
nhat mot tep, va co lan mot bao cao ghi "331 test" trong khi that ra la 313 -
dung loai loi ma chinh bao cao do canh bao nguoi khac dung mac phai.

Sua bang tay khong the lam dung mai. Cong cu nay bien no thanh viec may lam.

    python backend/scripts/check_docs.py          # bao cao
    python backend/scripts/check_docs.py --fix    # sua luon

TRA MA THOAT 1 khi co so lech, de dung duoc trong CI.

VI SAO DEM "COLLECTED" CHU KHONG DEM "PASSED": so test chay qua phu thuoc vao
may - test can Tesseract se tu bo qua neu may chua cai, nen "461 passed" dung
o may nay va sai o may khac. So test THU THAP duoc thi khong doi. Mot con so
trong tai lieu ma doi theo may nguoi doc la mot con so vo dung.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

# Tai lieu DANG SONG - phai luon dung voi hien tai.
#
# Bao cao theo ngay va theo moc KHONG nam trong danh sach nay: chung la anh
# chup mot thoi diem. "116 test pass" trong bao cao Ngay 5 la su that cua ngay
# hom do; sua no thanh 462 se bien mot ban ghi lich su thanh mot loi noi doi.
LIVING_DOCS = [
    "README.md",
    "Document/README.md",
    "Document/2-ke-hoach/kien-truc-agentic.md",
    "Document/2-ke-hoach/roadmap.md",
    "Document/3-bao-cao/ngay-21-demo.md",
]

# Cac cach mot con so test duoc viet trong tai lieu. Nhom 1 la con so.
#
# CO Y KHONG BAT "N pass": so test CHAY QUA phu thuoc vao may - test can
# Tesseract se tu bo qua neu may chua cai. Sua "461 pass" thanh "462 pass"
# theo so thu thap la bien mot cau dung thanh cau sai.
#
# Chinh cong cu nay da mac loi do ngay lan chay dau: no doi
# "462 test - 461 pass, 1 tu bo qua" thanh "462 test - 462 pass, 1 tu bo qua",
# mot cau tu mau thuan. Chi kiem con so KHONG doi theo moi truong.
TEST_CLAIMS = [
    re.compile(r"(\d{3,4})\s+test\b"),
]
ENDPOINT_CLAIMS = [
    re.compile(r"(\d{1,3})\s+endpoint\b"),
]


def dem_test() -> int:
    """So test thu thap duoc. Khong CHAY test - chi thu thap, mat vai giay."""
    # KHONG dung -q: o che do rut gon pytest in so test cua tung TEP roi thoi,
    # khong in dong tong "N tests collected" ma ham nay can.
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only"],
        cwd=ROOT, capture_output=True, text=True,
    )
    found = re.search(r"(\d+)\s+tests? collected", run.stdout)
    if not found:
        raise SystemExit("Khong doc duoc so test tu pytest. Ket qua:\n"
                         + run.stdout[-800:] + run.stderr[-400:])
    return int(found.group(1))


def dem_endpoint() -> int:
    """So endpoint that.

    Phai di qua `original_router.routes`: FastAPI KHONG gop cac router duoc
    include vao `app.routes`, nen dem thang tren `app.routes` se ra 12 thay vi
    24 - dung loi da mac mot lan roi.
    """
    sys.path.insert(0, str(BACKEND))
    from app.main import app

    seen: set[tuple[str, str]] = set()

    def walk(routes):
        for route in routes:
            inner = getattr(route, "original_router", None)
            if inner is not None:
                walk(inner.routes)
                continue
            methods = getattr(route, "methods", None)
            path = str(getattr(route, "path", ""))
            if not methods or path.startswith(("/openapi", "/docs", "/redoc")):
                continue
            for method in methods:
                if method not in ("HEAD", "OPTIONS"):
                    seen.add((method, path))

    walk(app.routes)
    return len(seen)


def kiem_tra(that: dict[str, int], sua: bool) -> list[str]:
    loi: list[str] = []
    for ten in LIVING_DOCS:
        path = ROOT / ten
        if not path.is_file():
            loi.append(f"{ten}: khong tim thay tep")
            continue

        noi_dung = path.read_text(encoding="utf-8")
        goc = noi_dung

        for nhan, mau_list in (("test", TEST_CLAIMS),
                               ("endpoint", ENDPOINT_CLAIMS)):
            dung = that[nhan]
            for mau in mau_list:
                for khop in list(mau.finditer(noi_dung)):
                    so = int(khop.group(1))
                    if so == dung:
                        continue
                    dong = noi_dung[:khop.start()].count("\n") + 1
                    loi.append(f"{ten}:{dong}  ghi {so} {nhan}, "
                               f"thuc te {dung}")
                    if sua:
                        cu = khop.group(0)
                        moi = cu.replace(str(so), str(dung), 1)
                        noi_dung = noi_dung.replace(cu, moi, 1)

        if sua and noi_dung != goc:
            path.write_text(noi_dung, encoding="utf-8")
    return loi


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Doi chieu so lieu trong tai lieu voi ma nguon that")
    parser.add_argument("--fix", action="store_true",
                        help="Sua luon thay vi chi bao")
    args = parser.parse_args()

    that = {"test": dem_test(), "endpoint": dem_endpoint()}
    print(f"Thuc te: {that['test']} test thu thap duoc, "
          f"{that['endpoint']} endpoint")
    print(f"Doi chieu {len(LIVING_DOCS)} tai lieu dang song "
          f"(bao cao theo ngay/moc duoc mien - chung la anh chup lich su)")
    print("")

    loi = kiem_tra(that, args.fix)
    if not loi:
        print("Moi con so deu khop.")
        return 0

    for dong in loi:
        print(("  DA SUA  " if args.fix else "  LECH    ") + dong)
    print("")
    if args.fix:
        print(f"Da sua {len(loi)} cho.")
        return 0
    print(f"Co {len(loi)} cho lech. Chay lai voi --fix de sua.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
