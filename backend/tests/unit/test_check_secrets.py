"""Test cho bo quet khoa bi ro ri - Ngay 8, dong 10.

Mot bo quet luon bao "sach" thi vo dung, va nguy hiem hon khong co gi: no tao
cam giac an toan gia. Bo test nay chung minh no BAT DUOC khoa that, dong thoi
KHONG bao dong gia o tai lieu va file mau.
"""

from __future__ import annotations

import pytest

from scripts.check_secrets import scan


def write(tmp_path, name: str, content: str):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def found(tmp_path, name: str, content: str) -> list[str]:
    """Tra ve ten cac loai van de tim thay trong mot file."""
    return [item[2] for item in scan([write(tmp_path, name, content)])]


# --- Phai BAT DUOC -------------------------------------------------------

def test_bat_duoc_khoa_google_that(tmp_path):
    """Khoa Google that co dang AIza + 35 ky tu."""
    key = "AIza" + "Sy" + "B" * 33
    assert "Google API key" in found(tmp_path, "config.py", f'KEY = "{key}"')


def test_bat_duoc_khoa_google_dang_moi(tmp_path):
    """Google AI Studio da doi sang dang "AQ.Ab8..." dai hon, khong con "AIza".

    LOI DA SUA: mau cu chi bat "AIza" nen mot khoa Gemini that cap nam 2026
    dan vao tai lieu se lot qua bo quet ma khong ai biet. Phat hien khi doi
    chieu voi khoa that dang dung cua du an.
    """
    key = "AQ" + "." + "Ab8RN6" + "J" * 42
    names = found(tmp_path, "ghi-chu.md", f"khoa dang dung: {key}")
    assert "Google API key (dang AQ.)" in names


def test_khong_bao_dong_gia_voi_chuoi_aq_ngan(tmp_path):
    """Chu "AQ." binh thuong trong van ban khong duoc bi coi la khoa."""
    text = "Phan AQ. 3 cua tai lieu noi ve chat luong anh dau vao."
    assert "Google API key (dang AQ.)" not in found(tmp_path, "ghi-chu.md", text)


def test_bat_duoc_khoa_rieng_pem(tmp_path):
    pem = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg\n-----END"  # secret-scan: allow
    assert "Khoa rieng PEM" in found(tmp_path, "key.pem", pem + " PRIVATE KEY-----")


def test_bat_duoc_service_account_json(tmp_path):
    """Dung file ma nguoi dung se tai ve tu Google Cloud."""
    content = '{\n  "type": "service_' + 'account",\n  "project_id": "ocr-demo"\n}'
    assert "Service account JSON" in found(tmp_path, "gcp-sa.json", content)


def test_bat_duoc_private_key_id(tmp_path):
    content = '{"private_key_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"}'  # secret-scan: allow
    assert "private_key_id" in found(tmp_path, "sa.json", content)


def test_bat_duoc_khoa_viet_thang_vao_ma_nguon(tmp_path):
    assert found(tmp_path, "settings.py",
                 'GEMINI_API_KEY = "aB3dEf7hIjKlMnOpQrStUvWx"')  # secret-scan: allow


def test_bat_duoc_bearer_token(tmp_path):
    token = "Bearer " + "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9abcdefghij"
    assert "Bearer token" in found(tmp_path, "notes.md", token)


# --- KHONG duoc bao dong gia ----------------------------------------------

def test_tai_lieu_nhac_den_ten_mau_khong_bi_bao_dong(tmp_path):
    """Chinh ke hoach Ngay 8 chua chuoi "AIza" de mo ta phep kiem tra.

    Neu bo quet bao dong o day, nguoi doc se quen dan voi viec bo qua canh bao -
    den khi co khoa that thi cung bo qua not.
    """
    content = ('| 10 | `grep -ri "AIza|private_key|BEGIN PRIVATE" .` '
               "| Khong co ket qua |")  # secret-scan: allow
    assert found(tmp_path, "ke-hoach.md", content) == []


def test_file_env_mau_khong_bi_bao_dong(tmp_path):
    content = ("GEMINI_API_KEY=\n"
               "GOOGLE_APPLICATION_CREDENTIALS=./secrets/gcp-sa.json\n"
               "GEMINI_MODEL=")
    assert found(tmp_path, ".env.example", content) == []


@pytest.mark.parametrize("line", [
    'api_key = "<dien khoa cua ban vao day>"',
    'API_KEY = "your-api-key-goes-here"',
    'token = "xxxxxxxxxxxxxxxxxxxx"',
    'SECRET = "example-secret-value-123"',
    'password = "unit-test-password-value"',
])
def test_gia_tri_vi_du_khong_bi_bao_dong(tmp_path, line):
    assert found(tmp_path, "doc.md", line) == []


def test_doc_ma_nguon_doc_khoa_tu_bien_moi_truong_khong_bi_bao_dong(tmp_path):
    content = ('import os\n'
               'api_key = os.environ["GEMINI_API_KEY"]\n'
               'settings.gemini_api_key = api_key\n')
    assert found(tmp_path, "config.py", content) == []


def test_anh_va_file_nhi_phan_bi_bo_qua(tmp_path):
    path = tmp_path / "card.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"AIza" + b"S" * 35)
    assert scan([path]) == []


def test_bao_cao_che_bot_gia_tri_tim_duoc(tmp_path):
    """Bao cao khong duoc in nguyen khoa ra man hinh hoac file log."""
    key = "AIzaSy" + "C" * 33
    items = scan([write(tmp_path, "leak.py", f'K = "{key}"')])
    masked = items[0][3]
    assert key not in masked and masked.startswith("AIzaS") and "..." in masked
