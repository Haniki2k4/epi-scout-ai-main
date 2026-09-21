# EpiScout AI

EpiScout AI là hệ thống giám sát thông tin dịch tễ từ báo điện tử. Hệ thống thu thập bài viết, phát hiện tín hiệu bệnh truyền nhiễm, hỗ trợ nhân viên y tế xác nhận và gom nhiều bài báo về cùng một sự kiện.

## Mục tiêu

- Phát hiện sớm ca bệnh, ổ dịch và hiện tượng y tế bất thường.
- Giảm bài tư vấn, quảng cáo, hành chính và từ khóa dùng sai ngữ cảnh.
- Giữ lại tín hiệu chưa gọi được tên bệnh, như chùm ca sốt hoặc động vật chết bất thường.
- Truy vết bài gốc, bằng chứng, kết quả lọc và quyết định của người duyệt.
- Theo dõi diễn biến theo bệnh, địa bàn, thời gian và sự kiện.

## Chức năng chính

### Thu thập và phát hiện

- Quét nguồn RSS đang hoạt động và bổ sung Google News RSS khi quét theo khoảng ngày.
- Chuẩn hóa nội dung, giải URL chuyển tiếp về nguồn báo và khử trùng URL.
- **Cửa A:** phát hiện từ khóa bệnh kèm ngữ cảnh dịch tễ.
- **Cửa B:** phát hiện tín hiệu bất thường dù chưa có tên bệnh.
- Loại sớm bài hỏi đáp, tư vấn, quảng cáo, video và từ khóa sai nghĩa.

### Phân loại và xác nhận

- LLM kiểm tra lại thông tin và trích xuất bệnh, địa bàn, thời gian, số ca, tử vong.
- Nhân viên y tế duyệt tín hiệu Cửa B và xác định bệnh trong cùng một lần.
- Bài Cửa B được giữ ẩn cho đến khi có quyết định hợp lệ.
- Trang Chất lượng hỗ trợ gán nhãn để đo precision, recall và nguyên nhân lọc sai.

### Khai thác kết quả

- Giữ từng bài báo để bảo toàn nguồn và gom các bài cùng sự kiện vào `NewsEvent`.
- Cung cấp dashboard, bản đồ, xu hướng, z-score và dự báo.
- Hỗ trợ cảnh báo cá nhân, bookmark và lịch gửi báo cáo.
- Xuất báo cáo Word và Excel.

## Workflow tổng quát

```text
RSS / Google News RSS
        │
        ▼
Chuẩn hóa, giải URL nguồn, lọc ngày và lọc trùng
        │
        ▼
Stage 1 — phát hiện ứng viên
   ├── Cửa A: từ khóa bệnh + ngữ cảnh dịch tễ
   └── Cửa B: tín hiệu bất thường không cần tên bệnh
        │
        ▼
Stage 2 — LLM kiểm tra và trích xuất
        │
        ├── Tuyến A hợp lệ ───────────────┐
        └── Tuyến B → NVYT xác nhận tín hiệu và bệnh
                                          │
                                          ▼
Stage 3 — tạo/ghép sự kiện, lưu ca bệnh và bằng chứng
        │
        ▼
Dashboard, cảnh báo, phân tích và báo cáo
```

## Các stage xử lý

### Stage 0 — Thu thập và tiền xử lý

Hệ thống tải feed, lấy URL nguồn, kiểm tra ngày đăng, chuẩn hóa HTML và loại URL trùng. Khoảng 10% bài đủ điều kiện được lấy mẫu ổn định trước bộ lọc nội dung để đánh giá chất lượng.

### Stage 1 — Phát hiện ứng viên theo hai cửa

Stage 1 tìm bài đáng kiểm tra tiếp, chưa phải kết luận cuối cùng.

#### Cửa A — Từ khóa bệnh có ngữ cảnh

Cửa A tìm từ khóa bệnh trong tiêu đề hoặc mô tả và chấm ngữ cảnh xung quanh. Chỉ nhắc đúng tên bệnh chưa đủ để trở thành tín hiệu.

Bài có thể đi tiếp khi có dấu hiệu như số ca, ca mắc, tử vong, ổ dịch, địa bàn, thời điểm hoặc phản ứng chống dịch. Bài hỏi đáp, kiến thức sức khỏe, quảng cáo, hội thảo chung chung và nghĩa bóng bị loại nếu không có bằng chứng sự kiện thật.

