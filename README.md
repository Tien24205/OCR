# Chuyển hóa danh thiếp thành hồ sơ đối tác chuẩn hóa

Ứng dụng web: chụp hoặc tải ảnh danh thiếp → OCR (Anh + Nhật) → trích xuất trường có cấu trúc → chuẩn hóa → tra cứu bổ sung thông tin doanh nghiệp **có dẫn nguồn** → lưu hồ sơ tập trung, tìm kiếm và xuất dữ liệu.

Đề bài #2.

> **Tệp này là tài liệu đầy đủ của dự án.** Kế hoạch theo ngày, báo cáo tiến độ
> và tài liệu kiểm chứng nằm trong `Document/` trên máy người phát triển và
> **không được đẩy lên GitHub** (xem `.gitignore`). Mọi kiến thức cần để hiểu,
> chạy, sửa và mở rộng hệ thống đều đã gom vào đây.

```
Streamlit (giao diện)  →  FastAPI (backend)  →  SQLite
                                ↓
        Google Vision HOẶC Tesseract (OCR)  +  Gemini (trích xuất trường)
```

Hai tầng AI được giữ **độc lập có chủ ý**: OCR đọc pixel, Gemini suy diễn. Mọi
giá trị Gemini trả về phải tìm được trong văn bản OCR, không tìm được thì bị
loại — nên nguồn này kiểm chứng được nguồn kia. Chi tiết ở mục
[Kiến trúc: hai nguồn độc lập và tầng grounding](#kiến-trúc-hai-nguồn-độc-lập-và-tầng-grounding).

Cả hai tầng đều là Python và dùng chung một môi trường ảo.

---

## Yêu cầu môi trường

- Python 3.11 trở lên
- Git

Không cần Node.js, không cần Docker.

## Cài đặt

Một môi trường ảo duy nhất ở gốc dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r frontend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Trên macOS/Linux thay `.\.venv\Scripts\python.exe` bằng `.venv/bin/python`, `Copy-Item` bằng `cp`.

Cơ sở dữ liệu tự tạo khi backend khởi động lần đầu — không cần chạy lệnh migration nào.

## Chạy

Cần **hai terminal**, cả hai chạy **từ thư mục gốc dự án**:

```powershell
# Terminal 1 — backend, cổng 8000
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --app-dir backend

# Terminal 2 — giao diện, cổng 8501
.\.venv\Scripts\streamlit.exe run frontend\asgi_app.py
```

Mở http://localhost:8501 · **Tài liệu API**: http://localhost:8000/docs — mô tả đầy đủ 34 endpoint, bảng mã lỗi và lưu ý khi tích hợp

> **Phải chạy từ gốc dự án.** Streamlit đọc `.streamlit/config.toml` theo thư mục đang chạy, không theo vị trí file ứng dụng. Chạy từ chỗ khác thì giới hạn dung lượng tải lên 8 MB sẽ không được áp dụng.

> **Vì sao chạy `asgi_app.py` chứ không phải `streamlit_app.py`.** `asgi_app.py`
> là vỏ ASGI mỏng bọc quanh đúng giao diện đó, chỉ thêm các thẻ PWA vào
> `<head>` để trang cài được lên màn hình chính của điện thoại (xem *Dùng trên
> điện thoại* bên dưới). Chạy thẳng `streamlit_app.py` vẫn hoạt động bình
> thường, chỉ là không cài lên màn hình chính được.

## Dùng trên điện thoại

Giao diện chạy được như một ứng dụng trên màn hình chính, không cần cài gì từ
cửa hàng ứng dụng.

**Cần HTTPS.** Trình duyệt chỉ cho phép dùng camera và cài PWA trên trang
`https://` (hoặc `localhost`). Chạy thử qua mạng LAN bằng `http://192.168.x.x`
thì camera sẽ bị chặn. Dùng `ngrok http 8501` hoặc đặt sau một reverse proxy có
chứng chỉ.

| Máy | Cách cài |
|---|---|
| Android (Chrome) | Menu ⋮ → **Cài ứng dụng** / **Thêm vào màn hình chính** |
| iPhone (Safari) | Nút Chia sẻ → **Thêm vào MH chính** |

Sau khi cài, ứng dụng mở toàn màn hình, không có thanh địa chỉ.

**Không có bộ nhớ đệm ngoại tuyến, và đó là cố ý.** Service worker của ứng dụng
chỉ chuyển tiếp yêu cầu chứ không giữ lại gì. Một bộ nhớ đệm sẽ giữ ảnh danh
thiếp và hồ sơ đối tác trong trình duyệt — nằm ngoài mọi phép kiểm quyền của
backend và sống lâu hơn cả phiên đăng nhập. Xem `frontend/asgi_app.py`.

**Cắt viền tự động.** Ở trang Quét thẻ, ảnh có viền nền rõ sẽ được đề xuất một
khung cắt, bật sẵn. Ảnh **gửi đi chính là ảnh đang hiển thị** — tắt công tắc là
gửi ảnh gốc. Không có bước sửa nào chạy sau lưng, vì ảnh đã gửi là bằng chứng
gốc để đối chiếu kết quả OCR. Trên 54 ảnh chụp thật trong `Dataset/Camera`, 50
ảnh nhận được đề xuất, cắt trung vị 31% diện tích.

## Thử ngay khi chưa có API key

Mặc định `OCR_PROVIDER=mock`, tức là phát lại kết quả OCR đã lưu theo mã băm của ảnh. **Tải một ảnh bất kỳ lên sẽ báo `FIXTURE_MISSING`** vì chưa có bản ghi cho ảnh đó.

Để có bộ ảnh dùng được ngay:

```powershell
.\.venv\Scripts\python.exe backend\scripts\make_card_sheets.py --crop
```

Lệnh này sinh 40 danh thiếp hư cấu kèm bản ghi tương ứng. Sau đó tải `datasets\_dryrun\dev\ja\001.jpg` lên là thấy trọn luồng chạy.

Ảnh đó là chữ in kỹ thuật số sắc nét tuyệt đối — **chỉ để xem luồng chạy, không dùng để đánh giá chất lượng OCR**.

---

## Biến cấu hình

Toàn bộ nằm ở `backend/.env` (đã bị `.gitignore` chặn). Xem `backend/.env.example` để biết danh sách đầy đủ.

| Biến | Ý nghĩa | Mặc định |
| --- | --- | --- |
| `OCR_PROVIDER` | `google`, `tesseract` (cục bộ, miễn phí), `rapidocr` (cục bộ, miễn phí, cần `pip install rapidocr onnxruntime`) hoặc `mock` (phát lại bản ghi, offline) | `mock` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Đường dẫn JSON service account; tương đối thì tính từ `backend/` | — |
| `TESSERACT_CMD` | Đường dẫn file chạy Tesseract — chỉ cần khi nó không nằm trong `PATH` | — |
| `API_KEYS` | Khóa API, ngăn cách bằng dấu phẩy. **Để trống = API mở** | — |
| `RATE_LIMIT_PER_MINUTE` | Số lời gọi mỗi phút cho mỗi khóa (0 = không giới hạn) | `60` |
| `EXTRACTOR` | `gemini` hoặc `heuristic` (regex, không cần mạng) | `heuristic` |
| `GEMINI_API_KEY` | Khóa từ Google AI Studio | — |
| `GEMINI_MODEL` | Tên model — **đừng đoán**, xem lệnh bên dưới | — |
| `AGENT_ENABLED` | Bật tầng agentic tự sửa lỗi | `false` |
| `DATABASE_URL` · `IMAGE_DIR` | Vị trí lưu trữ | `backend/data/` |
| `MAX_UPLOAD_BYTES` | Giới hạn dung lượng ảnh | 8 MB |
| `BATCH_WORKERS` | Số ảnh xử lý đồng thời trong một lô | 3 |
| `RETENTION_DAYS` | Thời hạn lưu bản quét và ảnh gốc; `0` = giữ mãi mãi | `0` |
| `ENRICH_*` | Giới hạn của bước tra cứu doanh nghiệp | xem `.env.example` |

### Xoá dữ liệu và thời hạn lưu trữ

Danh thiếp là dữ liệu cá nhân, nên phải có đường xoá:

| Lệnh | Xoá gì |
| --- | --- |
| `DELETE /api/scans/{id}` | Bản quét + ảnh gốc. Hồ sơ đã lưu **không** bị xoá theo |
| `DELETE /api/contacts/{id}` | Hồ sơ, email/điện thoại/địa chỉ, các bản quét của nó và ảnh gốc |

Xoá **hẳn**, không đánh dấu ẩn: một bản ghi "đã xoá" vẫn là dữ liệu cá nhân
đang lưu. Doanh nghiệp không bị xoá theo — nó dùng chung cho nhiều hồ sơ.

Ảnh lưu theo SHA-256 của nội dung nên hai bản quét có thể dùng chung một tệp;
ảnh **chỉ** bị xoá khi không còn bản quét nào trỏ tới.

`RETENTION_DAYS=30` thì bản quét quá 30 ngày bị dọn tự động (hồ sơ đã lưu giữ
nguyên). Việc dọn chạy nền sau mỗi lần quét, nhiều nhất một lần mỗi giờ — máy
không quét gì thì cũng không nhận thêm ảnh nào. Cần chắc chắn hơn thì gọi
`purge_expired` từ cron.

### Xuất dữ liệu

`GET /api/export?format=json|csv|vcf`, hoặc dùng nút trên trang **Hồ sơ**.

| Định dạng | Dùng khi nào |
| --- | --- |
| `json` | Sao lưu, nạp vào hệ thống khác — giữ đầy đủ dữ liệu và nguồn |
| `csv` | Mở bằng bảng tính; có BOM UTF-8 để Excel không đọc sai chữ Nhật |
| `vcf` | **vCard 3.0** — mở trên điện thoại là danh bạ tự nhận, không cần map cột |

Giao diện chỉ đọc **một** biến: `API_BASE_URL` (mặc định `http://127.0.0.1:8000`). Nó không giữ khóa nào.

### Bật OCR thật

Có ba đường. **Grounding hoạt động như nhau ở cả ba** — nó chỉ đòi hỏi OCR
và Gemini là hai nguồn độc lập, chứ không đòi OCR phải là nhà cung cấp nào.

| | `tesseract` | `rapidocr` | `google` |
| --- | --- | --- | --- |
| Chi phí | Miễn phí, không giới hạn | Miễn phí, không giới hạn | Miễn phí trong 1 000 đơn vị/tháng |
| Cần gắn thẻ | Không | Không | **Có** — bắt buộc bật billing |
| Cần mạng | Không | Chỉ lần đầu (tải model) | Có |
| Cài đặt | Phần mềm hệ thống | `pip install` | Tài khoản Google Cloud |
| Đa ngôn ngữ một lần gọi | Có | **Không** — mỗi ngôn ngữ một model | Có |

#### Đường A — Tesseract (miễn phí, chạy cục bộ)

Tesseract là phần mềm hệ thống, `pip install` không đủ:

- **Windows:** tải bản [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki).
  Trong trình cài đặt, mở mục *Additional language data* và **tick Japanese,
  Korean, Chinese** — quên bước này là lỗi hay gặp nhất, và ứng dụng sẽ báo
  đích danh gói nào còn thiếu.
- **macOS:** `brew install tesseract tesseract-lang`
- **Linux:** `apt install tesseract-ocr tesseract-ocr-jpn tesseract-ocr-kor tesseract-ocr-chi-sim`

Rồi đặt `OCR_PROVIDER=tesseract` trong `backend\.env`. Nếu lệnh `tesseract`
không nằm trong `PATH`, trỏ thẳng tới nó bằng `TESSERACT_CMD`.

#### Đường B — RapidOCR (miễn phí, chạy cục bộ, không cần cài phần mềm hệ thống)

```powershell
.\.venv\Scripts\python.exe -m pip install rapidocr onnxruntime
```

Rồi đặt `OCR_PROVIDER=rapidocr`. Ba điều phải biết trước khi chọn đường này:

- **Model tải về ở lần chạy đầu** (~100–200 MB, vào `site-packages`). Máy không
  có mạng ở lần chạy đầu sẽ báo lỗi `OCR_NOT_CONFIGURED` nói đúng nguyên nhân đó.
- **Mỗi ngôn ngữ một model, chọn theo `OCR_LANGUAGE_HINTS`.** Khác hẳn Tesseract
  vốn nhận `jpn+eng+kor+chi_sim` trong một lời gọi. Đặt `OCR_LANGUAGE_HINTS=ja,en`
  rồi quét thẻ tiếng Hàn thì nó dùng model tiếng Nhật để đọc Hangul — không có
  lỗi nào được báo, chỉ có kết quả sai. **Gợi ý ngôn ngữ phải khớp với thẻ.**
- **Không nằm trong `requirements.txt` và không có trong image Docker**, cố ý:
  phụ thuộc này nặng và chỉ đáng cài khi bạn thật sự cần nó.

Số đo đối chiếu giữa các nhà cung cấp OCR nằm trong `Document/4-kiem-chung/ocr-provider-notes.md` (không công khai).

#### Đường C — Google Vision

Cần bật billing trên Google Cloud và bật Cloud Vision API, sau đó chọn **một**
trong hai cách xác thực: trỏ `GOOGLE_APPLICATION_CREDENTIALS` tới file JSON
service account, hoặc để trống biến đó và chạy `gcloud auth application-default
login`.

#### Xác nhận cấu hình

```powershell
# 1. Xem tài khoản của bạn dùng được model Gemini nào
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --list-models

# 2. Điền backend\.env, rồi bấm "Xác minh dịch vụ" trên sidebar của ứng dụng
#    (hoặc gọi POST /api/readiness/verify) — chỉ tốn 2 lời gọi dịch vụ
```

Phép xác minh gọi **thật** nhà cung cấp OCR và bộ trích xuất đang bật, rồi nhớ kết quả cho `GET /api/health`. Nó phân biệt ba trạng thái mà trước đây bị gộp làm một: *đã điền cấu hình*, *đang chạy mock*, và *đã xác minh bằng lời gọi thật lúc HH:MM*.

`GET /api/health` báo trạng thái sẵn sàng của từng dịch vụ **mà không tiết lộ giá trị khóa**. Sidebar của ứng dụng hiển thị đúng thông tin này.

---

## Kiểm thử

Một lệnh chạy cả backend lẫn giao diện, từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

**738 test, không gọi mạng thật**: backend dùng `OCR_PROVIDER=mock`, giao diện dùng `AppTest` chạy headless với backend giả lập.

```powershell
# Quét rò rỉ khóa — trả mã thoát 1 nếu tìm thấy, dùng được trong CI
.\.venv\Scripts\python.exe backend\scripts\check_secrets.py --all

# Đối chiếu số liệu trong tài liệu với mã nguồn thật (thêm --fix để sửa luôn)
.\.venv\Scripts\python.exe backend\scripts\check_docs.py

# Kiểm tra bộ nhãn dữ liệu mẫu
.\.venv\Scripts\python.exe backend\scripts\check_labels.py

# Đo chất lượng trích xuất theo từng trường và từng ngôn ngữ
.\.venv\Scripts\python.exe backend\scripts\evaluate.py --split dev
```

### Cổng chặn trước khi đẩy code

CI chạy bốn cổng kiểm. Đã có một lần đẩy code với chỉ hai trong bốn cổng được
chạy ở máy — `ruff` và `pytest` xanh nên tưởng là xong, còn `check_docs.py`
thì lệch số liệu và CI đỏ.

Tệ hơn: **khi một cổng đỏ thì các bước sau nó trên CI không chạy nữa.** Lần
đó `check_secrets` và `pip-audit` không hề được kiểm, mà nhìn vào bảng kết
quả thì rất dễ tưởng chúng an toàn.

Bật cổng chặn ở máy, một lần cho kho mã nguồn này:

```powershell
git config core.hooksPath .githooks
```

Từ đó mỗi lần `git push` sẽ chạy `ruff`, `check_docs` và `check_secrets`
trước. Cả ba xong trong vài giây, và **cả ba đều chạy hết** dù cái trước đã
hỏng — khác với CI, để báo một lượt thay vì bắt sửa từng vòng.

`pytest` **không** nằm trong hook, có ý: bộ test mất gần hai phút, và gắn nó
vào mọi lần đẩy thì người ta sẽ học cách gõ `--no-verify`. Một cổng bị tắt
luôn thì tệ hơn một cổng hẹp. CI vẫn chạy test.

Số liệu tài liệu lệch thì sửa bằng:

```powershell
.\.venv\Scripts\python.exe backend\scripts\check_docs.py --fix
```

Bỏ qua một lần khi thật sự cần: `git push --no-verify`.


---

## Cấu trúc

```text
backend/app/          FastAPI
  ├── services/ocr/       lớp trừu tượng OCR: Google Vision + Tesseract + mock
  ├── services/extract/   trích xuất trường + grounding chống bịa dữ liệu
  ├── services/enrich/    tra cứu doanh nghiệp có chặn SSRF
  └── pipeline.py         điều phối; agent_runner.py khi bật chế độ agentic
backend/scripts/      công cụ chạy tay (thử OCR, sinh thẻ mẫu, đo chất lượng)
backend/tests/        unit + integration
frontend/             streamlit_app.py + app_pages/ + lib/
datasets/             ảnh mẫu (không commit) + labels.jsonl
Document/             kế hoạch, báo cáo, kiểm chứng — CHỈ CÓ TRÊN MÁY,
                      không đẩy lên GitHub; nội dung cốt lõi đã gom vào README
```

---

## Định hướng cho trợ lý AI

Mục này viết cho một trợ lý AI vừa mở kho mã nguồn này lần đầu. Người đọc bình
thường bỏ qua được.

### Bắt đầu đọc từ đâu

| Câu hỏi | Mở tệp |
| --- | --- |
| Một tấm ảnh đi qua những gì | `backend/app/pipeline.py` |
| Ai được xem cái gì | `backend/app/access.py` — **mọi** luật phân quyền ở đúng tệp này |
| Vì sao một giá trị bị loại | `backend/app/services/extract/grounding.py` |
| Cấu hình nào tồn tại, mặc định ra sao | `backend/app/config.py` |
| Đăng nhập, khoá API, giới hạn tần suất | `backend/app/auth.py` |
| Bảng dữ liệu | `backend/app/models.py` — 12 bảng |

### Bốn bất biến, đừng phá

1. **Grounding không được bỏ qua.** Mọi giá trị model trả về phải đối chiếu
   được với `raw_text`. Đừng thay bằng một câu trong prompt.
2. **Phân quyền chỉ sửa ở `access.py`.** Thêm endpoint mới thì gọi
   `loc_theo_chu()` hoặc `doi_quyen()`, đừng viết luật riêng tại chỗ.
3. **Bản ghi của người khác trả 404, không phải 403.** 403 xác nhận bản ghi đó
   có thật.
4. **Bằng chứng gốc bất biến.** `scans.raw_text` và `scans.extraction_json`
   không bao giờ bị ghi đè; người dùng sửa ở bảng hồ sơ.

### Quy ước viết mã

- **Ghi chú trong mã: tiếng Việt KHÔNG DẤU.** Chuỗi hiện cho người dùng thì có
  dấu đầy đủ. Đừng trộn hai thứ.
- Ghi chú trả lời **vì sao**, không phải **làm gì** — phần *làm gì* đã nằm
  trong chính dòng mã.
- Tên hàm và biến bằng tiếng Việt không dấu ở phần viết sau (`nguoi_goi`,
  `che_email`, `doi_quyen`); phần viết trước dùng tiếng Anh. Cả hai đều chấp
  nhận được, theo tệp đang sửa.

### Kiểm trước khi coi là xong

```powershell
python -m pytest -q                              # 738 test
python -m ruff check backend frontend mcp_server conftest.py
python backend\scripts\check_docs.py            # số liệu tài liệu vs mã nguồn
python backend\scripts\check_secrets.py         # khoá bị commit nhầm
```

Bốn lệnh này đúng là bốn cổng CI. Bật cổng chặn ở máy một lần:
`git config core.hooksPath .githooks`.

**Sửa bug thì viết test tái hiện bug TRƯỚC, sửa sau.** Test phải đỏ vì đúng lý
do trước khi bản vá được tính là xong.

### Hai cái bẫy đã có người vấp

- `/api/auth/*` nằm trong `PUBLIC_PATHS`, nên middleware xác thực **trả về sớm
  và không điền `request.state`**. Đọc `nguoi_goi(request)` ở đó sẽ luôn thấy
  "không có ai" — mà "không có ai" lại được coi là *chế độ mở*, tức thấy tất
  cả. Muốn kiểm quyền ở đường công khai thì phải tự đọc phiếu.
- `pytest.importorskip` **lặng lẽ bỏ qua** cả tệp test khi thiếu gói, và CI vẫn
  xanh. Kiểm bằng cách so số test CI thu thập được với số ở máy.

---

## Chạy bằng Docker

Một lệnh, không cần cài Python hay Tesseract trên máy:

```bash
cp backend/.env.example backend/.env   # điền khóa Gemini nếu có
docker compose up --build
```

Rồi mở **http://localhost:8501**.

| Điều | Cách làm |
| --- | --- |
| Dừng | `docker compose down` |
| Dừng **và xoá dữ liệu** | `docker compose down -v` |
| Xem log | `docker compose logs -f backend` |
| Chạy lại sau khi sửa mã | `docker compose up --build` |

**Dữ liệu sống lâu hơn container.** Hồ sơ và ảnh nằm trong volume `ocr-data`,
nên `docker compose down` rồi `up` lại vẫn còn nguyên. Chỉ `down -v` mới xoá.

**Khóa không nằm trong image.** `backend/.env` bị `.dockerignore` chặn và chỉ
được nạp lúc chạy — nên image đẩy lên registry cũng không mang theo khóa nào.
Một khóa lọt vào lớp image thì xoá tệp đi cũng không gỡ được, y hệt như commit
khóa vào Git.

### Một khác biệt cần biết trước

Gói Tesseract của Debian dùng bộ `tessdata` tiêu chuẩn, còn số đo **85,9%**
ngày 15/09 chạy trên `tessdata_best` cài tay trên Windows. `tessdata_best`
chính xác hơn nhưng chậm hơn.

Nghĩa là **kết quả trong container có thể khác con số trong báo cáo** — chênh
lệch đến từ dữ liệu model, không phải từ mã nguồn.

Đã quan sát thật trên cùng một tấm thẻ:

| | Máy thật (`tessdata_best`) | Container (tessdata Debian) |
| --- | --- | --- |
| Website | `https://www.example.co.` + `Jp` | `https://www.example.co` + `Jp` |
| Phòng ban | `営業 本 部 BES` | `営業 本 部 ss ah`, `=]`, `Al`, `Ail` |

Container **mất dấu chấm** trước `jp`, nên hệ thống nối dòng lại được
`example.cojp` chứ không phải `example.co.jp` — và grounding loại website đó.

**Đó là hành vi đúng.** Ký tự ấy thật sự không có trong văn bản OCR đọc ra;
chấp nhận nó nghĩa là bịa thêm một ký tự không ai nhìn thấy. Kết quả: trên
thẻ này container đọc được 5 trường, máy thật đọc được 6.

Muốn số đo khớp với báo cáo thì gắn `tessdata_best` vào bằng volume và đặt
`TESSDATA_PREFIX`.

---

## Triển khai miễn phí bằng Cloudflare Tunnel

Cách đưa ứng dụng lên một địa chỉ `https://` thật mà **không tốn tiền, không
cần VPS, không cần mở cổng trên router**. Ứng dụng chạy trên máy của bạn;
Cloudflare chỉ làm đường dẫn vào.

### Vì sao phải là HTTPS

Trình duyệt chặn camera và chặn cài PWA trên `http://` (trừ `localhost`).
Chạy qua IP trần là mất đường chụp ảnh — tức mất tính năng chính. Cloudflare
cấp và tự gia hạn chứng chỉ, không phải làm gì thêm.

### Đổi lại là gì

**Máy phải bật.** Tắt máy là trang sập. Đủ cho demo và cho dùng nội bộ; muốn
chạy 24/7 thì cần một máy chủ thật.

Dữ liệu nằm trong volume `ocr_ocr-data` trên máy bạn, không mất khi tắt.

### Các bước

**1. Sinh khóa ký phiên đăng nhập**

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

**2. Tạo tunnel ở Cloudflare**

Cần một tài khoản Cloudflare (miễn phí) và một tên miền đã trỏ nameserver về
Cloudflare. Vào **Zero Trust → Networks → Tunnels → Create a tunnel**, chọn
kiểu **Cloudflared**, đặt tên, rồi **sao lấy token**.

Ở bước *Public hostname*, khai:

| Ô | Điền |
|---|---|
| Subdomain | ví dụ `ocr` |
| Domain | tên miền của bạn |
| Service type | `HTTP` |
| URL | `frontend:8501` |

`frontend:8501` là tên dịch vụ trong mạng nội bộ của compose, **không phải**
`localhost:8501` — `cloudflared` chạy trong container, nên `localhost` với nó
là chính nó.

**3. Đặt hai biến vào tệp `.env` ở gốc dự án**

Là gốc dự án, **không phải** `backend/.env`:

```
JWT_SECRET=<chuỗi vừa sinh ở bước 1>
CLOUDFLARE_TUNNEL_TOKEN=<token vừa sao ở bước 2>
```

**4. Chạy**

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**5. Đăng ký NGAY, trước khi đưa địa chỉ cho ai**

Lớp phủ này đặt `REGISTRATION_OPEN=false`, nghĩa là trang **không nhận người
tự đăng ký**. Nhưng khi cơ sở dữ liệu chưa có tài khoản nào thì cửa vẫn mở —
phải có người đầu tiên vào được thì mới có quản trị, không thì hệ thống tự
khoá chết chính nó.

Nên có đúng một khe hở: **từ lúc dịch vụ lên đến lúc bạn đăng ký.** Ai vào
trước người đó là quản trị. Đăng ký xong là cửa tự đóng, không cần khởi động
lại, không cần sửa gì.

**6. Cấp tài khoản cho người khác**

Trang **Tổng quan → "Cấp tài khoản cho người khác"**, chỉ quản trị mới thấy.
Tài khoản tạo ở đây luôn là quyền thường.

### Vì sao phải đóng đăng ký — một lỗ hổng đã đo được

Hai quy tắc, mỗi cái đều hợp lý khi đứng riêng:

- trang đăng ký mở
- bản ghi `owner_id IS NULL` hiện với **mọi** người đăng nhập — cố ý, để bản
  quét tạo trước Ngày 23 không biến mất khi bật đăng nhập lên

Ghép lại thì thành một cửa mở. Đo thật trước khi sửa — một người lạ vừa đăng
ký lấy được:

```
danh sach ban quet     1
chi tiet ban quet      200
ANH THE                200      ← tải được ảnh tấm danh thiếp
danh sach ho so        1
XUAT TOAN BO           3112     ← cả tập dữ liệu, dạng tệp
```

`REGISTRATION_OPEN=false` bịt vế thứ nhất. Vế thứ hai giữ nguyên vì nó vẫn
đúng: người trong nhà cần thấy dữ liệu cũ.

### Lớp phủ `docker-compose.prod.yml` làm gì

| | Mặc định | Khi có lớp phủ |
|---|---|---|
| Cổng 8000 (API) | mở ra ngoài | **đóng hẳn** |
| Cổng 8501 (giao diện) | mở ra mọi giao diện mạng | chỉ `127.0.0.1` |
| `JWT_SECRET` | để trống được | **bắt buộc**, thiếu thì không khởi động |
| Đăng ký | mở cho bất kỳ ai | **đóng**, trừ khi chưa có tài khoản nào |
| Dữ liệu | volume `ocr-data` | volume **riêng** `ocr-prod-data` |
| OCR | `tesseract` | `tesseract` — miễn phí, người lạ quét bao nhiêu cũng không ra hoá đơn |
| Đường ra Internet | không có | `cloudflared` |

Backend không cần mở cổng vì giao diện gọi nó qua mạng nội bộ của compose.
Đã kiểm: đóng cổng 8000 rồi ứng dụng vẫn chạy đủ, chỉ là API không còn với
tới được từ ngoài.

### Đã kiểm chứng những gì

Mô phỏng yêu cầu đi qua tunnel (`Host` và `Origin` là tên miền Cloudflare,
không phải `localhost`):

| Đường | Kết quả |
|---|---|
| `GET /` | 200 |
| `GET /_stcore/health` | 200 |
| WebSocket `/_stcore/stream` | **101 Switching Protocols** |
| `/manifest.webmanifest`, `/sw.js`, `/icon-192.png` | 200 |
| Thẻ `rel="manifest"` trong `<head>` | có |

WebSocket là thứ quyết định giao diện có bấm được không, nên nó được kiểm
riêng: Streamlit có phép kiểm nguồn gốc kết nối, và phép kiểm đó **không**
chặn tunnel — nghĩa là không phải chỉnh `enableCORS` hay
`enableXsrfProtection` gì cả.

### Lỗi 530 — gần như chắc chắn là mạng chặn UDP

Đây là cái bẫy tốn thời gian nhất, nên ghi riêng.

`cloudflared` mặc định nối bằng **QUIC, chạy trên UDP cổng 7844**. Rất nhiều
mạng gia đình và mạng công ty chặn UDP ra ngoài. Khi đó tunnel vẫn khởi động,
vẫn in ra địa chỉ, nhưng mọi yêu cầu trả **530** — một mã lỗi không hề nhắc gì
đến UDP.

Dấu hiệu trong log:

```
ERR Failed to dial a quic connection  error="... timeout: no recent network activity"
INF precheck component="UDP Connectivity"  status=fail
INF precheck complete  suggested_protocol=http2
```

Chính `cloudflared` phát hiện ra và ghi `suggested_protocol=http2`, nhưng **nó
không tự chuyển**. Cả hai tệp `docker-compose.demo.yml` và
`docker-compose.prod.yml` đã đặt sẵn `--protocol http2`, nên bạn không gặp lỗi
này. HTTP/2 chạy trên TCP 443 — cùng đường với mọi trang web khác.

> Phải đặt bằng **cờ dòng lệnh**. Biến môi trường `TUNNEL_PROTOCOL` không được
> bản `cloudflared` hiện tại đọc ở chế độ này — đã thử, nó vẫn quay số QUIC và
> vẫn 530.

Nối thành công thì log có dòng này:

```
INF Registered tunnel connection  connIndex=0  location=hkg12  protocol=http2
```

Mạng cho UDP qua thì đặt `TUNNEL_PROTOCOL=quic` để nhanh hơn một chút.

### Khi có sự cố

```powershell
# Tunnel đã nối được chưa
docker compose logs cloudflared | Select-String -Pattern "Registered tunnel|ERR"

# Giao diện có sống không, kiểm ngay trên máy chủ
curl http://localhost:8501/

# Backend có sống không (cổng 8000 đã đóng nên phải hỏi từ bên trong)
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').status)"
```

### Một việc nên làm trước khi mở cho người khác

Đổi `API_KEYS` trong `backend/.env` sang khóa mới. Khóa đang dùng ở máy phát
triển không nên mang lên bản chạy thật.

---

## Dùng bằng trợ lý AI (MCP server)

`mcp_server/server.py` là một [MCP](https://modelcontextprotocol.io) server
cho phép Claude hoặc trợ lý AI khác dùng kho danh thiếp: quét thẻ, tìm hồ sơ,
xem kết quả nhận diện.

### Phân quyền: không có hệ quyền thứ hai

Server này **không** tự nghĩ ra một hệ quyền riêng. Nó **đăng nhập như một
người dùng bình thường** rồi gọi đúng những API mà giao diện web vẫn gọi —
nên giới hạn nằm ở backend, nơi đã có bộ test chứng minh, chứ không nằm ở đây.

Nghĩa là "phân quyền cho từng tài khoản" được thực hiện bằng cách **mỗi người
khai tài khoản của mình** trong cấu hình MCP của họ:

| Biến môi trường | Phạm vi nhìn thấy |
|---|---|
| `OCR_EMAIL` + `OCR_PASSWORD` | Đúng phần của tài khoản đó. `admin` thấy tất cả, y như trên web |
| `OCR_API_KEY` | Chế độ **hệ thống** — thấy tất cả, không gắn với ai |
| `OCR_API_URL` | Địa chỉ backend, mặc định `http://127.0.0.1:8000` |

Không có đường nào để trợ lý nhìn vượt qua phạm vi đó.

### Cài và khai báo

```powershell
.\.venv\Scripts\python.exe -m pip install -r mcp_server/requirements.txt
```

Trong tệp cấu hình MCP của Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "danh-thiep": {
      "command": "C:\đường\dẫn\.venv\Scripts\python.exe",
      "args": ["C:\đường\dẫn\mcp_server\server.py"],
      "env": {
        "OCR_API_URL": "http://127.0.0.1:8000",
        "OCR_EMAIL": "ban@congty.vn",
        "OCR_PASSWORD": "mật khẩu của bạn"
      }
    }
  }
}
```

> Mật khẩu nằm trong tệp cấu hình dưới dạng văn bản thường — cùng mức tin cậy
> với khóa API vốn đã nằm trong `backend/.env`. Muốn hơn thế thì cần một bảng
> khóa-theo-người-dùng có thu hồi được ở backend; đó là một tính năng riêng,
> chưa làm.

### Sáu công cụ

| Công cụ | Làm gì |
|---|---|
| `toi_la_ai` | Đang làm việc dưới danh tính nào, thấy được phạm vi nào |
| `tim_ho_so` | Tìm theo tên, công ty, email, số điện thoại |
| `xem_ho_so` | Chi tiết một hồ sơ |
| `danh_sach_ban_quet` | Các bản quét gần đây và trạng thái |
| `quet_danh_thiep` | Gửi một ảnh JPEG/PNG từ đĩa lên để nhận diện |
| `xem_ban_quet` | Văn bản OCR và các trường đọc được |

### Đã kiểm chứng

11 test chạy với backend **thật** (không giả lập lớp HTTP, vì điều cần chứng
minh nằm ở chỗ giáp giữa hai bên):

| Phép kiểm | Kết quả |
|---|---|
| An quét một thẻ, Bình gọi `danh_sach_ban_quet` | thấy 0 bản quét |
| Bình gọi `xem_ban_quet` với mã của An | bị chặn, kèm câu giải thích |
| Bình gọi `tim_ho_so` | 0 hồ sơ |
| Quản trị gọi `xem_ban_quet` với mã của nhân viên | đọc được |
| Sai mật khẩu | báo rõ tài khoản nào, để sửa được cấu hình |

CI cài `mcp` và chạy các test này. Khác với Tesseract (150 MB, để CI tự bỏ
qua), `mcp` là gói Python thuần cài hết vài giây — và một ranh giới quyền mà
CI không chạy thử thì không phải một ranh giới.

---

## Xác thực API

**Mặc định API không có xác thực** — bất kỳ ai gọi được cổng 8000 đều đọc được
toàn bộ hồ sơ. Chấp nhận được khi chỉ chạy trên máy cá nhân; **không** chấp
nhận được ở bất cứ nơi nào khác.

Bật lên:

```powershell
# 1. Sinh khóa
.\.venv\Scripts\python.exe -c "import secrets; print('ocr_' + secrets.token_urlsafe(32))"

