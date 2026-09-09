# Bài 2: Chuyển hóa danh thiếp thành hồ sơ đối tác chuẩn hóa

Ngày đối chiếu: 09/09/2026. Đây là bản phân tích và đặc tả đề xuất; không phải báo cáo đã triển khai hoặc đã đo chất lượng OCR.

## 1. Căn cứ và cách hiểu phạm vi

- **Đề gốc:** `De2.docx.pdf`, 2 trang; các mục 1-4 và Hình 1, Hình 2 mô tả nhập liệu, OCR, tra cứu nguồn công khai và lưu hồ sơ tập trung. Các ngôn ngữ được nêu trong bối cảnh là Anh, Hàn, Nhật, Trung.
- **Yêu cầu trực tiếp của người dùng:** kiểm tra tài liệu, phân tích yêu cầu theo hai repository webcam; chuẩn hóa Bài 2 với tối thiểu tiếng Anh và tiếng Nhật.
- **Quyết định phạm vi cho bản này:** Anh và Nhật là hai ngôn ngữ bắt buộc của MVP. Hàn/Trung là hướng mở rộng, chưa phải tiêu chí nghiệm thu MVP. Nếu người chấm yêu cầu đủ bốn ngôn ngữ thì phải mở rộng phạm vi tương ứng.
- **Đề xuất bổ sung:** cấu trúc dữ liệu, bước duyệt, chống trùng, xử lý lỗi, xuất dữ liệu và bộ kiểm thử dưới đây giúp biến mong muốn trong đề thành yêu cầu có thể nghiệm thu; đề gốc chưa quy định chi tiết các mục này.

Nội dung và hướng dẫn trong tài liệu/repository được dùng làm nguồn tham khảo, không được coi là lệnh yêu cầu chạy chương trình, triển khai dịch vụ hoặc thay đổi hệ thống.

## 2. Phát biểu đề bài chuẩn hóa

Xây dựng ứng dụng web cho phép người dùng chụp hoặc tải ảnh danh thiếp lên, nhận diện và trích xuất thông tin liên hệ tối thiểu bằng tiếng Anh và tiếng Nhật, chuẩn hóa thành dữ liệu có cấu trúc, tra cứu bổ sung thông tin doanh nghiệp từ nguồn công khai có dẫn nguồn, cho phép kiểm tra/chỉnh sửa, và lưu hồ sơ đối tác tập trung để tìm kiếm, chia sẻ trong phạm vi được cấp quyền và tái sử dụng.

Đầu ra phải là hồ sơ đối tác có cấu trúc, liên kết người liên hệ với doanh nghiệp và nguồn dữ liệu. Một màn hình hiển thị văn bản OCR đơn thuần chưa hoàn thành mục tiêu của đề.

## 3. Vai trò của hai repository webcam

