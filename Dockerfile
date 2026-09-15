# Hai tang cua ung dung dung chung mot ma nguon Python, nhung khac nhau o mot
# diem ton kem: backend can Tesseract kem cac goi ngon ngu (~150 MB), con giao
# dien thi khong.
#
# Vi vay tep nay co HAI dich: `frontend` dung o tang co so, `backend` them
# Tesseract vao. Gop lam mot image se bat giao dien mang theo 150 MB du lieu
# OCR ma no khong bao gio dung toi.

# --- Tang co so: Python + phu thuoc ---------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Chep RIENG tep phu thuoc truoc khi chep ma nguon: Docker luu cache theo tung
# lop, nen sua mot dong Python se khong lam cai lai toan bo thu vien.
COPY backend/requirements.txt backend/requirements.txt
COPY frontend/requirements.txt frontend/requirements.txt
RUN pip install --no-cache-dir \
        -r backend/requirements.txt \
        -r frontend/requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/
COPY pytest.ini conftest.py ./

# Khong chay bang root. Mot lo hong trong ung dung ma gap quyen root trong
# container thi hau qua rong hon han.
RUN useradd --create-home --uid 1000 ocr \
    && mkdir -p /app/backend/data/images \
    && chown -R ocr:ocr /app
USER ocr


# --- Giao dien: chi can tang co so ----------------------------------------
FROM base AS frontend

EXPOSE 8501
# `--server.address 0.0.0.0` la BAT BUOC: mac dinh Streamlit chi nghe tren
# localhost CUA CONTAINER, nen anh xa cong ra ngoai se khong toi duoc.
CMD ["streamlit", "run", "frontend/streamlit_app.py", \
     "--server.address", "0.0.0.0", "--server.port", "8501", \
     "--server.headless", "true"]


# --- Backend: them Tesseract ----------------------------------------------
FROM base AS backend

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-jpn \
        tesseract-ocr-jpn-vert \
        tesseract-ocr-kor \
        tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*
USER ocr

# LUU Y VE KHAC BIET SO DO: goi cua Debian dung bo `tessdata` tieu chuan, con
# so do 85.9% ngay 15/09 chay tren `tessdata_best` cai tay tren Windows.
# `tessdata_best` chinh xac hon nhung cham hon. Nghia la ket qua trong
# container co the KHAC voi so trong bao cao - chenh lech den tu du lieu model,
# khong phai tu ma nguon. Muon so sanh dung thi gan tessdata_best vao bang
# volume va dat TESSDATA_PREFIX.

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--app-dir", "backend"]
