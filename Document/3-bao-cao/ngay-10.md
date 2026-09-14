# Báo cáo Ngày 10 — Đóng gói và bàn giao

**Ngày thực hiện:** 14/09/2026
**Phạm vi:** mục Ngày 10 của [kế hoạch triển khai chi tiết](../2-ke-hoach/trien-khai-chi-tiet.md).

---

## 1. Kết quả

| Mục trong kế hoạch | Trạng thái |
| --- | --- |
| README: môi trường, cài đặt, biến cấu hình, tạo DB, chạy, kiểm thử, **giới hạn đã biết** | **Xong** — viết lại toàn bộ |
| Clone vào thư mục mới, làm theo README từ đầu | **Xong** — xem mục 2 |
| Kịch bản demo 5–7 phút | **Xong** — [ngay-10-demo.md](ngay-10-demo.md) |
| Báo cáo ngắn: đề bài → phạm vi → kiến trúc → quy tắc → kết quả → giới hạn | **Xong** — mục 4 |
| Câu trả lời cho 10 câu hỏi trình bày | **Xong** — mục 5 |
| Không thêm tính năng mới | **Tuân thủ** — chỉ sửa tài liệu và dọn rác |

---

## 2. Kiểm chứng từ bản sạch

Không chờ đến lúc bàn giao mới biết thiếu bước. Đã sao chép mã nguồn sang thư mục mới (loại `.venv`, `backend/data`, `backend/.env`, `datasets/_dryrun`, `reports`), rồi làm **đúng theo README, không dùng gì có sẵn trên máy**.

| Bước | Kết quả |
| --- | --- |
| `python -m venv .venv` | OK |
| Cài từ `backend/requirements.txt` + `frontend/requirements.txt` | OK, không lỗi phụ thuộc |
| `Copy-Item backend\.env.example backend\.env` | OK |
| `python -m pytest` | **313 pass** trong 52 giây |
| Khởi động backend | OK, `GET /api/health` trả 200 |
| Khởi động Streamlit | OK, trang phục vụ được |
| Cơ sở dữ liệu | **Tự tạo**, không cần lệnh migration |

### Ba vấn đề bàn giao tìm được

**a) Tải ảnh bất kỳ lên thì báo lỗi — trải nghiệm đầu tiên rất tệ.**

Mặc định `OCR_PROVIDER=mock`, tức phát lại kết quả OCR đã lưu theo mã băm của ảnh. Người mới clone về, tải một ảnh lên, nhận ngay:

```
FIXTURE_MISSING - Chua co fixture cho anh b170c30150c7
```

Người chấm sẽ tưởng ứng dụng hỏng. Đã thêm hẳn một mục trong README: chạy `make_card_sheets.py --crop` để sinh 40 thẻ hư cấu kèm bản ghi, rồi tải `datasets/_dryrun/dev/ja/001.jpg` lên là thấy trọn luồng. Đã kiểm chứng đường này chạy được trong bản sạch — trả về đúng tên công ty, email và hai số điện thoại.

**b) Thư mục `data/` rỗng nằm ở gốc dự án.**

Tàn dư từ lỗi đã sửa ở Ngày 2, khi `IMAGE_DIR=./data/images` còn được tính theo thư mục đang chạy thay vì theo `backend/`. `.gitignore` chỉ chặn `backend/data/` nên thư mục này không bị chặn. Đã xóa.

**c) `frontend/.streamlit/config.toml` từng là file chết.**

Streamlit đọc `.streamlit/config.toml` theo **thư mục đang chạy**, không theo vị trí file ứng dụng. README bảo chạy từ gốc repo, nên file cấu hình đặt trong `frontend/` không bao giờ được đọc — giới hạn tải lên 8 MB không hề có hiệu lực. File đã được chuyển về gốc từ trước; nay README ghi rõ lý do **phải chạy từ gốc dự án** để người sau không đặt lại nhầm chỗ.

---

## 3. README viết lại

README cũ là một bản nhật ký tích lũy theo ngày: bảy đoạn "Ngày N đã triển khai", số test cũ rải rác (73, 116, 174, 201) và số bảng cơ sở dữ liệu mâu thuẫn nhau (8, rồi 9, rồi 10). Nó trả lời câu hỏi *"dự án đã đi qua những gì"* trong khi người đọc README cần biết *"làm sao để chạy được"*.

Bản mới chỉ còn: chạy thế nào, cấu hình ra sao, kiểm thử bằng gì, **và giới hạn thật là gì**. Lịch sử theo ngày đã nằm sẵn trong `Document/3-bao-cao/`.

