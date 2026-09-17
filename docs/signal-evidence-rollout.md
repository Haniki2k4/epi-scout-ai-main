# Hướng dẫn triển khai migration bằng chứng tín hiệu

Tài liệu này dùng khi đưa mã nguồn và thay đổi cấu trúc dữ liệu lên một môi trường đang chạy. Migration giữ nguyên giá trị cột `disease_cases.case_count`, đồng thời gắn `data_quality=legacy_unverified` cho những hàng có `reported_value IS NULL`. Migration xóa các giá trị `news_events.case_count` cũ vì chúng có thể đã cộng trùng nhiều bài viết về cùng một sự kiện.

## 1. Kiểm tra đúng database trước khi làm gì khác

Từ thư mục `backend`, chạy lệnh sau với cấu hình kết nối của **database cần triển khai**:

```powershell
& ..\.venv\Scripts\python.exe -m alembic current
```

Ngày 17/09/2026, database local đã ở `e7b4c1d2f903 (head)` và API local chạy bằng `.venv` tại root repo với Python 3.13. API này không dùng `backend/venv` cũ. Vì vậy, không cần chạy lại migration hoặc dừng crawler local chỉ để thực hiện migration này.

Backend trên Hugging Face có thể kết nối tới database khác. Dockerfile của backend chỉ khởi động Uvicorn, không tự chạy Alembic. Hãy kiểm tra revision của database mà môi trường đó thực sự sử dụng.

## 2. Chuẩn bị nếu database còn ở revision cũ

1. Xác nhận môi trường Python dùng để chạy Alembic hoạt động. Đặt `SECRET_KEY` riêng, đủ mạnh cho xác thực ở môi trường public; biến này không phải điều kiện để Alembic chạy.
2. Tạm dừng crawler, scheduler, các lệnh ghi qua API và tác vụ tạo báo cáo có ghi vào database đích.
3. Tạo **bản sao lưu đầy đủ và mới** của database đích. `mysqldump` là công cụ sao lưu, không phải thành phần cần để server hoặc crawler hoạt động. Trên máy Windows này, nó có trong MySQL Workbench nhưng chưa nằm trong `PATH`. Điền các biến theo cấu hình DB thực tế; lệnh sẽ hỏi mật khẩu:

   ```powershell
   $dbServer = 'localhost'
   $dbPort = 3306
   $dbUser = 'gia-tri-DB_USER'
   $dbName = 'gia-tri-DB_NAME'
   $backupFile = 'E:\EBS-Processing\epi-scout-backup-YYYY-MM-DD.sql'

   & 'C:\Program Files\MySQL\MySQL Workbench 8.0 CE\mysqldump.exe' --single-transaction --routines --triggers -h $dbServer -P $dbPort -u $dbUser -p --databases $dbName "--result-file=$backupFile"
   if ($LASTEXITCODE -ne 0) { throw 'Sao lưu thất bại' }
   if ((Get-Item -LiteralPath $backupFile).Length -eq 0) { throw 'Tệp sao lưu rỗng' }
   ```

   Kiểm tra khả năng khôi phục bằng cách thử nhập tệp vào một database tạm. Giữ bản sao lưu ngoài repo. Tệp `backup.sql` ở root được tạo trước migration này nên không phải điểm khôi phục mới.
4. Ghi lại revision Alembic và số hàng của `disease_cases`, `news_events`, `article_identity` để đối chiếu sau migration.

## 3. Triển khai vào database còn ở revision cũ

1. Từ thư mục `backend`, chạy `alembic upgrade head` với **đúng cấu hình kết nối của database vừa sao lưu**. Revision mong đợi là `e7b4c1d2f903`.
2. Kiểm tra số hàng `disease_cases` không giảm. Số hàng có `data_quality = 'legacy_unverified'` phải tương ứng với những hàng trước migration có `reported_value IS NULL`. Kiểm tra số hàng `news_events` và `article_identity` không giảm.
3. Triển khai backend và frontend từ cùng phiên bản mã nguồn để API và giao diện tương thích. Các API bài viết/sự kiện vẫn giữ trường chuyển tiếp; API chất lượng và tín hiệu mới cần các bảng mới.
4. Cho phép ghi dữ liệu trở lại. Kiểm tra một lượt crawl, một mẫu RSS, hàng đợi duyệt của người phân tích và hai loại báo cáo.

Migration này không có lệnh `downgrade` tự động vì không thể khôi phục an toàn các tổng ca bệnh đã suy diễn. Nếu phải quay lui, dùng bản sao lưu đã kiểm tra khả năng khôi phục.

## 4. Điều kiện đo lường trước khi mở rộng

- `GET /api/quality/metrics` trả `null` khi chưa có mẫu gán nhãn làm mẫu số. Recall của LLM chỉ tính trên dữ liệu đã qua Stage 1; chỉ số ghép cặp chỉ tính trên các cặp ứng viên đã gán nhãn, không đại diện cho recall toàn bộ hệ thống gom nhóm.
- Gán nhãn mẫu RSS và cặp sự kiện trước khi điều chỉnh ngưỡng gom nhóm `0.75`. Từ `backend`, xuất mẫu RSS bằng `python scripts/export_quality_dataset.py --cutoff YYYY-MM-DD` và cặp sự kiện bằng `python scripts/export_event_pair_split.py --cutoff YYYY-MM-DD`. Những mục RSS chưa liên kết sự kiện chỉ có thể chia tập theo thời gian; lệnh xuất sẽ báo số lượng này.
- Chỉ làm gazetteer cấp xã/huyện, benchmark bộ crawl, mô hình local hoặc fine-tuning sau khi có nguồn địa danh đáng tin cậy và bộ dữ liệu P1 đã gán nhãn để đo baseline. Tiếp tục dùng RSS và LLM hiện tại cho đến khi số liệu cho thấy cần thay đổi.