# 2. Dán vào backend\.env
#    API_KEYS=ocr_...

# 3. Giao diện cũng cần khóa đó (Streamlit chạy phía máy chủ nên trình duyệt
#    không bao giờ thấy nó)
$env:API_KEY = "ocr_..."
```

Gọi API kèm khóa theo một trong hai cách:

```bash
curl -H "X-API-Key: ocr_..."          http://localhost:8000/api/contacts
curl -H "Authorization: Bearer ocr_..." http://localhost:8000/api/contacts
```

`GET /api/health` **luôn mở** để hệ thống giám sát biết dịch vụ còn sống — nó
chỉ trả về cờ true/false, không bao giờ trả về giá trị khóa nào. Trường
`auth_enabled` trong phản hồi cho biết API đang mở hay đóng.

**Đổi `API_KEYS` phải khởi động lại backend.** `--reload` chỉ theo dõi tệp
`.py`, không theo dõi `.env`.

### Hai giới hạn đã biết

| Giới hạn | Nghĩa là |
| --- | --- |
| Bộ đếm tần suất nằm **trong bộ nhớ một tiến trình** | Chạy nhiều bản sao thì mỗi bản đếm riêng; khởi động lại là mất bộ đếm |
| Khóa lưu dạng **văn bản thường** trong `.env` | Giống khóa Gemini. Đủ cho một máy; môi trường nhiều người dùng cần lưu dạng băm — xem mốc **v2.0** ở mục Lộ trình |

---

## Kết quả đo chất lượng

**Chưa có số đo trên ảnh chụp thật.** Công cụ đo đã xong và đã chạy trọn
đường, nhưng còn thiếu bước in, cắt và chụp 40 tấm thẻ mẫu.

| Hạng mục | Trạng thái |
| --- | --- |
| Công cụ đo (`evaluate.py`) | Xong, đã chạy trọn đường 15/09 |
| Quy tắc so sánh | Chốt trong mã nguồn, khóa bằng 22 test **trước khi đo** |
| Số đo trên ảnh chụp thật | **Chưa có** — 0/40 ảnh |
| Nghiệm thu tiếng Hàn, tiếng Trung | Mã nguồn hỗ trợ, chưa có bộ mẫu |

Báo cáo sinh ra ở `reports/evaluation.md` và tự in cảnh báo khi đang chạy ở
chế độ khô, nên không thể đọc nhầm số liệu thử thành số liệu nghiệm thu.

Bảng đo tách **bốn cột**: Đúng / Sai / Bỏ sót / **Tự sinh**. Cột cuối đếm giá
trị hệ thống trả về trong khi thẻ *không hề có* trường đó — bịa ra dữ liệu và
đọc nhầm là hai loại lỗi khác hẳn nhau về mức nguy hiểm, nên không gộp.

### Thử nhanh trên ảnh cắt sẵn (KHÔNG phải số đo)

Khi chỉ muốn kiểm chức năng — thêm một ngôn ngữ, đổi model, sửa pipeline —
một vòng in–cắt–chụp là quá đắt. Cắt thẳng từ trang PNG gốc:

```powershell
.\.venv\Scripts\python.exe backend\scripts\cut_cards.py
# -> datasets/the-cat/<split>/<lang>/001..010.png  (80 tấm)
```

Ảnh này **sắc nét tuyệt đối**, nên chúng nằm ở thư mục riêng và không bao giờ
đi vào `datasets/dev/` hay `datasets/eval/`. Đo trên ảnh sắc nét rồi gọi đó là
độ chính xác của hệ thống là tự lừa mình.

**Một kết quả đo được bằng bộ này** (10 thẻ mỗi ngôn ngữ, đếm số thẻ Tesseract
đọc ra đúng tên / đúng tên công ty):

| `OCR_LANGUAGE_HINTS` | EN | JA | KO | ZH | Tổng |
| --- | --- | --- | --- | --- | --- |
| `ja,en` | 10/10 | 9/9 | 0/0 | 3/1 | 22/20 |
| **`ja,en,ko,zh`** (mặc định) | 10/10 | 8/8 | 1/2 | **10/9** | **29/29** |
| chọn riêng từng thẻ | 10/10 | 9/9 | 2/2 | 9/10 | 30/31 |

Ba điều rút ra:

- **Bật đủ bốn ngôn ngữ không làm hỏng tiếng Anh** — 10/10 ở cả ba cấu hình.
  Thu hẹp xuống `ja,en` trong `.env` làm tiếng Trung tụt từ 10/9 xuống 3/1.
- **Chọn ngôn ngữ riêng cho từng thẻ chỉ hơn 1–2 thẻ**, không đáng để thêm một
  bước đoán ngôn ngữ trước khi OCR.
- **Tiếng Hàn hỏng ở mọi cấu hình**, kể cả `kor+eng` riêng. Các trường khác
  (email, điện thoại, địa chỉ) đọc được, chỉ mỗi tên là không. Chưa rõ đây là
  hạn chế của Tesseract hay của phông dùng để *vẽ* thẻ mẫu — nên không kết luận.

Đây là số đo trên ảnh sắc nét, **không phải** độ chính xác của sản phẩm.

Lấy số đo thật:

```powershell
.\.venv\Scripts\python.exe backend\scripts\make_card_sheets.py   # in 4 trang A4
# cắt, chụp từng thẻ, lưu vào datasets/<split>/<lang>/NNN.jpg
.\.venv\Scripts\python.exe backend\scripts\check_labels.py
.\.venv\Scripts\python.exe backend\scripts\evaluate.py --split dev
```

---

## Kiến trúc: hai nguồn độc lập và tầng grounding

Một tấm ảnh đi qua sáu trạm:

```text
1. Nhận ảnh    kiểm định dạng bằng GIẢI MÃ THẬT (không tin đuôi tệp hay
               Content-Type), giới hạn 8 MB, cạnh tối đa 6000 px, chặn bom
               nén, xoay theo EXIF rồi kiểm dung lượng lần nữa
