# Rollout Gate B theo ngữ cảnh

Gate B chạy sau khi bài RSS không khớp từ khóa bệnh của cửa A. Detector nhận diện bốn loại tín hiệu: chùm ca bất thường, động vật, môi trường và phản ứng thực địa. Bài cửa B ở chế độ Active được LLM kiểm tra, lưu ẩn và chờ NVYT duyệt cả tín hiệu lẫn bệnh trong một lần.

## Trước khi chạy migration

1. Sao lưu đúng cơ sở dữ liệu mà backend đang dùng và kiểm tra có thể phục hồi.
2. Kiểm tra `alembic current` bằng môi trường backend hoạt động; revision trước Gate B phải là `e7b4c1d2f903`.
3. Kiểm tra migration `c93e42b7d10a_gate_b.py`: chỉ thêm cột/bảng ở chiều upgrade. Đo thời gian và lock trên bản sao staging có dung lượng gần production.
4. Trên staging: `alembic upgrade head`, chạy test và smoke test, `alembic downgrade -1`, rồi `alembic upgrade head` để xác minh rollback. Downgrade xóa dữ liệu Gate B đã ghi; chỉ thử trên staging.
5. Chỉ sau khi staging đạt: backup production, chạy `alembic upgrade head` vào giờ ít tải. Không tự chạy migration từ lần khởi động API.

**Lưu ý máy local hiện tại:** `backend/venv` dùng Python 3.13 nhưng có binary `pydantic_core` cho cp312, nên chưa chạy được FastAPI/Alembic bằng venv đó. Sửa hoặc tạo venv tương thích trước khi chạy migration. Không thay đổi `.env` hoặc DB đang crawl trong quá trình triển khai code này.

## Bật theo pha

| Pha | Cấu hình | Hành vi |
| --- | --- | --- |
| Shadow | `GATE_B_ENABLED=true`, `GATE_B_LLM_ENABLED=false` | Đếm trên toàn RSS, ghi mẫu, không gọi LLM cửa B, không lưu bài cửa B |
| Active thử nghiệm | `GATE_B_LLM_ENABLED=true`, `GATE_B_LLM_FEED_ALLOWLIST=<URL feed>`, cùng `LLM_RECHECK_ENABLED=true` | Chỉ feed được cấp phép gửi B sang LLM; bài lưu ẩn |
| Mở rộng | Thêm từng URL feed vào allowlist | Theo dõi số ứng viên, số gọi LLM, precision và queue NVYT |

Allowlist rỗng **không cấp phép feed nào**. Giá trị `*` cấp phép mọi feed và chỉ nên dùng sau khi đã đo tải. Các cờ được đọc khi process backend khởi động, nên đổi `.env` cần khởi động lại backend.

## Kiểm tra sau migration

- `GET /api/quality/samples`: bài cửa A có `stage1_route=keyword`; bài không khớp A đã được B kiểm tra có `gate_b_evaluated=true`; bài video có `gate_b_evaluated=false`.
- `GET /api/quality/metrics`: chỉ cộng các feed của `ScanRun.status=completed`. `candidates_total` là số detector khớp, `active_processed_total` là số B được chuyển vào Stage 2 (không đồng nghĩa số request mạng LLM thành công).
- `GET /api/context-signals/queue`: chỉ NVYT/admin được xem bài B lưu ẩn. Trang `/signals/gate-b` cho phép duyệt.
- `GET /api/signals`: bài B chưa xác nhận bệnh không tạo event, không xuất hiện công khai.
- Duyệt cùng một `request_id` và payload phải trả cùng review. Dùng lại ID với payload khác hoặc version cũ phải trả 409.
- Khi chọn `disease_identified`, event, `human_label=relevant`, `is_excluded=false` được commit cùng nhau. Bài chưa xác định bệnh vẫn ẩn.
- Kiểm tra smoke test các API cũ: `/api/quality/samples`, `/api/quality/metrics`, `/api/signals`.

## Đo chất lượng

Mẫu RSS vẫn được chọn bằng hash URL 10% sau khử trùng URL trong scan và lọc ngày, trước video và cửa A. Gán bốn nhãn cho mẫu B đã khớp và mẫu **không khớp** mà `gate_b_evaluated=true`. Nhãn dương là `confirmed_event` và `early_signal`.

- Precision detector = TP / (TP + FP), trong các mẫu khớp B đã gán nhãn.
- Recall detector = TP / (TP + FN), FN lấy từ mẫu trượt A, được B kiểm tra nhưng không khớp B. Nếu chưa có mẫu âm gán nhãn, API trả recall `null`.
- Chỉ cộng mẫu có `detector_version` hiện hành. Ghi cả tử số và mẫu số; gán nhãn chọn lọc làm ước lượng bị lệch.
- `candidates_total / eligible_entries_total` là lưu lượng, **không phải** precision/recall.
- Precision LLM cửa B active được báo riêng. Không gộp kết quả A, shadow và active.


Sau khi sửa venv, chạy `backend/venv/Scripts/python.exe backend/scripts/gate_b_sample_check.py` để đếm tối đa 1.000 mẫu RSS trượt cửa A. Script chỉ đọc DB và chỉ in tổng số khớp theo loại. Đây là phép đo lưu lượng; cần NVYT gán nhãn để tính precision/recall.

Gán nhãn bài qua `/api/evaluation/{article_id}` hoặc import Excel sẽ từ chối/bỏ qua bài cửa B. Chỉ `/api/context-signals/{article_id}/review` được thay đổi trạng thái công bố của bài cửa B.
Khi chỉnh quy tắc detector, tăng `DETECTOR_VERSION` trong `signal_detector.py`; mẫu cùng URL được tách theo `(link, gate_b_mode, detector_version)` để không trộn kết quả hai phiên bản.
