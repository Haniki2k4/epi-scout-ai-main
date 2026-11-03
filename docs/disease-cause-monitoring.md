# Từ khóa bổ sung và thống kê theo nguyên nhân

Danh mục trong `backend/app/modules/news/disease_catalog.py` bổ sung các tên bệnh,
tác nhân và biến thể tìm kiếm. Không xóa từ khóa cũ, không sửa trạng thái bật/tắt,
không ghi đè bài báo, số ca hoặc sự kiện lịch sử. Seed chỉ thêm danh tính bệnh chưa có;
nếu một tên đồng nghĩa đã bị tắt, không thêm tên khác để tự bật lại bệnh đó.

## Phát hiện và trích xuất

- Stage 1 dò tên đang bật cùng các tên đồng nghĩa trong tiêu đề/tóm tắt, vẫn áp dụng
  bộ lọc tư vấn và điểm ngữ cảnh hiện có. Sau khi lấy sapo, bổ sung ứng viên nếu sapo
  nêu rõ một bệnh đang được giám sát.
- Stage 2 phải chọn tên thuộc ứng viên; chấp nhận tên khoa học đồng nghĩa và chuẩn hóa
  danh tính bệnh. `reason` tiếp tục lưu lý do trích xuất. Không đoán nguyên nhân từ triệu chứng.
- `virus`, `sốt` vẫn còn trong từ khóa và dữ liệu nguồn. Khi thống kê, dùng
  `virus chưa xác định`, `sốt chưa rõ nguyên nhân` nếu chưa có bệnh cụ thể tương ứng.
- `sốt do virus` chỉ dùng khi nguồn nêu rõ căn nguyên virus nhưng chưa xác định loại.
- Không đồng nhất Rickettsia với riêng sốt mò; không coi “vi khuẩn ăn thịt người”
  là tên riêng của Whitmore. Không gộp các phân týp cúm khác nhau.

## Hợp đồng API

Các endpoint thống kê hiện có giữ nguyên cấu trúc JSON, nhưng tên bệnh được chuẩn hóa
thay vì đếm tên đồng nghĩa thành các bệnh khác nhau. Các nhãn rộng chỉ được thay thế
trong kết quả đọc khi dữ liệu đã lưu có bệnh cụ thể thuộc nhóm tương ứng. Không quét
lại hoặc gọi LLM để suy luận nguyên nhân cho bài cũ.

- `GET /api/stats/disease-catalog`: toàn bộ tên bệnh chuẩn đang bật, bổ sung các tên
  có dữ liệu trong 12 tháng gần nhất; mỗi dòng có `disease_name`, `article_count`.
- `GET /api/stats/disease-breakdown?category=virus&days=30`: `category` nhận `virus`
  hoặc `sốt`, `days` từ 1 đến 366. Trả `category`, `days`, `metric_type=mention_count`,
  `total_articles`, `diseases` (từng tên bệnh và số bài).
- Bộ lọc `disease=virus` hoặc `disease=sốt` ở Z-score/dự báo dùng hợp các bài trong nhóm.
  Bộ lọc tên bệnh cụ thể hoặc tên đồng nghĩa chỉ tính bệnh đó. Nhãn “chưa xác định”
  chỉ chọn các bài chưa xác định, không chọn toàn nhóm.

Nhóm sốt là danh mục giám sát được khai báo tường minh, không phải suy luận triệu chứng
của mọi ca trong nhóm. Một bài nhắc nhiều bệnh chỉ tính một lần trong `total_articles`.
Không lấy tổng các dòng làm tổng số bài; không cộng số ca từ các bài đăng lại.

Trang Phân tích có bảng chi tiết theo nhóm và bộ chọn bệnh chuẩn cho Z-score/dự báo.
Trang quản trị vẫn giữ nguyên các từ khóa gốc để kiểm tra và bật/tắt.

## Bổ sung vào database

Mở **Quản trị → Dữ liệu → Từ khóa** (`/admin/data/keywords`) để thêm, sửa,
bật/tắt hoặc bỏ từ khóa. Nút **Bổ sung từ khóa gợi ý** hiển thị các mục còn thiếu,
tên đồng nghĩa và nhóm thống kê; chỉ thêm những mục được chọn. Các thao tác ghi yêu
cầu quyền admin. Bỏ từ khóa khỏi danh mục không xóa bài báo hoặc số ca lịch sử.

Backend không tự thêm lại từ khóa khi khởi động. Hai API quản trị mới:

