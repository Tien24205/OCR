"""Mo ta OpenAPI cho API - moc 17/09 "mo API cho he thong ben ngoai".

VI SAO TACH RA FILE RIENG: mo ta day du cho 18 endpoint se lam `main.py` va
`contact_routes.py` phinh len va kho doc. Tach ra thi phan dinh tuyen van gon,
con tai lieu thi day du.

Doc duoc o http://localhost:8000/docs
"""

from __future__ import annotations

DESCRIPTION = """
Chuyển danh thiếp thành hồ sơ đối tác có cấu trúc, có dẫn nguồn.

### Luồng chính

    POST /api/scans          tải ảnh lên, trả về ngay với status=pending
    GET  /api/scans/{id}     hỏi trạng thái cho tới khi status=ocr_done
    PATCH /api/scans/{id}/draft   người dùng sửa bản nháp
    POST /api/contacts       lưu bản nháp đã duyệt thành hồ sơ

### Hai điều cần biết trước khi tích hợp

**Xử lý là bất đồng bộ.** `POST /api/scans` trả về ngay; OCR chạy nền. Hỏi
`GET /api/scans/{id}` cho tới khi `status` là `ocr_done` hoặc `failed`.

**Mọi giá trị đều truy về được nguồn.** Mỗi trường trong bản nháp mang
`grounding_verdict` cho biết nó khớp văn bản OCR tới mức nào, và `source` cho
biết đến từ OCR hay do người dùng sửa. Giá trị không đối chiếu được với văn
bản OCR sẽ **không xuất hiện** trong bản nháp — hệ thống không trả về dữ liệu
mà nó không đọc được từ ảnh.

### Chống gửi trùng

`POST /api/contacts` yêu cầu header `Idempotency-Key`. Gửi lại cùng khóa trả
về đúng hồ sơ cũ thay vì tạo bản sao — an toàn khi mạng chập chờn hoặc người
dùng bấm hai lần.

### Xác thực

Hiện **chưa có**. API dành cho triển khai một người dùng trong mạng nội bộ.
Trước khi mở ra Internet phải thêm xác thực và phân quyền theo người tạo.
"""

TAGS = [
    {"name": "scans", "description":
     "Tải ảnh lên và theo dõi quá trình nhận diện."},
    {"name": "contacts", "description":
     "Hồ sơ đối tác đã duyệt: lưu, tìm kiếm, cập nhật, xuất dữ liệu."},
    {"name": "enrichment", "description":
     "Tra cứu thông tin doanh nghiệp từ nguồn công khai. Mỗi khẳng định kèm "
     "URL nguồn, thời điểm và đoạn trích nguyên văn."},
    {"name": "webhooks", "description":
     "Báo cho hệ thống bên ngoài khi một bản quét xử lý xong. "
     "**Mặc định tắt** — xem mô tả endpoint đăng ký."},
    {"name": "system", "description": "Trạng thái và số liệu tổng quan."},
]

# Ma loi dung chung cho moi endpoint. Than phan hoi loi luon co dang:
#   {"error": {"code": ..., "message": ..., "retryable": bool}}
ERROR_CODES = {
    "IMAGE_INVALID": "Tệp không phải ảnh hợp lệ. Hệ thống đọc magic bytes "
                     "chứ không tin đuôi tệp hay Content-Type.",
    "IMAGE_TOO_LARGE": "Ảnh vượt quá MAX_UPLOAD_BYTES (mặc định 8 MB).",
    "BATCH_TOO_LARGE": "Lô vượt quá BATCH_MAX_IMAGES (mặc định 10 ảnh).",
    "SCAN_NOT_FOUND": "Không có bản quét với mã này.",
    "STALE_REVISION": "Bản nháp đã bị sửa bởi một yêu cầu khác. Tải lại rồi "
                      "gửi lại — tránh ghi đè mất thay đổi của người khác.",
    "OCR_UNAVAILABLE": "Dịch vụ OCR tạm thời không phản hồi. `retryable=true`.",
    "OCR_REJECTED": "Dịch vụ OCR từ chối ảnh. `retryable=false` — thử lại "
                    "cũng không thành công, chỉ tốn thêm chi phí.",
    "EXTRACTOR_NOT_CONFIGURED": "Thiếu GEMINI_API_KEY hoặc GEMINI_MODEL.",
    "FIXTURE_MISSING": "Đang chạy OCR_PROVIDER=mock và chưa có bản ghi cho "
                       "ảnh này. Xem mục 'Thử ngay khi chưa có API key' trong README.",
    "WEBHOOK_DISABLED": "Webhook đang tắt. Bật bằng WEBHOOK_ENABLED=true.",
    "WEBHOOK_URL_REJECTED": "URL không hợp lệ hoặc trỏ tới địa chỉ mạng nội bộ.",
    "WEBHOOK_DUPLICATE": "URL này đã được đăng ký.",
}

