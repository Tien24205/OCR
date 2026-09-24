# Chuyển hóa danh thiếp thành hồ sơ đối tác chuẩn hóa

Ứng dụng web: chụp hoặc tải ảnh danh thiếp → OCR (Anh + Nhật) → trích xuất trường có cấu trúc → chuẩn hóa → tra cứu bổ sung thông tin doanh nghiệp **có dẫn nguồn** → lưu hồ sơ tập trung, tìm kiếm và xuất dữ liệu.

Đề bài #2. Tài liệu đầy đủ: [Document/README.md](Document/README.md)

```
Streamlit (giao diện)  →  FastAPI (backend)  →  SQLite
                                ↓
        Google Vision HOẶC Tesseract (OCR)  +  Gemini (trích xuất trường)
```

Hai tầng AI được giữ **độc lập có chủ ý**: OCR đọc pixel, Gemini suy diễn. Mọi
giá trị Gemini trả về phải tìm được trong văn bản OCR, không tìm được thì bị
loại — nên nguồn này kiểm chứng được nguồn kia. Xem
[kien-truc-agentic.md](Document/2-ke-hoach/kien-truc-agentic.md).

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

Mở http://localhost:8501 · **Tài liệu API**: http://localhost:8000/docs — mô tả đầy đủ 33 endpoint, bảng mã lỗi và lưu ý khi tích hợp

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

Số đo đối chiếu với Tesseract: xem [báo cáo nâng cấp 21/09](Document/3-bao-cao/nang-cap-ocr-21-09.md).

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

**723 test, không gọi mạng thật**: backend dùng `OCR_PROVIDER=mock`, giao diện dùng `AppTest` chạy headless với backend giả lập.

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
Document/             đề bài, kế hoạch, báo cáo, kiểm chứng
```

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

**5. Mở trang bằng điện thoại và đăng ký ngay**

Người đăng ký đầu tiên trở thành **quản trị**. Deploy xong mà đi ăn cơm thì
ai vào trước người đó nắm quyền.

### Lớp phủ `docker-compose.prod.yml` làm gì

| | Mặc định | Khi có lớp phủ |
|---|---|---|
| Cổng 8000 (API) | mở ra ngoài | **đóng hẳn** |
| Cổng 8501 (giao diện) | mở ra mọi giao diện mạng | chỉ `127.0.0.1` |
| `JWT_SECRET` | để trống được | **bắt buộc**, thiếu thì không khởi động |
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
| Khóa lưu dạng **văn bản thường** trong `.env` | Giống khóa Gemini. Đủ cho một máy; môi trường nhiều người dùng cần lưu dạng băm — xem [roadmap.md](Document/2-ke-hoach/roadmap.md) mốc v2.0 |

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

Lấy số đo thật:

```powershell
.\.venv\Scripts\python.exe backend\scripts\make_card_sheets.py   # in 4 trang A4
# cắt, chụp từng thẻ, lưu vào datasets/<split>/<lang>/NNN.jpg
.\.venv\Scripts\python.exe backend\scripts\check_labels.py
.\.venv\Scripts\python.exe backend\scripts\evaluate.py --split dev
```

---

## Kiến trúc và lộ trình

| Tài liệu | Nội dung |
| --- | --- |
| [kien-truc-agentic.md](Document/2-ke-hoach/kien-truc-agentic.md) | Vì sao chia thành nhiều tác tử, mô hình ba hành động, grounding như lớp an toàn, sơ đồ Mermaid |
| [roadmap.md](Document/2-ke-hoach/roadmap.md) | v1.0 → v4.0, kèm **điều kiện bắt đầu** từng mốc |
| [ngay-21-demo.md](Document/3-bao-cao/ngay-21-demo.md) | Kịch bản demo 7–10 phút |
| [Document/4-kiem-chung/](Document/4-kiem-chung/) | Cái gì đã thật sự chạy, cái gì mới chỉ viết xong |

---

## Thiết kế đáng chú ý

**Chống bịa dữ liệu.** Mô hình sinh có thể trả về một email "hợp lý" ghép từ tên người và tên miền công ty, dù thẻ không hề in email. Câu lệnh "không được bịa" làm giảm tỷ lệ chứ không triệt tiêu, và không đo lường được. Vì vậy mọi giá trị mô hình trả về đều phải **đối chiếu được với văn bản OCR gốc** — không đối chiếu được thì bị loại khỏi bản nháp, nhưng vẫn được ghi lại để báo cáo đo được tỷ lệ tự sinh.

**Bằng chứng gốc là bất biến.** Người dùng sửa dữ liệu ở bảng hồ sơ; `scans.raw_text` và `scans.extraction_json` giữ nguyên kết quả của máy. Không có điều này thì không đo được chất lượng tự động trước khi sửa tay.

**Khóa dịch vụ không bao giờ rời backend.** Streamlit chạy phía máy chủ và gọi FastAPI bằng `httpx`, nên trình duyệt không hề biết tới Google. Không có CORS, không có biến cấu hình nào gửi xuống trình duyệt.

**Thông tin tra cứu phải có nguồn.** Mỗi khẳng định kèm URL, thời điểm và đoạn trích nguyên văn; đoạn trích nào không tìm thấy trên trang nguồn thì khẳng định bị loại. Bộ tải trang chặn địa chỉ nội bộ ở **từng lần chuyển hướng**, không chỉ ở URL đầu.

---

## Giới hạn đã biết

**Chưa có lời gọi Google Vision hay Gemini nào được thực hiện trong dự án này.** Toàn bộ kiểm thử chạy trên provider giả lập. Nghĩa là chưa trả lời được câu hỏi trung tâm: hệ thống đọc đúng bao nhiêu phần trăm các trường trên một tấm danh thiếp thật. Xem [báo cáo Ngày 9](Document/3-bao-cao/ngay-9.md).

| Hạng mục | Trạng thái |
| --- | --- |
| Bộ ảnh mẫu đã chụp | 0/40 — nhãn và trang in đã sẵn sàng |
| Đo chất lượng thật | Công cụ xong, chưa có số |
| Kiểm thử camera, HTTPS trên điện thoại | Chưa — cần thiết bị thật |
| Ngôn ngữ | Mã nguồn xử lý được cả 4 (Anh, Hàn, Nhật, Trung). Hàn và Trung **chưa có thẻ mẫu**, nên ở mức "không bị chặn" chứ chưa phải "đã kiểm chứng" |
| Phạm vi ảnh | Mỗi ảnh một thẻ, một mặt, bố cục ngang |
| Chưa hỗ trợ | Nhiều thẻ trong một ảnh, dịch tự động, chữ dọc nâng cao |

Tầng agentic mặc định **tắt** (`AGENT_ENABLED=false`). Bật lên thì ảnh mờ sẽ bị chặn trước khi gọi dịch vụ, OCR điểm thấp được thử lại với ảnh tăng tương phản, và thiếu tên/công ty thì đọc lại bằng prompt khác — tất cả trong một ngân sách retry có giới hạn.