- “Hà Nội ghi nhận 3 ca sởi” → đi tiếp.
- “Người lớn có mắc tay chân miệng không?” → loại vì là bài tư vấn.
- “Lao về phía trước” → không được hiểu là bệnh lao.

#### Cửa B — Tín hiệu ngữ cảnh không cần từ khóa bệnh

Nếu bài không qua Cửa A, Cửa B tìm bốn nhóm tín hiệu:

1. chùm ca hoặc hiện tượng y tế bất thường chưa rõ nguyên nhân;
2. tín hiệu từ động vật;
3. tín hiệu từ môi trường hoặc thực phẩm;
4. phản ứng thực địa như phong tỏa, kiểm dịch hoặc khử khuẩn diện rộng.

Cửa B yêu cầu cụm tín hiệu, ngữ cảnh hỗ trợ và không phạm cụm loại trừ. Detector không tự suy luận tên bệnh.

- **Shadow:** ghi nhận để đo detector, chưa chuyển bài sang LLM.
- **Active:** feed được cấp phép chuyển ứng viên sang Stage 2 và lưu bài ở trạng thái ẩn.

### Stage 2 — LLM kiểm tra và trích xuất

LLM trả nhãn `relevant`, `noise`, `irrelevant` hoặc `unsure`, đồng thời cố gắng trích xuất bệnh, địa bàn, ngày xảy ra, số ca và bằng chứng.

Tuyến A hợp lệ được xử lý tiếp. Tuyến B vẫn phải chờ nhân viên y tế xác nhận tín hiệu và bệnh; LLM không thay thế quyết định nghiệp vụ.

### Stage 3 — Xác nhận và tạo sự kiện

- Bài tuyến A hợp lệ được tạo mới hoặc ghép vào `NewsEvent`.
- Bài tuyến B chỉ được công bố và tạo/ghép sự kiện sau khi nhân viên y tế xác nhận.
- Mỗi bài vẫn được lưu riêng; số liệu ca bệnh gắn với nguồn đã nêu chúng.
- Bài bị loại, chưa chắc chắn hoặc chưa duyệt không xuất hiện như tín hiệu công khai.

## Tiêu chí bài liên quan

Bài liên quan phải có ít nhất một tín hiệu có thể hành động:

- ca bệnh hoặc ổ dịch thật tại một địa bàn;
- chùm triệu chứng hoặc sự kiện y tế bất thường;
- cảnh báo từ động vật, môi trường hoặc thực phẩm;
- hoạt động ứng phó thực địa cho một nguy cơ dịch tễ cụ thể.

Bài tư vấn, quảng cáo, hội nghị chung chung, nghĩa bóng hoặc từ khóa nằm trong từ khác bị loại nếu không có bằng chứng sự kiện thật.

## Vai trò người dùng

- **Người dùng:** xem dashboard, tin tức, sự kiện, cảnh báo, bookmark và báo cáo.
- **Nhân viên y tế/người duyệt:** xác nhận tín hiệu Cửa B và bệnh.
- **Admin:** quản lý tài khoản, từ khóa, nguồn RSS, lịch quét, báo cáo và chất lượng.

## Chất lượng hệ thống

Trang **Chất lượng scout** đo riêng:

- Cửa A: chất lượng tuyến từ khóa;
- Cửa B: chất lượng detector ngữ cảnh, gồm mẫu khớp và mẫu bỏ sót;
- Stage 2: chất lượng LLM trên các bài đã đến LLM;
- gom sự kiện: độ đúng của quyết định ghép bài;
- nguồn crawl: số bài tải, qua Stage 1, được lưu và lỗi theo feed.

`Nhiễu` và `Không liên quan` đều bị loại nhưng giữ thành hai nhãn để tìm nguyên nhân: nhiễu là bài có cụm từ khiến detector bắt nhầm; không liên quan là bài không có tín hiệu dịch tễ đáng kể.

## Tài liệu kỹ thuật

Xem [Cài đặt và kiến trúc kỹ thuật](docs/technical-setup.md) để biết công nghệ, database, API, biến môi trường, cách chạy local và triển khai.

Tài liệu vận hành:

- [Rollout Gate B](docs/gate-b-rollout.md)
- [Rollout Signal Evidence](docs/signal-evidence-rollout.md)
- [Thiết kế mở rộng nguồn crawl](docs/feature-crawl-data-expansion.md)