# Mo ta cho tung endpoint. Khoa la (method, duong dan).
ENDPOINTS: dict[tuple[str, str], dict] = {
    ("post", "/api/scans"): {
        "summary": "Tải một ảnh danh thiếp lên",
        "description":
            "Nhận JPEG hoặc PNG. Kiểm tra bằng magic bytes, xoay theo EXIF, "
            "lưu theo SHA-256 của nội dung nên cùng một ảnh chỉ tốn một bản "
            "trên đĩa.\n\n"
            "Trả về **ngay** với `status=pending`; OCR chạy nền. "
            "Hỏi `GET /api/scans/{id}` để biết kết quả.",
    },
    ("post", "/api/scans/batch"): {
        "summary": "Tải nhiều ảnh trong một lần gửi",
        "description":
            "Tối đa `BATCH_MAX_IMAGES` ảnh. Xử lý với số luồng đồng thời có "
            "giới hạn (`BATCH_WORKERS`, mặc định 3) — không chạy hết song song "
            "để tránh chạm trần quota của dịch vụ OCR.\n\n"
            "**Một ảnh hỏng không làm hỏng cả lô**: mỗi ảnh có mục kết quả "
            "riêng, ảnh lỗi trả về khóa `error`.",
    },
    ("get", "/api/scans/{scan_id}"): {
        "summary": "Trạng thái và kết quả của một bản quét",
        "description":
            "`status` đi theo: `pending` → `processing` → `ocr_done` → "
            "`committed`, hoặc rẽ sang `failed`.\n\n"
            "Khi `ocr_done`, trường `draft` chứa dữ liệu đã chuẩn hóa. Mỗi "
            "dòng có `grounding_verdict` (`exact` / `fuzzy`) và `source` "
            "(`ocr` / `user`).",
    },
    ("patch", "/api/scans/{scan_id}/draft"): {
        "summary": "Sửa bản nháp trước khi lưu thành hồ sơ",
        "description":
            "Phải gửi kèm `revision` đang có. Nếu bản nháp đã bị sửa bởi yêu "
            "cầu khác thì trả `STALE_REVISION` thay vì ghi đè.\n\n"
            "Dòng mới thì bỏ trống `id`. Bằng chứng OCR gốc trong "
            "`scans.raw_text` và `scans.extraction_json` **không bao giờ** bị "
            "thay đổi bởi endpoint này.",
    },
    ("post", "/api/scans/{scan_id}/retry"): {
        "summary": "Chạy lại một bản quét đã lỗi",
        "description": "Chỉ dùng cho lỗi tạm thời. Không phải tải ảnh lên lại.",
    },
    ("get", "/api/scans/{scan_id}/duplicates"): {
        "summary": "Hồ sơ có thể trùng với bản nháp này",
        "description":
            "Chấm điểm theo email, số điện thoại, tên kèm doanh nghiệp và mã "
            "băm ảnh. **Không tự gộp** — người dùng quyết định.",
    },
    ("post", "/api/contacts"): {
        "summary": "Lưu bản nháp đã duyệt thành hồ sơ",
        "description":
            "**Bắt buộc header `Idempotency-Key`.** Gửi lại cùng khóa trả về "
            "đúng hồ sơ cũ thay vì tạo bản sao.\n\n"
            "Chạy trong một transaction: hồ sơ, doanh nghiệp, các giá trị đa "
            "trị và nguồn dữ liệu cùng thành công hoặc cùng thất bại.",
    },
    ("get", "/api/contacts"): {
        "summary": "Tìm kiếm hồ sơ",
        "description":
            "`q` tìm theo tên, công ty, email và số điện thoại. Chuỗi tìm kiếm "
            "được chuẩn hóa NFKC nên chữ full-width tiếng Nhật khớp được với "
            "half-width — `ＴＥＬ：０３` tìm ra `TEL:03`.",
    },
    ("get", "/api/export"): {
        "summary": "Xuất toàn bộ hồ sơ",
        "description":
            "| `format` | Dùng khi nào |\n"
            "| --- | --- |\n"
            "| `json` | Giữ đầy đủ dữ liệu và nguồn. Dùng để sao lưu hoặc nạp "
            "vào hệ thống khác |\n"
            "| `csv` | Mở bằng bảng tính. Có BOM UTF-8 để Excel trên Windows "
            "không đọc sai chữ Nhật; ô đa giá trị là mảng JSON để giữ số 0 đầu "
            "của số điện thoại |\n"
            "| `vcf` | vCard 3.0 — mở trên điện thoại là danh bạ tự nhận, "
            "không cần map cột |",
    },
    ("post", "/api/organizations/{organization_id}/enrich"): {
        "summary": "Tra cứu thông tin doanh nghiệp từ nguồn công khai",
        "description":
            "Lấy tên miền từ website hoặc email công ty trên thẻ. **Không đoán "
            "website từ tên công ty** — không có tên miền thì trả `not_found`.\n\n"
            "Mỗi khẳng định phải kèm đoạn trích **nguyên văn** từ trang nguồn; "
            "đoạn nào không tìm thấy trên trang thì khẳng định bị loại.\n\n"
            "Bộ tải trang chặn địa chỉ mạng nội bộ ở **từng lần chuyển hướng**, "
            "tôn trọng `robots.txt`, giới hạn kích thước và thời gian.\n\n"
            "Lỗi tra cứu **không** làm mất kết quả OCR.",
    },
    ("get", "/api/health"): {
        "summary": "Trạng thái ứng dụng và mức sẵn sàng của dịch vụ",
        "description":
            "Chỉ trả `true`/`false` cho từng mục cấu hình — **không bao giờ "
            "tiết lộ giá trị khóa**. Khóa `verified` là kết quả lần xác minh "
            "thật gần nhất (`null` nếu chưa chạy lần nào); đọc từ bộ nhớ, "
            "không gọi dịch vụ.",
    },
    ("get", "/api/scans"): {
        "summary": "Danh sách bản quét gần đây",
        "description":
            "`?limit=` (mặc định 12, tối đa 50). Kèm `full_name`, "
            "`company_name` đọc từ bản nháp và `image_ref` để hiện ảnh thu "
            "nhỏ — đủ để nhận ra thẻ mà không phải mở từng bản quét.",
    },
    ("get", "/api/scans/status"): {
        "summary": "Trạng thái của nhiều bản quét trong một lời gọi",
        "description":
            "`?ids=a,b,c` — dùng để theo dõi một lô đang chạy. Hỏi từng bản "
            "quét một sẽ nhân số lời gọi theo số ảnh và đụng giới hạn tần "
            "suất; endpoint này có chi phí không đổi theo số ảnh.\n\n"
            "Mã không tồn tại bị **bỏ qua** thay vì làm hỏng cả lô.",
    },
    ("post", "/api/readiness/verify"): {
        "summary": "Xác minh dịch vụ bằng lời gọi thật",
        "description":
            "Phân biệt **đã cấu hình** với **chạy được**: gọi thật nhà cung "
            "cấp OCR và bộ trích xuất đang bật, rồi nhớ kết quả cho "
            "`GET /api/health`.\n\n"
            "**Tốn hạn mức:** tối đa hai lời gọi dịch vụ mỗi lần. Tesseract "
            "kiểm cục bộ nên không tốn gì; Google Vision và Gemini thì có.",
    },
    ("get", "/api/stats"): {
        "summary": "Số liệu tổng quan cho bảng điều khiển",
        "description":
            "Tổng số bản quét/hồ sơ/doanh nghiệp, phân bố ngôn ngữ, điểm tin "
            "cậy trung bình, thống kê quyết định của tầng agentic, và hồ sơ "
            "tạo mới theo ngày trong 14 ngày gần nhất.",
    },
    ("get", "/api/contacts/{contact_id}"): {
        "summary": "Chi tiết một hồ sơ",
        "description":
            "Gồm toàn bộ giá trị đa trị, doanh nghiệp liên kết, thông tin tra "
            "cứu kèm nguồn, và liên kết ngược về bản quét gốc.",
    },
    ("patch", "/api/contacts/{contact_id}"): {
        "summary": "Cập nhật một hồ sơ đã lưu",
        "description":
            "Dùng khi sửa hồ sơ sau lúc lưu. Cũng cần `revision` để tránh hai "
            "người ghi đè lên nhau.",
    },
    ("get", "/api/contacts/{contact_id}/duplicates"): {
        "summary": "Hồ sơ khác có thể trùng với hồ sơ này",
        "description":
            "Dùng để rà soát kho hồ sơ đã có. Chỉ gợi ý, **không tự gộp** — "
            "hai người trùng tên là chuyện bình thường.",
    },
    ("patch", "/api/enrichments/{enrichment_id}"): {
        "summary": "Duyệt hoặc bác bỏ một khẳng định tra cứu",
        "description":
            "Người dùng quyết định giữ hay bỏ từng thông tin bổ sung. Dữ liệu "
            "tra cứu **không bao giờ tự ghi đè** thông tin đọc từ thẻ.",
    },
    ("get", "/api/images/{image_ref}"): {
        "summary": "Tải ảnh gốc của một bản quét",
        "description":
            "`image_ref` là SHA-256 của nội dung ảnh. Chỉ chấp nhận đúng 64 ký "
            "tự hex — không ghép chuỗi đường dẫn từ tham số đầu vào, nên không "
            "thể dùng để đọc file khác trên máy chủ.",
    },
    ("get", "/api/organizations"): {
        "summary": "Danh sách doanh nghiệp để chọn khi lưu hồ sơ",
        "description":
            "Dùng khi người dùng muốn gắn hồ sơ mới vào một doanh nghiệp đã có "
            "thay vì tạo bản ghi trùng.",
    },
    ("get", "/api/organizations/{organization_id}"): {
        "summary": "Chi tiết doanh nghiệp kèm thông tin đã tra cứu",
        "description":
            "Mỗi khẳng định có `status`: `verified`, `unverified`, "
            "`conflicting` (nhiều nguồn nói khác nhau) hoặc `not_found`.",
    },
    ("post", "/api/webhooks"): {
        "summary": "Đăng ký một URL nhận thông báo",
        "description":
            "**Mặc định tắt** (`WEBHOOK_ENABLED=false`). Đây là tính năng duy "
            "nhất gửi dữ liệu **ra ngoài** tới địa chỉ do người dùng nhập, mà "
            "API hiện chưa có xác thực — bất kỳ ai gọi được API đều có thể "
            "đăng ký một URL và nhận toàn bộ dữ liệu bản quét. Chỉ bật khi đã "
            "thêm xác thực hoặc chắc chắn chỉ chạy trong mạng nội bộ.\n\n"
            "URL được kiểm tra bằng cùng bộ chặn của bước tra cứu doanh "
            "nghiệp: chỉ http/https tới địa chỉ công khai, không nhận thông "
            "tin đăng nhập trong URL, không nhận cổng ngoài 80/443. Địa chỉ "
            "được **kiểm tra lại ở từng lần gửi**, vì tên miền có thể đổi sang "
            "địa chỉ nội bộ sau khi đăng ký.\n\n"
            "Khóa bí mật chỉ trả về **một lần duy nhất** ở phản hồi này. Bên "
            "nhận dùng nó để xác minh chữ ký `X-Signature-256` "
            "(HMAC-SHA256 của thân yêu cầu).",
    },
    ("get", "/api/webhooks"): {
        "summary": "Danh sách URL đã đăng ký",
        "description": "Không kèm khóa bí mật.",
    },
    ("patch", "/api/webhooks/{target_id}"): {
        "summary": "Bật hoặc tắt một webhook",
    },
    ("delete", "/api/webhooks/{target_id}"): {
        "summary": "Xoá một webhook",
    },
    ("post", "/api/scans/{scan_id}/enrich"): {
        "summary": "Tra cứu doanh nghiệp từ một bản quét",
        "description":
            "Tiện hơn so với việc tự tạo doanh nghiệp rồi gọi endpoint tra cứu "
            "— dùng luôn tên và tên miền trong bản nháp của bản quét này.",
    },
}