2. OCR         ra raw_text + toạ độ từng khối chữ
3. Trích xuất  raw_text → khuôn CardExtraction có sẵn trường
4. GROUNDING   đối chiếu TỪNG giá trị với raw_text; không khớp thì loại
5. Chuẩn hoá   điện thoại về dạng quốc tế, email chữ thường, bỏ hậu tố công ty
6. Lưu hồ sơ   phát hiện trùng, người dùng chọn gộp hay tạo mới, kèm revision
```

Trạm 4 là trạm các sản phẩm cùng loại không có — chúng đi thẳng từ 3 sang 5.

### Quy tắc grounding

> Mọi giá trị model trả về đều phải tìm được trong văn bản OCR. Không tìm
> được thì **bị loại**, nhưng vẫn **được ghi lại**.

Vế sau quan trọng ngang vế trước. Giá trị bị loại không biến mất im lặng — nó
vào `scans.grounding_json`, để đo được model bịa nhiều hay ít. Một hệ thống âm
thầm vứt dữ liệu là một hệ thống không ai kiểm toán được.

**Vì sao là một tầng code chứ không phải một câu trong prompt:** prompt chỉ là
lời đề nghị. Model có thể làm theo hôm nay và không làm theo khi đổi phiên bản.
Một tầng chạy *sau* model thì model không có đường đi vòng qua. Khoá bằng **31
test** cố tình ép hệ thống bịa dữ liệu.

### Vì sao hai nguồn phải độc lập

OCR đọc pixel. Model suy diễn. Đó là **hai nguồn khác nhau**, nên nguồn này
kiểm chứng được nguồn kia.

Nếu để model sinh ra cả văn bản thô lẫn các trường thì cơ chế này mất sạch ý
nghĩa — thành ra lấy lời khai của một người ra kiểm chứng chính lời khai đó.

Đây là lý do hệ thống giữ thêm một nhà cung cấp OCR cục bộ thay vì bỏ OCR đi
cho gọn. Tesseract đọc Kanji kém hơn Vision, nhưng nó vẫn **độc lập** với
Gemini — và tính độc lập mới là thứ không được phép đánh đổi.

### Tầng agentic

Mặc định **tắt** (`AGENT_ENABLED=false`). Bật lên thì tầng điều phối đọc kết
quả từng bước rồi quyết định bước sau, trong **ngân sách tối đa 2 lượt thử lại
mỗi bản quét**:

| Tình huống | Hành động |
| --- | --- |
| Ảnh mờ | Chặn trước khi gọi dịch vụ — không tiêu lời gọi cho một ảnh vô vọng |
| OCR điểm thấp | Đọc lại với ảnh đã tăng tương phản |
| Thiếu tên hoặc công ty | Trích xuất lại bằng prompt khác |

Mỗi quyết định được ghi lại và xem được trên trang Tổng quan. Ngân sách có giới
hạn vì một vòng thử lại không chặn là một hoá đơn không chặn.

---

## Lộ trình

> **Nguyên tắc xuyên suốt:** không thêm tính năng khi chưa đo được tính năng
> hiện có. Xây tầng mới trên một nền chưa đo là cách chắc chắn để sau này
> không biết chỗ nào hỏng.

Mỗi mốc ghi kèm **điều kiện để bắt đầu** — phần lớn việc phía sau không chặn ở
công sức lập trình mà chặn ở chỗ khác.

### v1.0 — bản hiện tại · *mã nguồn xong, chưa nghiệm thu*

Đã chạy được: chụp/tải ảnh (hàng loạt tối đa 10) · OCR qua bốn nhà cung cấp ·
trích xuất có schema · grounding · điểm tin cậy bốn tín hiệu · điều phối
agentic có nhánh rẽ thật · tra cứu doanh nghiệp dẫn nguồn, chặn SSRF ·
lưu/tìm/chống trùng · xuất JSON, CSV, vCard · đa người dùng có phân quyền ·
34 endpoint · 738 test.

Còn thiếu để gọi là v1.0 thật:

| Việc | Chặn ở đâu |
| --- | --- |
| Số đo chất lượng trên ảnh chụp thật | Cần in, cắt, chụp 40 thẻ — hiện **0/40** |
| Kiểm thử camera, HTTPS trên điện thoại | Cần thiết bị thật |

*Ghi chú thành thật:* tiếng Hàn và tiếng Trung **đã có trong mã nguồn** nhưng
**chưa từng được đo**, nên tính là *chưa nghiệm thu*, không phải *đã xong*.

### v1.1 — nghiệm thu bốn ngôn ngữ

*Bắt đầu khi:* đã có số đo tiếng Anh và tiếng Nhật.

Đo **riêng từng ngôn ngữ** — gộp chung sẽ giấu mất ngôn ngữ nào yếu. Hiệu
chỉnh ngưỡng so khớp mờ theo dữ liệu thật; ngưỡng 0.90 hiện nay chưa từng được
kiểm trên chữ Kanji thật. Hiệu chỉnh ngưỡng của tác tử chất lượng ảnh — mã
nguồn tự ghi *"thresholds are uncalibrated rules"*.

### v1.5 — mở cho hệ thống khác dùng

*Bắt đầu khi:* chất lượng đã đo và chấp nhận được.

Xác thực bằng khoá API và giới hạn tần suất **đã làm sớm**, vì chúng không
đụng gì tới tầng AI nên không làm hỏng số đo sau này — trong khi để API mở thì
mọi câu nói về "mở cho hệ thống khác dùng" đều không đứng vững. Còn chờ: băm
khoá khi lưu, bộ đếm tần suất dùng chung giữa nhiều bản sao, webhook bật mặc
định, nhập hàng loạt từ thư mục.

### v2.0 — nhiều người dùng

Bảng `users`, phân quyền, Docker, đa người dùng: **đã làm**. Còn lại: chuyển
SQLite sang PostgreSQL, nhật ký thao tác chi tiết theo từng trường.

**Phải trả lời trước khi đi tiếp:** bảng `scans` giữ ảnh gốc và văn bản OCR
bất biến. Nhiều người dùng nghĩa là dữ liệu cá nhân của người khác — lưu bao
lâu, ai xoá được, phải chốt **trước** khi viết dòng mã đầu tiên.

### v3.0 — di động và dịch thuật

Ứng dụng gốc, làm việc ngoại tuyến, dịch chức danh Nhật ↔ Anh.

*Vì sao dịch thuật chưa làm sớm:* chức danh doanh nghiệp Nhật không dịch theo
từ điển được — `部長` là "trưởng phòng" hay "giám đốc" tuỳ quy mô công ty.

### v4.0 — nối vào quy trình kinh doanh

Đồng bộ CRM hai chiều, tác tử gộp trùng, bản đồ quan hệ.

> **Cảnh báo:** tác tử gộp trùng là thứ dễ gây hại nhất trong toàn bộ lộ trình.
> Gộp nhầm hai người thành một hồ sơ là mất dữ liệu **không khôi phục được**, và
> sai lầm đó lan ra mọi hệ thống đã đồng bộ. Phải đo được tỷ lệ nhận nhầm trên
> dữ liệu thật trước, và phải luôn có bước người xác nhận.

### Việc cố ý KHÔNG làm

| Không làm | Vì sao |
| --- | --- |
| Để Gemini làm luôn OCR cho gọn | Phá vỡ tính độc lập hai nguồn; grounding mất sạch ý nghĩa |
| Đọc thẻ hai mặt trong một ảnh | Đề bài chốt một thẻ một mặt; mở rộng phải đổi cả bộ nhãn chuẩn |
| Tự động sửa chính tả tên người | Tên người không có "đúng chính tả"; sửa tự động là bịa có hệ thống |
| Đoán ngôn ngữ khi chữ Hán không phân biệt được | Trả về nhãn `han` trung thực thay vì đoán bừa giữa Nhật và Trung |

---

## Thiết kế đáng chú ý

**Chống bịa dữ liệu.** Mô hình sinh có thể trả về một email "hợp lý" ghép từ tên người và tên miền công ty, dù thẻ không hề in email. Câu lệnh "không được bịa" làm giảm tỷ lệ chứ không triệt tiêu, và không đo lường được. Vì vậy mọi giá trị mô hình trả về đều phải **đối chiếu được với văn bản OCR gốc** — không đối chiếu được thì bị loại khỏi bản nháp, nhưng vẫn được ghi lại để báo cáo đo được tỷ lệ tự sinh.

**Bằng chứng gốc là bất biến.** Người dùng sửa dữ liệu ở bảng hồ sơ; `scans.raw_text` và `scans.extraction_json` giữ nguyên kết quả của máy. Không có điều này thì không đo được chất lượng tự động trước khi sửa tay.

**Khóa dịch vụ không bao giờ rời backend.** Streamlit chạy phía máy chủ và gọi FastAPI bằng `httpx`, nên trình duyệt không hề biết tới Google. Không có CORS, không có biến cấu hình nào gửi xuống trình duyệt.

**Thông tin tra cứu phải có nguồn.** Mỗi khẳng định kèm URL, thời điểm và đoạn trích nguyên văn; đoạn trích nào không tìm thấy trên trang nguồn thì khẳng định bị loại. Bộ tải trang chặn địa chỉ nội bộ ở **từng lần chuyển hướng**, không chỉ ở URL đầu.

---

## Giới hạn đã biết

**Chưa có lời gọi Google Vision hay Gemini nào được thực hiện trong dự án này.** Toàn bộ kiểm thử chạy trên provider giả lập. Nghĩa là chưa trả lời được câu hỏi trung tâm: hệ thống đọc đúng bao nhiêu phần trăm các trường trên một tấm danh thiếp thật.

| Hạng mục | Trạng thái |
| --- | --- |
| Bộ ảnh mẫu đã chụp | 0/40 — nhãn và trang in đã sẵn sàng |
| Đo chất lượng thật | Công cụ xong, chưa có số |
| Kiểm thử camera, HTTPS trên điện thoại | Chưa — cần thiết bị thật |
| Ngôn ngữ | Mã nguồn xử lý được cả 4 (Anh, Hàn, Nhật, Trung). Hàn và Trung **chưa có thẻ mẫu**, nên ở mức "không bị chặn" chứ chưa phải "đã kiểm chứng" |
| Phạm vi ảnh | Mỗi ảnh một thẻ, một mặt, bố cục ngang |
| Chưa hỗ trợ | Nhiều thẻ trong một ảnh, dịch tự động, chữ dọc nâng cao |

Tầng agentic mặc định **tắt** (`AGENT_ENABLED=false`). Bật lên thì ảnh mờ sẽ bị chặn trước khi gọi dịch vụ, OCR điểm thấp được thử lại với ảnh tăng tương phản, và thiếu tên/công ty thì đọc lại bằng prompt khác — tất cả trong một ngân sách retry có giới hạn.