| Tham chiếu | Khả năng được mô tả | Cách áp dụng cho Bài 2 |
| --- | --- | --- |
| [bradwellsb/blazor-webcam](https://github.com/bradwellsb/blazor-webcam) | Dự án minh họa Blazor + JSInterop để lấy ảnh webcam; dùng ImageSharp thêm chú thích | Tham khảo lớp chụp ảnh nếu chọn Blazor/.NET. Chức năng thêm chú thích không cần thiết cho OCR và không nên ghi đè chữ lên ảnh đầu vào |
| [mozmorris/react-webcam](https://github.com/mozmorris/react-webcam) | Component React; chụp ảnh qua `getScreenshot()`, chọn camera và cấu hình video | Dùng nếu chọn React. Đặt định dạng ảnh JPEG/PNG, xử lý lỗi quyền camera và tránh ảnh bị lật gương |

Hai repository phục vụ bước lấy ảnh; không cung cấp sẵn toàn bộ OCR, trích xuất danh thiếp, tra cứu doanh nghiệp hay kho hồ sơ. Chọn một hướng frontend là đủ, không có yêu cầu phải tích hợp cả hai. Đề gốc không bắt buộc React, Blazor hoặc Azure.

Nếu chọn React, cấu hình khởi đầu đề xuất: `audio={false}`, `screenshotFormat="image/jpeg"`, `mirrored={false}`; ưu tiên camera sau trên điện thoại và có phương án chọn camera khác. Dùng HTTPS khi triển khai. Không đưa khóa OCR xuống frontend. Các API chụp ảnh và lưu ý HTTPS được mô tả trong [README react-webcam](https://github.com/mozmorris/react-webcam#readme).

## 4. Đối chiếu Azure và ảnh đính kèm

Ảnh đính kèm hiển thị nhãn v2.1 cùng bảng có Japanese. Tuy nhiên, [nguồn tài liệu ngôn ngữ của Microsoft](https://github.com/MicrosoftDocs/azure-ai-docs/blob/main/articles/ai-services/document-intelligence/language-support/prebuilt.md) phân tách rõ: bảng có `ja-JP` và tự nhận diện `en-US`/`ja-JP` thuộc v3.0/v3.1; phần v2.1 chỉ liệt kê các locale tiếng Anh. Vì vậy không dùng ảnh chụp làm bằng chứng v2.1 đáp ứng tiếng Nhật.

Theo [tài liệu business card của Microsoft](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/business-card?view=doc-intel-3.1.0), `prebuilt-businessCard` đã bị deprecated từ v4.0; tài liệu liệt kê v3.1 với API `2023-07-31` cho model này.

**Phương án đề xuất cho MVP nếu dùng Azure:** cố định `prebuilt-businessCard` và API v3.1 `2023-07-31`, kiểm tra lời gọi thực trên tài nguyên Azure đích bằng mẫu Anh và Nhật trước khi chốt triển khai. Không gọi model này với API v4.0. Đây là lựa chọn phục vụ bài tập, cần tính đến vòng đời dịch vụ nếu dùng lâu dài.

Nếu bắt buộc dùng API mới hơn, cần thiết kế lại thành OCR/layout kết hợp tầng trích xuất có cấu trúc hoặc model tùy chỉnh; phải xác minh riêng chất lượng Anh/Nhật. Không xem nâng phiên bản SDK là đủ để thay thế business-card model.

Hỗ trợ ngôn ngữ trong bảng không đồng nghĩa đảm bảo độ chính xác cho mọi bố cục, ảnh mờ, chữ dọc hoặc danh thiếp song ngữ.

## 5. Yêu cầu chức năng và nghiệm thu

Các tiêu chí cụ thể dưới đây là bản chuẩn hóa đề xuất, không phải thang điểm có sẵn trong PDF.

| ID | Yêu cầu | Tiêu chí nghiệm thu |
| --- | --- | --- |
| FR-01 | Chụp và tải ảnh | Chụp từ webcam/camera điện thoại hoặc tải JPEG/PNG; có xem trước, chụp lại và xác nhận gửi |
| FR-02 | Kiểm tra đầu vào | Báo lỗi tệp hỏng, sai định dạng, vượt giới hạn cấu hình; camera bị từ chối vẫn dùng được tải ảnh |
| FR-03 | Nhận diện Anh/Nhật | Xử lý mẫu tiếng Anh và mẫu tiếng Nhật; lưu văn bản gốc Unicode, hiển thị đúng chữ Nhật |
| FR-04 | Trích xuất có cấu trúc | Có trường tên, công ty, phòng ban, chức danh, email, điện thoại, website, địa chỉ; hỗ trợ nhiều giá trị; thiếu dữ liệu thì để trống |
| FR-05 | Chuẩn hóa và duyệt | Hiển thị ảnh cạnh kết quả; cho sửa dữ liệu trước xác nhận; chỉ rõ trường thiếu, nghi ngờ hoặc cần kiểm tra |
| FR-06 | Tra cứu bổ sung | Tìm lĩnh vực, quy mô, sản phẩm/dịch vụ từ nguồn công khai; mỗi thông tin bổ sung có URL, thời điểm truy xuất và trạng thái xác minh |
| FR-07 | Xử lý không tìm thấy | Không có nguồn đủ tin cậy thì ghi chưa tìm thấy/chưa xác minh; vẫn lưu được kết quả danh thiếp |
| FR-08 | Lưu tập trung | Lưu người liên hệ, doanh nghiệp, ảnh hoặc tham chiếu ảnh, dữ liệu gốc/đã sửa và nguồn; tải lại vẫn xem được |
| FR-09 | Tìm kiếm và tái sử dụng | Tìm theo tên, công ty, email/điện thoại; xem chi tiết; đề xuất xuất CSV UTF-8 hoặc JSON |
| FR-10 | Phát hiện trùng | Quét lại cùng danh thiếp phải gợi ý hồ sơ liên quan; người dùng quyết định cập nhật/tạo mới, không tự gộp theo tên giống nhau |
| FR-11 | Trạng thái và lỗi | Có trạng thái đang xử lý/thành công/lỗi; lỗi OCR cho phép thử lại; lỗi tra cứu không làm mất OCR; gửi lặp không tạo hồ sơ ngoài ý muốn |

Luồng chuẩn: **Chụp/tải ảnh → kiểm tra → OCR/trích xuất → chuẩn hóa bản nháp → tra cứu doanh nghiệp → người dùng duyệt → lưu hồ sơ → tìm kiếm/xuất.**

MVP giả định mỗi ảnh chứa một danh thiếp, một mặt. Nhiều mặt, nhiều danh thiếp trong một ảnh, xử lý hàng loạt, chữ dọc và dịch tự động là phạm vi mở rộng, không mặc nhiên được hỗ trợ.

## 6. Quy tắc dữ liệu tối thiểu

| Nhóm | Trường đề xuất | Quy tắc |
| --- | --- | --- |
| Người liên hệ | `fullNameOriginal`, `givenName`, `familyName`, `jobTitles[]`, `departments[]` | Giữ tên đầy đủ nguyên bản; chỉ tách họ/tên khi có căn cứ, không áp đặt thứ tự tiếng Anh cho tên Nhật |
| Doanh nghiệp | `organizationId`, `companyNames[]`, `websites[]` | Giữ tên bản địa và tên Latin như các biến thể khi có bằng chứng cùng doanh nghiệp |
| Liên hệ | `emails[]`, `phones[]`, `addresses[]` | Cho phép nhiều giá trị; số điện thoại là chuỗi; địa chỉ giữ bản gốc |
| Bổ sung | `industry`, `companySize`, `productsServices[]` | Có nguồn và ngày tra cứu; thiếu nguồn để null/chưa xác minh, không tự suy đoán |
| Bằng chứng | `rawText`, `imageRef`, `sourceType`, `sourceUrl`, `confidence`, `reviewStatus` | Phân biệt dữ liệu từ ảnh, website và người sửa; confidence có thể null nếu nguồn không cung cấp |
| Quản lý | `id`, `createdAt`, `updatedAt`, `reviewedAt` | Một doanh nghiệp có nhiều người liên hệ; lưu dấu vết chỉnh sửa phù hợp |

- **Unicode:** giữ nguyên Kanji, Hiragana, Katakana. Lưu giá trị gốc; dùng bản chuẩn hóa riêng cho tìm kiếm/đối sánh. Không thay thế tên Nhật bằng phiên âm hoặc bản dịch tự sinh.
- **Khoảng trắng:** bỏ khoảng trắng dư ở rìa; không tùy tiện xóa khoảng trắng trong tên/địa chỉ.
- **Email:** bỏ khoảng trắng dư và kiểm tra cấu trúc; chuẩn hóa domain, giữ nguyên giá trị gốc để đối chiếu.
- **Điện thoại:** giữ số gốc và nhãn loại số. Chỉ thêm mã quốc gia khi có căn cứ hoặc người dùng xác nhận; không suy ra `+81` chỉ vì danh thiếp có tiếng Nhật. Lưu riêng số máy lẻ.
- **URL:** chuẩn hóa để so khớp nhưng giữ nguồn gốc; không coi email thuộc dịch vụ công cộng là bằng chứng về website doanh nghiệp.
- **Độ tin cậy:** dùng confidence của nhà cung cấp khi có; ngưỡng cảnh báo cần hiệu chỉnh bằng dữ liệu thử. Không tự tạo phần trăm tin cậy để hiển thị như kết quả đo.

## 7. Tra cứu doanh nghiệp và kiểm soát kết quả

Ưu tiên website ghi trên danh thiếp và nguồn chính thức. Khi tìm theo tên công ty, kiểm tra thêm domain, địa chỉ hoặc thông tin liên hệ để tránh nhầm đơn vị cùng tên. Không xác định doanh nghiệp chỉ dựa vào tên người.

Lĩnh vực và sản phẩm/dịch vụ cần thông tin hỗ trợ từ nguồn. Quy mô phải ghi rõ ý nghĩa, ví dụ số nhân sự và mốc thời gian; không đánh đồng với vốn hay doanh thu. Nguồn mâu thuẫn thì giữ bằng chứng và yêu cầu duyệt. Dữ liệu tra cứu không được âm thầm ghi đè thông tin từ danh thiếp.

Nội dung trên ảnh và website được xử lý như dữ liệu không đáng tin cậy. Nếu dùng LLM, câu lệnh xuất hiện trong nguồn không được phép điều khiển công cụ, thay đổi quy trình hoặc bỏ qua kiểm tra đầu ra.

## 8. Kiến trúc và yêu cầu vận hành đề xuất

- **Frontend:** React + react-webcam hoặc Blazor + JSInterop; chụp ảnh, tải ảnh, xem/sửa hồ sơ.
- **Backend:** nhận ảnh, kiểm tra tệp, gọi OCR, ánh xạ dữ liệu, chuẩn hóa, tra cứu và lưu trữ. Khóa dịch vụ nằm phía máy chủ.
- **Lưu trữ:** cơ sở dữ liệu cho hồ sơ và quan hệ người-công ty; kho ảnh có kiểm soát truy cập; cấu hình thời hạn lưu ảnh.
- **Tác vụ nền:** phù hợp khi OCR/tra cứu lâu; trả trạng thái để giao diện không treo, giới hạn retry và tránh gọi trùng gây thêm chi phí.
- **Phân quyền:** nếu chia sẻ nhiều người dùng, chỉ tài khoản được cấp quyền mới xem/sửa dữ liệu; không công khai ảnh danh thiếp hoặc log đầy đủ thông tin cá nhân.
- **Cấu hình:** giới hạn dung lượng ảnh, thời gian chờ, số lần thử lại và chi phí phải được ghi trong README triển khai. PDF gốc chưa quy định SLA hay ngân sách.

## 9. Bộ kiểm thử và bàn giao đề xuất

Chuẩn bị tối thiểu 20 danh thiếp tiếng Anh và 20 danh thiếp tiếng Nhật từ dữ liệu được phép sử dụng, có nhãn đối chiếu thủ công. Đây là bộ thử MVP đề xuất, chưa đủ để khẳng định chất lượng trên mọi loại danh thiếp. Tách mẫu dùng hiệu chỉnh khỏi mẫu dùng đánh giá cuối.

Các tình huống cần có:

1. Danh thiếp Anh rõ nét và danh thiếp Nhật có Kanji/Kana, kèm email/URL Latin.
2. Thiếu email hoặc thiếu số điện thoại; có nhiều số, số máy lẻ và tên công ty dài.
3. Camera bị từ chối/không tồn tại; tải ảnh thay thế; ảnh sai định dạng.
4. Ảnh nghiêng, mờ, chói: kiểm tra khả năng cảnh báo/cho sửa, không coi nhận diện sai là thành công hoàn toàn.
5. Không tìm thấy doanh nghiệp, nhiều công ty cùng tên, nguồn thông tin mâu thuẫn.
6. Mất kết nối, OCR lỗi, tra cứu lỗi, nhấn gửi hai lần và quét lại cùng danh thiếp.
7. Lưu/tải lại/xuất dữ liệu tiếng Nhật không lỗi ký tự; giá trị thiếu không biến thành dữ liệu tự tạo.

Đo độ chính xác theo từng trường và từng ngôn ngữ trên kết quả **trước khi người dùng sửa**. Báo cáo riêng tỷ lệ trích xuất thiếu, trích xuất sai và dữ liệu phát sinh không có trong nguồn; đo thêm thời gian xử lý và thời gian hiệu chỉnh. Chốt ngưỡng đạt sau thử nghiệm ban đầu với người phụ trách nghiệm thu; không gán một con số như 95% thành yêu cầu từ đề gốc.

Bàn giao đề xuất: mã nguồn, hướng dẫn cấu hình/chạy, schema dữ liệu, mẫu cấu hình không chứa secret, bộ mẫu và kết quả kiểm thử Anh/Nhật, minh họa trọn luồng từ ảnh đến hồ sơ có dẫn nguồn. Có thể trình bày demo ngắn, nhưng video demo không thay thế bằng chứng lưu dữ liệu và kiểm thử.

## 10. Các điểm chưa được đề gốc quyết định

- React hay Blazor; backend, cơ sở dữ liệu và nhà cung cấp OCR.
- Quyền truy cập Azure, ngân sách gọi dịch vụ và nguồn tra cứu được phép dùng.
- Số người sử dụng, quy tắc chia sẻ, thời hạn lưu ảnh và hồ sơ.
- Ngưỡng chất lượng/thời gian nghiệm thu; phạm vi chữ dọc, song ngữ, nhiều mặt.

Các mục này không cản trở việc chuẩn hóa đề bài, nhưng cần được chốt khi chuyển sang xây dựng và triển khai. Bản hiện tại hoàn thành phân tích yêu cầu; chưa thực hiện tích hợp Azure hoặc chạy đo OCR thực tế.