Mọi con số trong README mới đều lấy từ lần chạy thật trong bản sạch.

---

## 4. Báo cáo ngắn

### Đề bài

Sau hội thảo, người dùng có hàng chục đến hàng trăm danh thiếp. Nhập tay tốn thời gian và dễ sai; tra cứu doanh nghiệp phải làm riêng; dữ liệu lưu rải rác nên khó tìm lại và chia sẻ. Cần hệ thống chụp/scan danh thiếp, tự động trích xuất, tra cứu bổ sung từ nguồn công khai, tổng hợp thành hồ sơ đối tác chuẩn hóa.

### Phạm vi đã chọn

MVP là **tiếng Anh và tiếng Nhật**; mỗi ảnh một thẻ, một mặt, bố cục ngang. Đề gốc còn nêu tiếng Hàn và tiếng Trung — đó là hướng mở rộng, đã ghi rõ trong đặc tả chứ không lặng lẽ bỏ qua.

### Kiến trúc

Streamlit (giao diện) → FastAPI (backend) → SQLite, với Google Vision làm OCR và Gemini làm tầng trích xuất trường.

Streamlit chạy **phía máy chủ**, nên trình duyệt không bao giờ gọi thẳng tới Google: không có CORS, không có biến cấu hình nào gửi xuống trình duyệt, ảnh danh thiếp không phải phơi ra Internet.

Tách hai tầng OCR và trích xuất là quyết định quan trọng nhất: Vision đọc chữ (bằng chứng từ điểm ảnh), Gemini gán trường (mô hình sinh), rồi đối chiếu hai bên. Nếu để một mô hình làm cả hai việc thì nó tự chấm điểm chính mình.

### Quy tắc chuẩn hóa

Ranh giới rõ: **chuẩn hóa là sửa định dạng, không bao giờ là suy đoán nội dung.**

- Giữ tên nguyên bản; không đảo họ/tên, không phiên âm, không dịch
- Số điện thoại là chuỗi; không tự thêm `+81` chỉ vì thẻ có tiếng Nhật
- Email và URL chuẩn hóa để so khớp nhưng giữ giá trị gốc để đối chiếu
- Địa chỉ giữ nguyên xuống dòng và ký tự 〒
- Thiếu dữ liệu thì để trống, không suy đoán

### Kết quả

| | |
| --- | --- |
| Test tự động | **313 pass**, không gọi mạng thật |
| Endpoint API | 18 |
| Bảng cơ sở dữ liệu | 10 |
| Ma trận tình huống hỏng (Ngày 8) | 9/13 tự động, 3 cần thiết bị thật |
| Đo chất lượng OCR | **Chưa có số** |

### Giới hạn

**Chưa có lời gọi Google Vision hay Gemini nào trong toàn bộ dự án.** Mọi kiểm thử chạy trên provider giả lập. Câu hỏi trung tâm của đề — *hệ thống đọc đúng bao nhiêu phần trăm các trường trên một tấm danh thiếp tiếng Nhật* — chưa có câu trả lời.

Còn thiếu: 40 ảnh chụp thật (nhãn và trang in đã sẵn sàng), kiểm thử camera và HTTPS trên điện thoại, và đo chất lượng thật.

---

## 5. Mười câu hỏi khi trình bày

**1. Vì sao webcam chỉ giải quyết đầu vào?**
Nó lấy được ảnh, còn OCR, trích xuất trường, chuẩn hóa, tra cứu và lưu hồ sơ đều là việc riêng. Một màn hình hiện văn bản OCR thô chưa hoàn thành đề bài.

**2. OCR, trích xuất, chuẩn hóa, tra cứu khác nhau ở đâu?**
OCR đọc chữ từ ảnh. Trích xuất xác định chữ nào thuộc trường nào. Chuẩn hóa đưa về quy tắc thống nhất mà **không đổi nội dung**. Tra cứu là bước riêng, tìm thêm thông tin doanh nghiệp từ nguồn công khai.

**3. Chứng minh hỗ trợ tiếng Nhật bằng gì?**
Hiện chỉ chứng minh được phần kỹ thuật: Kanji đi qua lưu → tải lại → xuất JSON/CSV không đổi, có test riêng; tìm kiếm dùng NFKC nên chữ full-width khớp được với half-width. **Chưa chứng minh được chất lượng nhận diện** vì chưa chạy OCR thật.

