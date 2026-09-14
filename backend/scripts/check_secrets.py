"""Quet toan bo file duoc Git theo doi de tim khoa bi ro ri - Ngay 8, muc 10.

VI SAO CAN CONG CU THAY VI MOT LENH grep

Ke hoach ghi `grep -ri "AIza|private_key|BEGIN PRIVATE"`. Lenh do co hai van de:

  1. No bao dong gia o chinh tai lieu. File ke hoach nay CHUA chuoi "AIza" de
     mo ta phep kiem tra, nen grep se luon tim thay va nguoi doc se quen dan
     voi viec bo qua canh bao - den khi co khoa that thi cung bo qua not.

  2. No chi bat duoc ba dang. Khoa Gemini, service account JSON va token
     Bearer co hinh dang khac nhau.

Cong cu nay khop theo HINH DANG cua khoa chu khong theo tu khoa, nen nhac
den "AIza" trong tai lieu khong bi bao dong, con `AIzaSy...` du 39 ky tu thi bi.

CACH DUNG

    python backend/scripts/check_secrets.py          # quet file Git theo doi
    python backend/scripts/check_secrets.py --all    # quet ca file chua theo doi

Tra ve ma thoat 1 neu tim thay bat ky thu gi, de dung duoc trong CI.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Moi mau khop HINH DANG that cua khoa, khong khop tu khoa mo ta.
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("Google API key",
     re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
     "Khoa API cua Google (Gemini, Maps...) - thu hoi ngay tren Google Cloud"),
    # LOI DA SUA: Google AI Studio cap khoa Gemini theo dang moi "AQ.Ab8..."
    # chu khong con chi "AIzaSy..." nua. Mau tren khong bat duoc dang do, nen
    # mot khoa that dan vao tai lieu hay JSON se lot qua ma khong ai biet.
    # Phat hien khi kiem tra chinh khoa that cua du an nay.
    ("Google API key (dang AQ.)",
     re.compile(r"(?<![A-Za-z0-9_])AQ\.[A-Za-z0-9_\-]{40,}"),
     "Khoa API Gemini dang moi cua Google AI Studio - thu hoi ngay"),
    ("Khoa rieng PEM",
     re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
     "Khoa rieng - thu hoi va tao lai"),
    ("Service account JSON",
     re.compile(r'"type"\s*:\s*"service_account"'),
     "File credentials cua Google Cloud - phai nam trong backend/secrets/"),
    ("private_key_id",
     re.compile(r'"private_key_id"\s*:\s*"[0-9a-f]{20,}"'),
     "Dinh danh khoa rieng cua service account"),
    ("OpenAI/Anthropic key",
     re.compile(r"\b(?:sk|sk-ant)-[A-Za-z0-9_\-]{20,}"),
     "Khoa API cua nha cung cap LLM"),
    ("Bearer token",
     re.compile(r"[Bb]earer\s+[A-Za-z0-9_\-\.]{30,}"),
     "Token truy cap"),
    # KHONG dat \b o dau: ten bien that thuong la GEMINI_API_KEY hoac
    # OPENAI_API_KEY, ma "_" la ky tu tu nen khong co ranh gioi truoc "API".
    # Dat \b o do se bo sot dung nhung truong hop hay gap nhat.
    ("Gan khoa truc tiep vao ma nguon",
     re.compile(
         r"(?i)(?:api_?key|secret|password|passwd|token|credential)\b\s*[=:]\s*"
         r"[\"'][A-Za-z0-9_\-\.]{16,}[\"']"),
     "Gia tri bi viet thang vao ma nguon thay vi doc tu bien moi truong"),
]

# Phan mo rong khong phai van ban thi bo qua.
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".ico", ".woff", ".woff2",
                 ".ttf", ".ttc", ".db", ".pyc", ".zip", ".gz"}

# Dau cho phep TUONG MINH. Dat o cuoi dong de bao "day la mau co y, khong phai
# khoa that" - dung cho chinh bo test cua scanner.
#
# VI SAO CAN: neu de scanner luon bao 4 van de o file test cua no, nguoi doc se
# quen dan voi viec bo qua canh bao - den khi co khoa that thi cung bo qua not.
# Dau nay phai duoc go vao co y, nen no khong the vo tinh che giau khoa that.
ALLOW = re.compile(r"secret-scan:\s*allow")

# Dong chua mot trong cac dau hieu nay la vi du/placeholder, khong phai khoa that.
PLACEHOLDER = re.compile(
    r"(?i)(<[^>]*>|\bxxx+\b|\bplaceholder\b|\bexample\b|\byour[-_ ]|\bdien\b"
    r"|\bfake\b|\bdummy\b|\btest[-_]?key\b|\bunit-test\b|\.\.\.)")


def tracked_files(scan_all: bool) -> list[Path]:
    """Liet ke cac file can quet.

    LOI DA SUA: truoc day `--all` them "--others --exclude-standard" ma KHONG
    them "--cached". Trong `git ls-files`, "--others" THAY THE hanh vi mac
    dinh chu khong cong them, nen `--all` chi con quet file chua theo doi -
    bo qua toan bo 167 file da theo doi. Kho sach thi no quet 0 file roi in
    "Khong tim thay khoa nao bi ro ri": mot den xanh khong kiem tra gi ca, va
    dung o che do nguoi ta chon vi tuong la ky hon.
    """
    command = ["git", "ls-files"]
    if scan_all:
        command += ["--cached", "--others", "--exclude-standard"]
    output = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout
    return [ROOT / line for line in output.splitlines() if line.strip()]


def _display(path: Path) -> Path:
    """Duong dan ngan gon de in ra, nhung khong vo voi file ngoai repo."""
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def scan(paths: list[Path]) -> list[tuple[Path, int, str, str, str]]:
    findings = []
    for path in paths:
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for number, line in enumerate(text.splitlines(), 1):
            if ALLOW.search(line) or PLACEHOLDER.search(line):
                continue
            for name, pattern, advice in PATTERNS:
                found = pattern.search(line)
                if found:
                    excerpt = found.group(0)
                    masked = excerpt[:6] + "..." + excerpt[-4:] \
                        if len(excerpt) > 14 else excerpt
                    findings.append(
                        (_display(path), number, name, masked, advice))
                    break
    return findings


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Quet khoa bi ro ri (Ngay 8)")
    parser.add_argument("--all", action="store_true",
                        help="Quet ca file chua duoc Git theo doi")
    args = parser.parse_args()

    paths = tracked_files(args.all)
    findings = scan(paths)

    if not paths:
        print("LOI: khong liet ke duoc file nao de quet.")
        print("Ket qua 'khong ro ri' o day la vo nghia - dung tin no.")
        return 1
    print(f"Da quet {len(paths)} file"
          + (" (gom ca file chua theo doi)" if args.all else " duoc Git theo doi"))

    if not findings:
        print("\nKhong tim thay khoa nao bi ro ri.")
        return 0

    print(f"\nTIM THAY {len(findings)} VAN DE:\n")
    for path, number, name, masked, advice in findings:
        print(f"  {path}:{number}")
        print(f"    {name}: {masked}")
        print(f"    -> {advice}")
        print("")

    print("Neu khoa da tung duoc commit, xoa file thoi la CHUA DU - no van nam")
    print("trong lich su Git. Phai thu hoi khoa do va tao khoa moi.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
