# Tài liệu dự án

Chuyển hóa danh thiếp thành hồ sơ đối tác chuẩn hóa (Đề bài #2).
Mục lục này cập nhật ngày **14/09/2026**.

## Đọc theo thứ tự nào

| Bạn muốn biết | Đọc file |
| --- | --- |
| Đề bài gốc yêu cầu gì | [1-de-bai/De2.docx.pdf](1-de-bai/De2.docx.pdf) |
| Yêu cầu đã chuẩn hóa thành tiêu chí nghiệm thu (FR-01…FR-11) | [1-de-bai/yeu-cau-chuan-hoa.md](1-de-bai/yeu-cau-chuan-hoa.md) |
| Cách làm và thiết kế kỹ thuật | [2-ke-hoach/trien-khai-chi-tiet.md](2-ke-hoach/trien-khai-chi-tiet.md) |
| Vì sao kiến trúc lại là agentic | [2-ke-hoach/kien-truc-agentic.md](2-ke-hoach/kien-truc-agentic.md) |
| Đã làm được tới đâu | [3-bao-cao/](3-bao-cao/) — đọc từ `ngay-1-2.md` |
| Cái gì đã kiểm chứng thật, cái gì chưa | [4-kiem-chung/](4-kiem-chung/) |

---

## 1. Đề bài

| File | Nội dung |
| --- | --- |
| [De2.docx.pdf](1-de-bai/De2.docx.pdf) | Đề gốc, 2 trang. Nguồn sự thật duy nhất về phạm vi |
| [yeu-cau-chuan-hoa.md](1-de-bai/yeu-cau-chuan-hoa.md) | Phân tích đề, chốt FR-01…FR-11 và quy tắc dữ liệu |

## 2. Kế hoạch

| File | Nội dung | Trạng thái |
| --- | --- | --- |
| [ke-hoach-10-ngay.md](2-ke-hoach/ke-hoach-10-ngay.md) | Lịch trình 10 ngày ở mức mục tiêu | Đang theo |
| [trien-khai-chi-tiet.md](2-ke-hoach/trien-khai-chi-tiet.md) | Kiến trúc, schema DB, hợp đồng API, DoD từng ngày | Tài liệu kỹ thuật chính |
| [nang-cap-6-tieu-chi.md](2-ke-hoach/nang-cap-6-tieu-chi.md) | Kế hoạch mở rộng 12–29/09 theo 6 tiêu chí chấm | Đang theo, xem cảnh báo dưới |
| [kien-truc-agentic.md](2-ke-hoach/kien-truc-agentic.md) | Vì sao chia thành nhiều tác tử, mô hình quyết định, grounding như lớp an toàn | Mốc 20/09 |
| [roadmap.md](2-ke-hoach/roadmap.md) | Lộ trình v1.0 → v4.0, kèm điều kiện bắt đầu từng mốc | Mốc 20/09 |
| [nang-cap-ocr-mien-phi.md](2-ke-hoach/nang-cap-ocr-mien-phi.md) | Nâng cấp bằng công nghệ miễn phí: nhà cung cấp OCR thứ ba và CI | 21/09 |
| [san-sang-thuong-mai.md](2-ke-hoach/san-sang-thuong-mai.md) | Lộ trình từ "chạy được" tới "bán được": đa khách hàng, quyền xoá dữ liệu, tích hợp CRM | 21/09, chờ quyết định |

> **Mốc kế tiếp là 15/09 — OCR thật.** Mốc 12–14 đã xong hạng mục; 15/09 không phải việc lập trình mà là lấy credentials và chụp ảnh.

> **Cảnh báo về kế hoạch nâng cấp:** tài liệu đó tự ghi *"giả định bạn sẽ lấy được API key trước ngày 13/09"*. Hôm nay 14/09 vẫn chưa có key, nên giả định nền đã sai mà kế hoạch chưa được điều chỉnh. Mốc 15/09 (OCR thật) đang chặn toàn bộ Giai Đoạn 2 trở đi.

## 3. Báo cáo tiến độ

Mỗi báo cáo trả lời bốn câu: **làm gì → mục đích → cách làm → vì sao làm như vậy**.

| File | Phạm vi |
| --- | --- |
| [ngay-1-2.md](3-bao-cao/ngay-1-2.md) | Khung dự án, schema 8 bảng, đường đi OCR, grounding |
| [ngay-3.md](3-bao-cao/ngay-3.md) | Tiếp nhận ảnh: validate, EXIF, lưu theo SHA-256 |
| [ngay-4.md](3-bao-cao/ngay-4.md) | Nối OCR vào ứng dụng, tác vụ nền, bản nháp |
| [ngay-5.md](3-bao-cao/ngay-5.md) | Chuẩn hóa theo trường, form duyệt đa giá trị |
| [ngay-6.md](3-bao-cao/ngay-6.md) | Tra cứu doanh nghiệp có dẫn nguồn, chặn SSRF |
| [ngay-7.md](3-bao-cao/ngay-7.md) | Lưu hồ sơ, tìm kiếm, phát hiện trùng, xuất JSON/CSV |
| [ngay-8.md](3-bao-cao/ngay-8.md) | Ma trận 13 tình huống hỏng; 9/13 tự động, 3 chờ làm tay |
| [ngay-9.md](3-bao-cao/ngay-9.md) | Công cụ đo chất lượng đã xong; **chưa có số thật** vì thiếu OCR và ảnh |
| [ngay-10.md](3-bao-cao/ngay-10.md) | Đóng gói, kiểm chứng từ bản sạch, báo cáo bàn giao |
| [ngay-10-demo.md](3-bao-cao/ngay-10-demo.md) | Kịch bản demo 5–7 phút (bản cũ, giữ để đối chiếu) |
| [ngay-21-demo.md](3-bao-cao/ngay-21-demo.md) | **Kịch bản demo 7–10 phút** — bản đang dùng, kèm câu trả lời khi bị hỏi |
| [moc-15-09.md](3-bao-cao/moc-15-09.md) | Giảm rủi ro cho lần chạy OCR thật đầu tiên |
| [moc-16-19-09.md](3-bao-cao/moc-16-19-09.md) | Mở rộng ra 4 ngôn ngữ, test trọn hành trình, UX |
| [moc-20-22-09.md](3-bao-cao/moc-20-22-09.md) | Tài liệu kiến trúc, kịch bản demo, kiểm chứng bàn giao từ bản sạch |
| [moc-23-29-09.md](3-bao-cao/moc-23-29-09.md) | **Đăng nhập + phân quyền, kho ảnh, PWA + cắt viền, mạng lưới, hồi quy bàn giao** — kèm hai lỗ rò đã vá |
| [nang-cap-ocr-21-09.md](3-bao-cao/nang-cap-ocr-21-09.md) | Nâng cấp bằng công nghệ miễn phí: nhà cung cấp OCR thứ ba, model Gemini mới, CI năm cổng — kèm số đo |

Ngày 9 và 10 đã có báo cáo. Ngày 9 **chưa đạt Định nghĩa hoàn thành** — công cụ xong, thiếu số thật.

## 4. Kiểm chứng

Tách riêng khỏi báo cáo, vì đây là nơi ghi **cái gì đã thật sự chạy** chứ không phải cái gì đã viết xong.

| File | Nội dung |
| --- | --- |
| [ra-soat-ngay-1-2.md](4-kiem-chung/ra-soat-ngay-1-2.md) | Rà soát độc lập Ngày 1–2, đính chính báo cáo trước |
| [doi-chieu-ke-hoach-nang-cap.md](4-kiem-chung/doi-chieu-ke-hoach-nang-cap.md) | Đối chiếu kế hoạch nâng cấp với code |
| [ocr-provider-notes.md](4-kiem-chung/ocr-provider-notes.md) | Phiếu ghi chép nhà cung cấp OCR — mục B **đã điền 14/09**; C, D, F chờ Vision |
| `ket-qua-*.json` | Kết quả các lần kiểm tra tự động, có mốc thời gian |

---

## Trạng thái dự án — 14/09/2026

Số liệu dưới đây lấy trực tiếp từ mã nguồn, không chép lại từ báo cáo.

| Chỉ số | Giá trị |
| --- | --- |
| Test | 679 test — 499 pass, 1 tự bỏ qua (cần Tesseract) |
| Endpoint API | 24 (20 đường dẫn), tất cả có mô tả OpenAPI |
| Bảng cơ sở dữ liệu | 10 |
| Nhãn chuẩn sẵn sàng | 40 (20 Anh + 20 Nhật) |

### Đã xong

Ngày 1–7 của kế hoạch gốc: khung dự án, schema, tiếp nhận ảnh, OCR + trích xuất + grounding, chuẩn hóa và màn hình duyệt, tra cứu doanh nghiệp có dẫn nguồn, lưu/tìm kiếm/chống trùng/xuất dữ liệu.

**Mốc 12, 13 và 14/09 của kế hoạch nâng cấp đã đủ hạng mục.** Điều phối agentic có nhánh rẽ thật (ảnh mờ thì dừng, OCR điểm thấp thì thử lại với ảnh tăng tương phản, thiếu tên/công ty thì đọc lại bằng prompt khác) với ngân sách retry có giới hạn; chấm điểm tin cậy theo từng trường với đủ 4 tín hiệu; xử lý hàng loạt chạy song song có giới hạn; trang **Tổng quan**.

**Công cụ cho Ngày 9 đã sẵn sàng dù chưa có ảnh:**

| Công cụ | Việc nó làm |
| --- | --- |
| `backend/scripts/make_card_sheets.py` | Sinh 4 trang A4 gồm 40 danh thiếp hư cấu + 40 nhãn chuẩn. In, cắt, chụp là có bộ mẫu |
| `backend/scripts/evaluate.py` | Đo chất lượng theo từng trường và từng ngôn ngữ, xuất `reports/evaluation.md` |
| `backend/app/services/evaluation.py` | Quy tắc so sánh, **chốt trước khi đo** và có 18 test khóa lại |
| `POST /api/readiness/verify` | Xác minh dịch vụ bằng đúng 2 lời gọi thật, kết quả nhớ lại cho `/api/health` |
| `backend/scripts/check_secrets.py` | Quét rò rỉ khóa theo hình dạng, không theo từ khóa; dùng được trong CI |

Chạy thử toàn bộ đường đo mà chưa cần ảnh chụp:

```powershell
.\.venv\Scripts\python.exe backend\scripts\make_card_sheets.py --crop
.\.venv\Scripts\python.exe backend\scripts\evaluate.py --split dev --dataset datasets/_dryrun
```

### Chưa xong

| Hạng mục | Ghi chú |
| --- | --- |
| **Google Vision** | Chưa có một lời gọi thật nào. Thiếu `backend/secrets/gcp-sa.json` |
| **Ảnh chụp** | 0/40 — nhãn và trang in đã sẵn sàng, còn thiếu bước in và chụp |
| Ngày 8 — 3 dòng còn lại | Quyền camera, DevTools, HTTPS trên điện thoại — cần trình duyệt và thiết bị thật |
| `Document/3-bao-cao/chat-luong.md` | Chỉ viết được sau khi có OCR thật |

### Điều quan trọng nhất

**Toàn bộ Ngày 3–7 được xây trên hai fixture tổng hợp.** Hai file trong `backend/tests/fixtures/ocr/` mang nhãn `provider: "synthetic"` — sinh từ văn bản viết tay ở Ngày 2, không phải kết quả OCR.

679 test xanh chứng minh mã nguồn tự nhất quán. Nó **không** chứng minh OCR đọc được danh thiếp tiếng Nhật.

**Ngày 14/09 đã gạch được một gạch đầu dòng:** schema `CardExtraction` *đã* được Gemini chấp nhận — `gemini-3.5-flash`, gọi thật, trả về đúng `山田 太郎` và email. Đây là lần đầu dự án chạm tới một dịch vụ thật. Chi tiết ở [4-kiem-chung/ocr-provider-notes.md](4-kiem-chung/ocr-provider-notes.md) mục B.

Còn **hai** thứ chưa từng được kiểm chứng, cả hai đều cần ảnh chụp thật: ngưỡng `_FUZZY_THRESHOLD = 0.90` của grounding có đúng với chữ Kanji thật không, và nhánh tăng tương phản của agent có hoạt động trên ảnh mờ thật không.

Phần **đọc phản hồi của Vision** thì nay đã kiểm chứng được mà không cần gọi thật: 17 test dựng lại đúng cấu trúc trang → khối → đoạn → từ → ký tự mà Vision trả về, gồm cả cờ ngắt dòng. Trước đó vùng code này chưa từng chạy dòng nào.

Càng xây thêm trước khi chạy thật thì càng nhiều mã nguồn phải sửa lại sau.

---

## Quy ước đặt tên

- Thư mục đánh số theo thứ tự đọc: đề bài → kế hoạch → báo cáo → kiểm chứng.
- Tên file tiếng Việt không dấu, kebab-case.
- Báo cáo theo ngày: `ngay-N.md`. Kết quả kiểm tra tự động: `ket-qua-*.json`.
- Trong tài liệu dùng **đường dẫn tương đối**, không dùng `file:///c:/...` — đường dẫn tuyệt đối hỏng ngay khi người khác mở repo.