**4. Vì sao giữ nguyên tên Nhật và dữ liệu OCR gốc?**
Phiên âm hay dịch là thêm thông tin không có trên thẻ. Còn dữ liệu OCR gốc là bằng chứng duy nhất để đối chiếu và để đo chất lượng trước khi người dùng sửa.

**5. Không đọc được email hoặc không tìm thấy doanh nghiệp thì sao?**
Để trống, không suy đoán. Tra cứu không có nguồn đủ tin cậy thì ghi "chưa tìm thấy" và **không đụng tới** kết quả OCR.

**6. Xác định đúng doanh nghiệp thế nào?**
Ưu tiên website in trên thẻ, rồi tới tên miền email công ty (loại email dịch vụ công cộng). Không có cả hai thì trả "chưa tìm thấy" — không đoán website từ tên công ty. Mỗi khẳng định phải kèm đoạn trích nguyên văn từ trang nguồn.

**7. Dữ liệu lưu ở đâu, còn sau khi khởi động lại không?**
SQLite ở `backend/data/app.db`, ảnh lưu theo SHA-256 trong `backend/data/images/`. Đã kiểm chứng: tắt backend, khởi động tiến trình khác, hồ sơ và khóa chống gửi lặp còn nguyên.

**8. Vì sao API key nằm ở backend?**
Streamlit chạy phía máy chủ, trình duyệt chỉ nói chuyện với Streamlit. Có `check_secrets.py` quét rò rỉ khóa theo hình dạng và trả mã thoát 1 để dùng trong CI.

**9. Chọn phiên bản OCR nào, thử ra sao?**
Google Cloud Vision `DOCUMENT_TEXT_DETECTION` + Gemini structured output. Không dùng Azure `prebuilt-businessCard` vì model đó đã ngừng phát triển từ API v4.0. **Chưa gọi thật lần nào** — nhưng có 17 test dựng lại đúng cấu trúc phản hồi của Vision để kiểm chứng phần đọc dữ liệu trước.

**10. Phần nào chưa làm và vì sao ưu tiên như vậy?**
Chưa có OCR thật và số đo chất lượng. Ưu tiên xây đủ luồng trước vì nó không phụ thuộc vào việc có API key hay không; nhưng phải nói thẳng là **đó là một sai lầm về thứ tự** — xem mục 6.

---

## 6. Điều cần nói thẳng

Theo kế hoạch 10 ngày, dự án đã đi hết cả 10 ngày về mặt hạng mục. Nhưng **Ngày 2 chưa bao giờ đạt**, và mọi ngày sau đó được xây trên nền đó.

Kế hoạch Ngày 2 ghi rõ: *"Nếu chưa đạt: ưu tiên giải quyết quyền truy cập... Có thể dùng response mẫu để tiếp tục dựng giao diện, nhưng không coi dữ liệu mô phỏng là đã hoàn thành OCR; nếu kéo dài phải điều chỉnh lịch/phạm vi."*

Thực tế: đã dùng dữ liệu mô phỏng suốt Ngày 3 đến Ngày 10, và lịch trình không được điều chỉnh. Hệ quả là ba thứ vẫn chưa ai biết đúng hay sai:

- Schema `CardExtraction` đã bao giờ được Gemini chấp nhận chưa
- Ngưỡng `_FUZZY_THRESHOLD = 0.90` có hợp với chữ Kanji thật không
- Nhánh tăng tương phản của tầng agentic có giúp được ảnh mờ thật không

Cái đã làm được để giảm thiệt hại: mọi đường đi tới dịch vụ thật đều có test dựng lại cấu trúc phản hồi thật, và có lệnh `try_ocr.py --check` xác nhận cấu hình bằng đúng hai lời gọi. Nên khi có API key, xác suất gặp lỗi bất ngờ đã thấp hơn nhiều.

Nhưng không thứ nào thay thế được việc chạy thật.

---

## 7. Việc còn lại

Theo đúng thứ tự:

1. **Lấy API key** → `try_ocr.py --check`
2. **In, cắt, chụp 40 thẻ** từ `datasets/print/` → `check_labels.py`
3. `evaluate.py --split dev` để sửa lỗi, rồi `--split eval` **một lần duy nhất** lấy số báo cáo
4. Làm nốt 3 dòng thủ công của Ngày 8: quyền camera, DevTools, HTTPS trên điện thoại
5. Cập nhật [báo cáo Ngày 9](ngay-9.md) bằng số thật

Chỉ sau bước 3 thì dự án mới thật sự trả lời được câu hỏi của đề bài.
