# Bài 2: Nội dung đề bài và kế hoạch hoàn thành trong 10 ngày

> **Cập nhật triển khai 11/09/2026:** Dự án thực tế đã chọn Streamlit + FastAPI + SQLite, Google Vision + Gemini. Các đoạn React/Blazor/Azure bên dưới là lựa chọn tham khảo ban đầu; mục tiêu theo ngày vẫn giữ nguyên. Khi học frontend, ưu tiên Streamlit `session_state`, `form`, `fragment`, camera/upload; backend học FastAPI, Pydantic, SQLAlchemy và httpx. Xem [rà soát Ngày 1–2](../4-kiem-chung/ra-soat-ngay-1-2.md) để biết phần đã đạt và việc còn thiếu.

## 1. Hiểu đúng bài tập cần hoàn thành

**Tên đề bài:** Chuyển hóa danh thiếp thành dữ liệu đối tác chuẩn hóa.

**Vấn đề thực tế:** Sau hội thảo hoặc sự kiện, người dùng có nhiều danh thiếp. Nhập thông tin bằng tay mất thời gian, dễ sai; việc tìm hiểu doanh nghiệp phải làm riêng; dữ liệu lưu rải rác nên khó tìm lại và sử dụng chung.

**Sản phẩm cần xây dựng:** Một ứng dụng web cho phép chụp hoặc tải ảnh danh thiếp, trích xuất thông tin, chuẩn hóa dữ liệu, tra cứu thêm thông tin doanh nghiệp từ nguồn công khai và lưu thành hồ sơ có thể tìm kiếm, chỉnh sửa, tái sử dụng.

**Phạm vi ngôn ngữ:** Bắt buộc có tiếng Anh và tiếng Nhật theo yêu cầu hiện tại. Đề gốc còn nêu tiếng Hàn và tiếng Trung trong bối cảnh; kế hoạch 10 ngày này chưa triển khai hai ngôn ngữ đó.

Luồng sử dụng cần hoàn thành:

```text
Chụp hoặc tải ảnh danh thiếp
→ Xem trước và xác nhận ảnh
→ OCR và trích xuất các trường thông tin
→ Chuẩn hóa thành bản nháp
→ Tra cứu bổ sung thông tin doanh nghiệp, kèm nguồn
→ Người dùng kiểm tra và chỉnh sửa
→ Lưu hồ sơ tập trung
→ Tìm lại, cập nhật và xuất dữ liệu
```

### Phân biệt ba công việc dễ bị nhầm

| Công việc | Ý nghĩa | Ví dụ |
| --- | --- | --- |
| OCR | Đọc chữ từ ảnh | Đọc được `山田 太郎`, tên công ty, email |
| Trích xuất | Xác định chữ nào thuộc trường nào | Đưa `山田 太郎` vào trường họ tên, email vào danh sách email |
| Chuẩn hóa | Đưa dữ liệu về cấu trúc và quy tắc thống nhất | Giữ tên gốc, bỏ khoảng trắng dư ở email, lưu nhiều số điện thoại thành danh sách |

Tra cứu doanh nghiệp là bước riêng: tìm lĩnh vực, quy mô và sản phẩm/dịch vụ từ nguồn công khai. Một màn hình trả về văn bản OCR chưa hoàn thành bài tập này.

### Những chức năng cần có trong bản hoàn thành

- Chụp danh thiếp bằng camera hoặc tải ảnh JPEG/PNG; xem trước và chụp lại.
- Nhận diện danh thiếp tiếng Anh và tiếng Nhật.
- Trích xuất tên, công ty, phòng ban, chức danh, email, điện thoại, website và địa chỉ khi có trên ảnh.
- Cho người dùng sửa kết quả; không tự điền dữ liệu không đọc được.
- Tra cứu thông tin doanh nghiệp; lưu URL nguồn và thời điểm tra cứu.
- Lưu hồ sơ bền vững phía máy chủ; có danh sách, tìm kiếm và trang chi tiết.
- Xử lý được lỗi camera, OCR và tra cứu mà không làm mất dữ liệu đã có.