TAG_BY_PREFIX = [
    ("/api/scans", "scans"),
    ("/api/contacts", "contacts"),
    ("/api/organizations", "enrichment"),
    ("/api/enrichments", "enrichment"),
    ("/api/export", "contacts"),
    ("/api/webhooks", "webhooks"),
]


def _error_table() -> str:
    rows = ["", "### Mã lỗi", "",
            "Thân phản hồi lỗi luôn có dạng "
            "`{\"error\": {\"code\", \"message\", \"retryable\"}}`.", "",
            "| Mã | Ý nghĩa |", "| --- | --- |"]
    rows += [f"| `{code}` | {text} |" for code, text in ERROR_CODES.items()]
    return "\n".join(rows)


def _walk(routes):
    """Duyet het moi route, ke ca route nam trong router duoc include.

    FastAPI ban nay KHONG trai phang router duoc include vao `app.routes`:
    no dat mot doi tuong `_IncludedRouter` vao do, va cac route that nam trong
    `.original_router.routes`. Chi lap qua `app.routes` se bo sot toan bo
    endpoint cua `contact_routes.py` ma khong bao loi gi.
    """
    for route in routes:
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from _walk(included.routes)
        elif hasattr(route, "path"):
            yield route


def apply(app) -> None:
    """Gan mo ta vao schema OpenAPI da sinh.

    Lam sau khi dinh tuyen da khai bao xong, nen khong can sua tung decorator.
    Endpoint nao chua co mo ta thi giu nguyen - khong im lang ghi de.
    """
    app.description = DESCRIPTION + _error_table()
    app.openapi_tags = TAGS
    app.openapi_schema = None          # buoc sinh lai voi mo ta moi

    for route in _walk(app.routes):
        path = getattr(route, "path", "")
        if not path.startswith("/api"):
            continue

        for prefix, tag in TAG_BY_PREFIX:
            if path.startswith(prefix):
                route.tags = [tag]
                break
        else:
            route.tags = ["system"]

        for method in getattr(route, "methods", set()):
            doc = ENDPOINTS.get((method.lower(), path))
            if not doc:
                continue
            route.summary = doc["summary"]
            if doc.get("description"):
                route.description = doc["description"]