- `GET /api/keywords/suggestions`: danh sách gợi ý chưa có tên hoặc tên đồng nghĩa.
- `POST /api/keywords/import-suggestions`, JSON `{"keywords":["Whitmore","Marburg"]}`:
  thêm các mục được chọn, bỏ qua mục đã có kể cả đang tắt; trả `added_count`,
  `skipped_count`, `added_keywords`. Gọi lại không thêm trùng.

Việc thêm/sửa thông thường cũng kiểm tra tên đồng nghĩa để tránh tạo trùng bệnh.
Nếu cần vận hành qua CLI, chạy từ thư mục gốc dự án:

```powershell
python -m backend.scripts.add_monitoring_keywords
python -m backend.scripts.add_monitoring_keywords --apply
```

Nếu MySQL chạy trong container local của dự án:

```powershell
python -m backend.scripts.add_monitoring_keywords --docker-container epi-scout-mysql
python -m backend.scripts.add_monitoring_keywords --docker-container epi-scout-mysql --apply
```

Lệnh không có `--apply` chỉ xem trước. Khi áp dụng, lưu snapshot từ khóa vào
`backups/keywords-before-add-*.json`, thêm mục còn thiếu, rồi kiểm tra ID, nội dung,
trạng thái và ngày tạo của mọi dòng cũ. Chạy lại không thêm trùng. Không có migration schema.

## Kiểm thử

```powershell
python -m pytest backend/tests/test_disease_catalog.py -q --disable-warnings
```

Kiểm thử dùng SQLite riêng: seed thêm mới, bảo toàn trạng thái tắt, tên đồng nghĩa,
phân týp riêng, nguyên nhân chưa rõ, tổng bài không trùng, Z-score/dự báo, dữ liệu cũ,
ghép sự kiện với tên cũ, bộ lọc Stage 1 và kiểm tra tên do LLM trả về.

## Chạy bản clone local

Trong lượt triển khai local ngày 03/11/2026, bản mới dùng frontend cổng 8080 và
chuyển các yêu cầu `/api` đến backend cổng 8001.
Chạy `start-backend.ps1` và `start-frontend.ps1` từ thư mục gốc để sử dụng đúng bản
clone này; các script tự xác định thư mục dự án. Proxy API local được cấu hình qua
`EPISCOUT_API_PROXY_TARGET` trong `frontend/.env.local` (không commit).

Database gốc `EpiScoutDB` được giữ nguyên. Bản mới dùng bản sao
`EpiScoutDB_latest_20261103` đã nâng cấp lên revision `b7d4e2f901aa`; cấu hình trong
`.env` local (không commit). Backup SQL ở `backups/before-latest-*.sql`.
Migration có sẵn của dự án chuyển các tổng ca event suy ra trước đây thành chưa
xác minh; các giá trị gốc vẫn còn trong database gốc và bản sao lưu SQL.

## Kiểm soát mức độ liên quan của bài báo

Luồng thu thập: RSS → lọc từ khóa/ngữ cảnh → tải thân bài gốc → loại menu,
tin liên quan và bình luận → AI đọc nội dung → đối chiếu câu bằng chứng →
duyệt tín hiệu Cửa B nếu cần → công khai và thống kê. Không đọc được thân bài,
AI lỗi hoặc thiếu bằng chứng thì giữ bài ở trạng thái chưa xác minh và ẩn công khai.
Đường dẫn lưu bài thủ công cũng phải qua bước đọc và thẩm định nội dung.

AI phải trả `relevance_evidence` với `signal_type` và `quote` nguyên văn từ thân
bài. Bộ kiểm tra xác nhận trích dẫn có trong bài; đánh giá ý nghĩa dịch tễ vẫn
do mô hình và người thẩm định thực hiện. Đây không phải bảo đảm phân loại đúng 100%.
Tin bệnh viện báo cáo ca nhiễm thực tế được giữ, kể cả một ca; câu hỏi tư vấn,
tin dịch vụ, nghiên cứu thuần túy và tin y tế không liên quan dịch bệnh bị loại.

Danh sách tin, số tin mới và thống kê dùng cùng điều kiện ẩn, đồng thời tôn trọng
nhãn người thẩm định khi nhãn đó khác nhãn AI. Việc rà soát dữ liệu cũ dùng
`backend.scripts.review_article_content` và `backend.scripts.apply_relevance_review`.
Script áp dụng mặc định chỉ tạo báo cáo; `--apply` lưu bản sao JSON trước khi
ẩn bài và cập nhật trạng thái các sự kiện mất nguồn hợp lệ. Giữ nguyên bài,
observations, từ khóa và nhãn thẩm định gốc để tra cứu/khôi phục.