**Bổ sung để bài làm dễ kiểm chứng:** xuất JSON hoặc CSV UTF-8, cảnh báo hồ sơ có thể trùng và báo cáo kiểm thử. Đây là đề xuất triển khai, không phải thang điểm được ghi sẵn trong đề gốc.

### Giới hạn chủ động trong 10 ngày

Mỗi lần xử lý một ảnh, một danh thiếp, một mặt; tập trung danh thiếp in rõ, bố cục ngang thông thường. Chưa làm nhận diện nhiều thẻ trong một ảnh, xử lý hàng loạt, dịch tự động, chữ dọc nâng cao, ứng dụng di động riêng hoặc tự huấn luyện model.

## 2. Cách tổ chức công việc để kịp 10 ngày

Kế hoạch giả định một người thực hiện khoảng **5-6 giờ tập trung mỗi ngày**, đã biết lập trình cơ bản và có thể dùng dịch vụ OCR. Tổng thời gian dự kiến 50-60 giờ, không phải cam kết mọi người mới bắt đầu đều hoàn thành trong thời lượng này.

Mỗi ngày chia thành: khoảng 1 giờ học đúng phần sắp dùng, 3-4 giờ thực hành và 1 giờ kiểm thử/ghi chép. Nếu đã biết nội dung học, chuyển thời gian đó sang làm bài. Không học toàn bộ một framework trước khi bắt đầu sản phẩm.

**Chọn công nghệ vào ngày 1 và giữ ổn định:**

| Điều kiện của bạn | Hướng triển khai |
| --- | --- |
| Đã quen JavaScript/TypeScript | React + react-webcam; backend Node.js/Express; SQLite cho bản demo chạy một máy chủ |
| Đã quen C#/.NET | Blazor + JSInterop; backend ASP.NET Core; SQLite cho bản demo chạy một máy chủ |

Các đầu việc dưới đây dùng React để minh họa. Nếu chọn Blazor, thay kiến thức component/hooks bằng component Razor, binding và JSInterop; các phần OCR, dữ liệu, tra cứu và kiểm thử giữ nguyên mục tiêu.

SQLite được đặt ở backend, không đặt trong từng trình duyệt. Nếu nơi triển khai không lưu được tệp bền vững, cần cơ sở dữ liệu bên ngoài hoặc chọn demo trên máy chủ có ổ lưu bền vững.

**Hai repository chỉ hỗ trợ phần camera:** [react-webcam](https://github.com/mozmorris/react-webcam) dành cho React; [blazor-webcam](https://github.com/bradwellsb/blazor-webcam) là ví dụ Blazor/JSInterop. Không cần học hoặc tích hợp cả hai.

**Lựa chọn OCR phải được thử sớm:** Nếu dùng Azure theo tài liệu đã đối chiếu, thử `prebuilt-businessCard` với API v3.1 `2023-07-31`. Model này đã deprecated từ v4.0, không ghép nó với API v4.0. Kiểm tra lời gọi thực và mẫu Anh/Nhật ở ngày 2; không chờ đến khi giao diện hoàn thiện mới kiểm tra dịch vụ. Tham khảo [model business card](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/business-card?view=doc-intel-3.1.0) và [phạm vi ngôn ngữ theo phiên bản](https://github.com/MicrosoftDocs/azure-ai-docs/blob/main/articles/ai-services/document-intelligence/language-support/prebuilt.md).

## 3. Những kiến thức cần học và mức cần nắm

| Kiến thức | Cần nắm đến đâu để làm bài | Dùng vào ngày |
| --- | --- | --- |
| Frontend cơ bản | Component, state, form, sự kiện, hiển thị danh sách và trạng thái tải/lỗi | 1, 3, 5, 7 |
| HTTP và bất đồng bộ | Request/response, JSON, POST/GET/PATCH, mã lỗi, `async/await`, timeout | 2-4, 6-7 |
| Xử lý ảnh trên web | File, Blob, FormData, ảnh base64/data URL, quyền camera, ảnh lật gương | 3 |
| Backend | Tạo API, kiểm tra dữ liệu đầu vào, gọi dịch vụ bên ngoài, cấu hình biến môi trường | 1-4 |
| OCR và trích xuất | Văn bản thô khác dữ liệu có cấu trúc; confidence không đảm bảo đúng; ánh xạ response vào schema riêng | 2, 4 |
| Unicode và tiếng Nhật | Lưu/hiển thị đúng chữ Nhật; giữ tên nguyên bản; không áp dụng thứ tự họ/tên tiếng Anh cho tên Nhật | 4-5, 9 |
| Chuẩn hóa và validation | Phân biệt sửa định dạng với suy đoán nội dung; giữ dữ liệu gốc; giá trị thiếu; nhiều email/số điện thoại | 4-5 |
| Cơ sở dữ liệu | Khóa chính, khóa ngoại, quan hệ một-nhiều, CRUD, truy vấn tìm kiếm và lưu bền vững | 1, 7 |
| Tra cứu và bằng chứng | Xác định đúng doanh nghiệp, nguồn chính thức, URL nguồn, thời điểm truy xuất, xử lý thông tin mâu thuẫn | 2, 6 |
| Kiểm soát LLM nếu sử dụng | Đầu ra theo schema, không bịa trường thiếu, kiểm tra kết quả; nội dung nguồn không phải lệnh điều khiển | 6 |
| Kiểm thử | Dữ liệu chuẩn đối chiếu, trường hợp lỗi, đo trước khi sửa tay, tách mẫu phát triển và đánh giá | 1, 8-9 |
| Vận hành tối thiểu | Không lộ API key, HTTPS cho camera khi triển khai, giới hạn tệp, quyền truy cập hồ sơ | 2-3, 8, 10 |

Không cần học sâu mạng neural, huấn luyện OCR, microservices, Kubernetes hoặc một hệ thống CRM đầy đủ để hoàn thành phạm vi này.

## 4. Kế hoạch chi tiết từng ngày

### Ngày 1: Chốt phạm vi, thiết kế dữ liệu và dựng khung dự án

**Học và nắm rõ:** Luồng frontend → backend → dịch vụ OCR → cơ sở dữ liệu; cấu trúc JSON; quan hệ một doanh nghiệp có nhiều người liên hệ.

**Việc phải làm:**

1. Viết checklist chức năng theo mục 1; ghi các phần chưa làm trong 10 ngày.
2. Chọn React hoặc Blazor theo nền tảng đã biết; tạo dự án và quản lý bằng Git.
3. Phác thảo ba màn hình: nhập ảnh, xem/sửa kết quả, danh sách/chi tiết hồ sơ.
4. Xác định schema tối thiểu theo mục 5 bên dưới trước khi nối OCR.
5. Chuẩn bị dần 20 mẫu Anh và 20 mẫu Nhật được phép sử dụng; chia mỗi ngôn ngữ thành 10 mẫu phát triển và 10 mẫu đánh giá giữ riêng.
6. Ghi nhãn đúng từ ảnh: tên, công ty, email, số điện thoại… Nhờ người đọc được tiếng Nhật kiểm tra những trường bạn không chắc; không dùng chính kết quả OCR làm đáp án chuẩn.

**Vì sao làm:** Phạm vi và cấu trúc dữ liệu rõ giúp tránh dựng giao diện xong mới phát hiện thiếu phần tra cứu hoặc không lưu được nhiều số điện thoại.

**Kết quả cuối ngày:** Dự án chạy, backend trả được phản hồi đơn giản, có schema nháp, phác thảo màn hình và danh sách mẫu kiểm thử.

### Ngày 2: Chứng minh OCR Anh/Nhật hoạt động và chốt nguồn tra cứu

**Học và nắm rõ:** Gọi REST API, xác thực bằng key phía máy chủ, gửi ảnh, đọc JSON, xử lý tác vụ bất đồng bộ và nhận biết sai phiên bản model.

**Việc phải làm:**

1. Cấu hình dịch vụ OCR ở backend bằng biến môi trường; tạo tệp cấu hình mẫu không chứa khóa thật.
2. Viết script hoặc API thử độc lập; gửi ít nhất 2 ảnh Anh và 2 ảnh Nhật rõ nét.
3. Lưu phản hồi để xem model trả những trường nào, dữ liệu dạng đơn hay danh sách, trường nào bị thiếu/sai.
4. Xác nhận chữ Nhật đi qua backend mà không lỗi mã hóa.
5. Kiểm tra khả năng truy cập nguồn tra cứu: website doanh nghiệp trên danh thiếp và một dịch vụ tìm kiếm có quyền sử dụng nếu cần tìm theo tên.
6. Ghi lại nhà cung cấp, phiên bản, cách cấu hình, giới hạn và chi phí cần theo dõi.

**Vì sao làm:** OCR và quyền truy cập dịch vụ là hai phụ thuộc có thể làm hỏng toàn bộ lịch trình. Phải biết chúng hoạt động trước khi đầu tư nhiều vào giao diện.

**Kết quả cuối ngày:** Có bằng chứng OCR thực cho cả hai ngôn ngữ và có phương án tra cứu khả thi.

**Nếu chưa đạt:** Ưu tiên giải quyết quyền truy cập hoặc thử một phương án OCR/trích xuất khác trên cùng mẫu. Có thể dùng response mẫu để tiếp tục dựng giao diện, nhưng không coi dữ liệu mô phỏng là đã hoàn thành OCR; nếu kéo dài phải điều chỉnh lịch/phạm vi, không che phần thiếu bằng demo giả.

### Ngày 3: Hoàn thành chụp ảnh, tải ảnh và gửi lên backend

**Học và nắm rõ:** Component/state; camera permission; `getScreenshot()` hoặc JSInterop; File/Blob/FormData; ảnh hiển thị và ảnh thực gửi đi có thể khác nhau.

**Việc phải làm:**

1. Tích hợp camera theo repository tương ứng; tắt âm thanh vì bài này chỉ cần ảnh.
2. Thêm tải ảnh JPEG/PNG để sử dụng khi không có camera.
3. Làm xem trước, chụp lại, xác nhận và nút gửi ảnh.
4. Gửi ảnh tới backend; kiểm tra tệp thật, định dạng và giới hạn dung lượng ở backend.
5. Có thông báo khi camera bị từ chối hoặc không có thiết bị; kiểm tra ảnh không bị lật chữ.

**Vì sao làm:** Ảnh đầu vào quyết định chất lượng OCR; đường tải ảnh giúp ứng dụng vẫn dùng được khi camera không hoạt động.

**Kết quả cuối ngày:** Cả ảnh chụp và ảnh tải lên đều đến được backend; người dùng biết cần làm gì khi gặp lỗi.

### Ngày 4: Nối OCR vào ứng dụng và trả dữ liệu theo schema riêng

**Học và nắm rõ:** Ánh xạ dữ liệu, null/danh sách rỗng, phân biệt dữ liệu nhà cung cấp và dữ liệu ứng dụng; trạng thái đang xử lý/thành công/lỗi.

**Việc phải làm:**

1. Nối đầu vào ngày 3 với lời gọi OCR đã kiểm chứng ngày 2.
2. Tạo hàm ánh xạ response OCR sang schema chung của ứng dụng.
3. Trích xuất các trường có trên ảnh; giữ văn bản gốc và confidence nếu dịch vụ cung cấp.
4. Cho phép nhiều email/số điện thoại; trường không có thì để trống.
5. Hiển thị kết quả trên màn hình; xử lý timeout/lỗi OCR và cho thử lại.

**Vì sao làm:** Schema riêng giúp phần lưu trữ và giao diện không bị phụ thuộc hoàn toàn vào định dạng của một dịch vụ OCR.

**Kết quả cuối ngày:** Người dùng gửi ảnh Anh hoặc Nhật và thấy các trường thông tin thực được trích xuất trong ứng dụng.

### Ngày 5: Chuẩn hóa dữ liệu và làm màn hình kiểm tra/chỉnh sửa

**Học và nắm rõ:** Validation khác normalization; Unicode; tên Nhật; định dạng email, điện thoại và URL; lưu giá trị gốc bên cạnh giá trị đã sửa.

**Việc phải làm:**

1. Viết các hàm chuẩn hóa nhỏ: bỏ khoảng trắng dư ở rìa, kiểm tra email/URL, giữ số điện thoại dưới dạng chuỗi.
2. Giữ tên Nhật nguyên bản; không tự đảo họ/tên, dịch tên hoặc thêm `+81` chỉ dựa vào ngôn ngữ.
3. Hiển thị ảnh cạnh form để đối chiếu; hỗ trợ thêm/sửa/xóa phần tử trong danh sách liên hệ.
4. Đánh dấu trường thiếu hoặc cần kiểm tra; nếu dùng confidence thì ghi nhận đây là tín hiệu hỗ trợ, không phải kết luận đúng/sai.
5. Kiểm thử các quy tắc bằng trường hợp thực: thiếu trường, nhiều số, số máy lẻ, khoảng trắng và ký tự Nhật.

**Vì sao làm:** OCR sẽ có sai sót. Bước duyệt làm cho hồ sơ cuối cùng có thể sử dụng, đồng thời thể hiện đúng yêu cầu “chuẩn hóa”.

**Kết quả cuối ngày:** Có form sửa hoàn chỉnh, dữ liệu gốc còn giữ được và các quy tắc chuẩn hóa không làm mất nội dung.

### Ngày 6: Tự động tra cứu bổ sung thông tin doanh nghiệp

**Học và nắm rõ:** Ghép đúng doanh nghiệp, đọc nội dung công khai, nguồn dữ liệu, xử lý không tìm thấy. Nếu dùng LLM, học cách yêu cầu đầu ra có cấu trúc và kiểm tra thông tin bằng nguồn.

**Việc phải làm:**

1. Ưu tiên website trên danh thiếp; nếu không có, dùng công cụ/API tìm kiếm đã chốt để tìm theo tên công ty kèm địa chỉ hoặc domain liên quan.
2. Đối chiếu tên/domain/địa chỉ; trường hợp không rõ thì đưa các ứng viên để người dùng chọn, không tự chọn công ty chỉ vì trùng tên.
3. Giới hạn việc đọc vào một số trang công khai liên quan như giới thiệu, sản phẩm, hồ sơ công ty; không xây crawler toàn Internet.
4. Trích xuất lĩnh vực, quy mô và sản phẩm/dịch vụ khi nguồn có thông tin; quy mô cần ghi rõ là nhân sự hay chỉ số nào và mốc thời gian nếu có.
5. Lưu URL, thời điểm và đoạn bằng chứng ngắn cho từng thông tin bổ sung; thiếu nguồn thì để chưa tìm thấy/chưa xác minh.
6. Hiển thị thông tin bổ sung để duyệt; lỗi tra cứu không xóa kết quả OCR.
7. Khi backend đọc URL, chỉ cho phép địa chỉ web công khai hợp lệ, chặn mạng nội bộ và giới hạn thời gian/dung lượng tải. Không để nội dung nguồn điều khiển các công cụ của LLM.

**Vì sao làm:** Đề bài yêu cầu làm giàu hồ sơ đối tác. Có dẫn nguồn giúp người dùng kiểm chứng và tránh đưa thông tin của doanh nghiệp khác vào hồ sơ.

**Kết quả cuối ngày:** Có ít nhất một ví dụ doanh nghiệp được bổ sung tự động có nguồn và một ví dụ không tìm thấy được xử lý đúng. Chỉ đặt một liên kết tìm kiếm cho người dùng tự tra cứu chưa hoàn thành bước này.

### Ngày 7: Lưu tập trung, tìm kiếm và tái sử dụng hồ sơ

**Học và nắm rõ:** CRUD, quan hệ người liên hệ-doanh nghiệp, lưu bền vững, truy vấn tìm kiếm và đối sánh hồ sơ trùng.

**Việc phải làm:**

1. Tạo bảng doanh nghiệp, người liên hệ, bản quét và thông tin bổ sung/nguồn theo schema đã chốt.
2. Làm API lưu bản nháp đã duyệt và cập nhật hồ sơ; dùng transaction khi nhiều thao tác phải thành công cùng nhau.
3. Làm danh sách, tìm kiếm theo tên/công ty/email và trang chi tiết.
4. Gợi ý trùng từ email/số điện thoại kết hợp thông tin khác; để người dùng quyết định cập nhật hay tạo mới.
5. Làm xuất JSON trước; thêm CSV UTF-8 nếu còn thời gian và kiểm tra giữ đúng chữ Nhật.
6. Tắt và khởi động lại ứng dụng để xác nhận hồ sơ vẫn tồn tại.

**Vì sao làm:** Đây là bước biến kết quả nhận diện tạm thời thành kho dữ liệu có thể tìm lại và tái sử dụng.

**Kết quả cuối ngày:** Hoàn thành trọn luồng từ ảnh đến hồ sơ lưu thật, tìm lại được và xuất được dữ liệu.

### Ngày 8: Kiểm thử tích hợp và xử lý các trường hợp hỏng

**Học và nắm rõ:** Kiểm thử trọn luồng, trạng thái lỗi, thử lại có giới hạn, chống gửi trùng và phân quyền tối thiểu nếu có nhiều người dùng.

**Việc phải làm:**

1. Chạy toàn bộ luồng với các mẫu phát triển Anh/Nhật.
2. Thử camera bị từ chối, tệp sai định dạng, ảnh mờ, OCR lỗi, mạng ngắt và tra cứu không có kết quả.
3. Thử nhấn gửi/lưu hai lần; tránh tạo hồ sơ trùng do cùng một yêu cầu bị gửi lại.
4. Kiểm tra khóa dịch vụ không xuất hiện trong frontend, repository hoặc log; kiểm tra quyền xem hồ sơ theo phạm vi demo.
5. Kiểm tra trên trình duyệt/máy sẽ dùng để trình bày, thử camera điện thoại qua HTTPS nếu cần.
6. Sửa lỗi theo thứ tự: mất dữ liệu → hỏng luồng chính → sai dữ liệu → khó sử dụng → hình thức.

**Vì sao làm:** Một demo chạy được đúng một lần chưa chứng minh ứng dụng đáp ứng yêu cầu sử dụng thực tế.

**Kết quả cuối ngày:** Luồng chính ổn định, lỗi có thông báo và đường tiếp tục; không còn lỗi làm mất hồ sơ hoặc không lưu được.

### Ngày 9: Đo chất lượng và hoàn thiện bằng chứng kết quả

**Học và nắm rõ:** Nhãn chuẩn, độ chính xác theo trường/ngôn ngữ, đo trước khi sửa tay và phân biệt chất lượng tự động với chất lượng sau người dùng duyệt.

**Việc phải làm:**

1. Hoàn thiện nhãn chuẩn; chạy 10 mẫu Anh và 10 mẫu Nhật đã giữ riêng để đánh giá.
2. Lưu kết quả tự động trước khi chỉnh sửa; đối chiếu từng trường với đáp án từ ảnh.
3. Báo cáo riêng tên, công ty, email, điện thoại, địa chỉ theo hai ngôn ngữ; ghi số đúng, sai, bỏ sót và tự sinh thông tin không có trên ảnh.
4. Ghi thời gian OCR, tra cứu, tổng xử lý và thời gian sửa tay; nêu điều kiện đo.
5. Kiểm tra thông tin bổ sung có đúng doanh nghiệp và thực sự được URL nguồn hỗ trợ hay không.
6. Sửa lỗi quan trọng; nếu điều chỉnh dựa trên bộ đánh giá, ghi rõ bộ đó đã được dùng để sửa và bổ sung mẫu mới để kiểm tra lại nếu có thể.

**Vì sao làm:** Có số liệu và lỗi cụ thể giúp chứng minh mức đáp ứng Anh/Nhật, thay vì chỉ khẳng định “hỗ trợ đa ngôn ngữ”.

**Kết quả cuối ngày:** Có bảng đánh giá, ví dụ thành công/thất bại và danh sách giới hạn trung thực. Không tự ghi đạt 95% khi chưa đo hoặc chưa có tiêu chí thống nhất.

### Ngày 10: Đóng gói, diễn tập và bàn giao

**Học và nắm rõ:** Khả năng tái lập môi trường, tài liệu cấu hình, trình bày luồng nghiệp vụ và giải thích lựa chọn kỹ thuật.

**Việc phải làm:**

1. Viết README: yêu cầu môi trường, cài đặt, biến cấu hình, tạo cơ sở dữ liệu, chạy frontend/backend và cách kiểm thử.
2. Kiểm tra chạy lại từ bản mã nguồn sạch; không phụ thuộc vào cấu hình riêng chưa ghi trong tài liệu.
3. Chuẩn bị demo 5-7 phút: danh thiếp Anh, danh thiếp Nhật, sửa trường OCR sai, tra cứu có nguồn, lưu và tìm lại, một tình huống lỗi.
4. Chuẩn bị báo cáo ngắn: đề bài, phạm vi, kiến trúc, quy tắc chuẩn hóa, kết quả kiểm thử và giới hạn.
5. Đóng gói mã nguồn, cấu hình mẫu, hướng dẫn, bộ mẫu được phép chia sẻ và báo cáo kết quả.
6. Giữ thời gian cuối ngày làm dự phòng cho lỗi cài đặt/demo; không thêm tính năng mới.

**Vì sao làm:** Người chấm cần chạy được, thấy đủ yêu cầu và hiểu bạn đã giải quyết vấn đề như thế nào.

**Kết quả cuối ngày:** Bộ bàn giao có thể chạy lại và demo hoàn chỉnh; mô tả rõ phần đã làm, phần chưa làm và kết quả đo thực tế.

## 5. Dữ liệu cần thiết kế từ đầu

| Nhóm dữ liệu | Nội dung tối thiểu | Vì sao cần |
| --- | --- | --- |
| Người liên hệ | ID, tên nguyên bản, chức danh, phòng ban, các email/số điện thoại, ID doanh nghiệp | Một công ty có nhiều người; một người có nhiều cách liên hệ |
| Doanh nghiệp | ID, tên nguyên bản, website, địa chỉ | Gom thông tin công ty vào cùng hồ sơ để tái sử dụng |
| Bản quét | ID, tham chiếu ảnh, văn bản OCR, kết quả trích xuất gốc, thời điểm | Đối chiếu và đánh giá OCR mà không mất bằng chứng |
| Thông tin bổ sung | Lĩnh vực, quy mô, sản phẩm/dịch vụ, URL và bằng chứng cho từng thông tin | Kiểm tra thông tin đến từ đâu và có đáng tin không |
| Trạng thái duyệt | Bản nháp/đã duyệt, giá trị đã sửa, thời điểm cập nhật | Phân biệt kết quả máy với dữ liệu đã được người dùng xác nhận |

Quy tắc bắt buộc nắm rõ:

- Không dùng trường số để lưu số điện thoại vì có dấu `+`, số 0 đầu và số máy lẻ.
- Không bắt buộc mọi danh thiếp phải có đủ trường; phân biệt không có thông tin với lỗi không đọc được.
- Không tự tách họ/tên Nhật khi không chắc; tên đầy đủ nguyên bản là giá trị chính.
- Không thay dữ liệu gốc bằng bản dịch hoặc phiên âm tự sinh.
- Không tự điền quy mô/lĩnh vực chỉ vì “có vẻ hợp lý”; dữ liệu bổ sung phải có nguồn.
- Không gộp hồ sơ chỉ vì hai người hoặc hai công ty có tên giống nhau.

## 6. Cách tự đo kết quả và kiểm tra đã hoàn thành

Với mỗi trường và mỗi ngôn ngữ, đếm số trường có trên ảnh chuẩn, số trích xuất đúng, số sai, số bỏ sót. Ví dụ: trong 10 danh thiếp Nhật có 8 email, đọc đúng 7 email thì tỷ lệ đúng trên email có thật là `7/8 = 87,5%`. Ghi riêng các email tự sinh ở ảnh không có email; không để những trường hợp đó biến mất khỏi báo cáo.

Chốt quy tắc so sánh trước khi đo: email có thể bỏ khoảng trắng dư, số điện thoại có thể bỏ dấu phân cách khi đối chiếu; tên/công ty phải giữ đúng nội dung. Không nới quy tắc sau khi thấy kết quả chỉ để tăng điểm. Bộ mẫu nhỏ chỉ cho biết chất lượng trong phạm vi đã thử.

### Checklist cuối cùng

- [ ] Chụp được ảnh và tải được ảnh thay thế.
- [ ] Chạy OCR thực với cả tiếng Anh và tiếng Nhật.
- [ ] Trả về dữ liệu theo trường, không chỉ văn bản thô.
- [ ] Giữ đúng chữ Nhật qua trích xuất, sửa, lưu, tải lại và xuất dữ liệu.
- [ ] Có quy tắc chuẩn hóa rõ ràng và người dùng sửa được kết quả.
- [ ] Tra cứu bổ sung chạy tự động trong ít nhất các trường hợp có nguồn hỗ trợ.
- [ ] Thông tin bổ sung có nguồn; không tìm thấy thì thông báo đúng.
- [ ] Hồ sơ lưu bền vững, tìm lại và cập nhật được.
- [ ] Lỗi camera/OCR/tra cứu không làm mất phần dữ liệu đã có.
- [ ] Có kết quả kiểm thử riêng cho Anh và Nhật trước sửa tay.
- [ ] Có hướng dẫn chạy và cấu hình mẫu không chứa khóa bí mật.
- [ ] Demo trọn luồng chạy được trên môi trường bàn giao.

## 7. Nếu tiến độ bị chậm, ưu tiên thế nào?

| Mốc kiểm soát | Phải có | Khi chậm |
| --- | --- | --- |
| Hết ngày 2 | OCR thực Anh/Nhật và quyền truy cập nguồn tra cứu | Tập trung xử lý phụ thuộc dịch vụ; tạm dừng làm đẹp giao diện |
| Hết ngày 4 | Ảnh → OCR → các trường trên màn hình | Giữ upload hoạt động để kiểm tra OCR; hoàn thiện camera sau, vẫn phải có trước bàn giao |
| Hết ngày 7 | Trọn luồng có tra cứu và lưu dữ liệu | Hoãn CSV, cải tiến giao diện và chống trùng nâng cao; giữ JSON nếu cần xuất |
| Hết ngày 8 | Luồng chính ổn định | Dừng thêm tính năng; ưu tiên lỗi sai/mất dữ liệu |
| Ngày 9-10 | Kiểm thử, tài liệu và demo | Giữ thời gian này; ghi rõ giới hạn thay vì thêm tính năng chưa kiểm chứng |

Không cắt bỏ tiếng Nhật, trích xuất có cấu trúc, chuẩn hóa, tra cứu có nguồn hoặc lưu hồ sơ vì đây là những phần tạo nên bài làm đúng phạm vi đã chọn. Có thể giảm độ đẹp giao diện, số bộ lọc, định dạng xuất và các tính năng mở rộng.

## 8. Những câu hỏi bạn cần tự giải thích được khi trình bày

1. Vì sao webcam chỉ giải quyết đầu vào, chưa giải quyết OCR và hồ sơ đối tác?
2. OCR, trích xuất, chuẩn hóa và tra cứu khác nhau ở đâu?
3. Bạn đã chứng minh hỗ trợ tiếng Nhật bằng những mẫu và số liệu nào?
4. Vì sao phải giữ nguyên tên Nhật và dữ liệu OCR gốc?
5. Ứng dụng làm gì khi không đọc được email hoặc không tìm thấy doanh nghiệp?
6. Bạn xác định đúng doanh nghiệp và kiểm chứng thông tin bổ sung thế nào?
7. Dữ liệu được lưu ở đâu, có còn sau khi khởi động lại không?
8. Vì sao API key nằm ở backend và ảnh danh thiếp không nên công khai?
9. Lựa chọn phiên bản OCR nào, đã thử thực tế ra sao và có giới hạn gì?
10. Phần nào đã hoàn thành, phần nào chưa làm và vì sao ưu tiên như vậy trong 10 ngày?

Nếu trả lời được bằng mã nguồn, màn hình và kết quả kiểm thử thực tế, bạn đã nắm được cả cách làm lẫn lý do thiết kế của bài tập.
