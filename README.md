# Epi Scout AI - Hệ thống Giám sát Dịch bệnh Thông minh

Dự án Epi Scout AI là một ứng dụng web full-stack giúp theo dõi, thu thập và phân tích tin tức về dịch bệnh từ các nguồn báo chí chính thống tại Việt Nam.

## Yêu cầu hệ thống

Trước khi cài đặt, hãy đảm bảo máy tính của bạn đã cài đặt các công cụ sau:

*   **Python**: Phiên bản 3.8 trở lên.
*   **Node.js**: Phiên bản 18 trở lên (khuyên dùng LTS).
*   **SQL Server**: Database engine (Microsoft SQL Server).
*   **ODBC Driver 17 for SQL Server**: Driver để Python kết nối với SQL Server.

## Cấu trúc dự án

*   **backend/**: Mã nguồn server (Python/FastAPI).
*   **src/**: Mã nguồn frontend (React/Vite).

## Cài đặt

### 1. Clone dự án

```bash
git clone <repository-url>
cd epi-scout-ai-node
```

### 2. Cài đặt Backend

Di chuyển vào thư mục gốc và cài đặt các thư viện Python:

```bash
pip install -r backend/requirements.txt
```

### 3. Cấu hình Database

Tạo file `.env` tại thư mục gốc của dự án và điền thông tin kết nối SQL Server của bạn:

```env
DB_SERVER=localhost
DB_NAME=EpiScoutDB
DB_USER=<your_db_username>
DB_PASSWORD=<your_db_password>
```

*Lưu ý: Hãy đảm bảo bạn đã tạo database `EpiScoutDB` trong SQL Server hoặc để code tự động tạo bảng (tuy nhiên DB phải tồn tại trước).*

### 4. Cài đặt Frontend

Cài đặt các gói npm cho giao diện:

```bash
npm install
```

## Hướng dẫn chạy dự án

Bạn cần chạy song song cả Backend và Frontend trên 2 cửa sổ terminal khác nhau.

### Chạy Backend (API Server)

Tại thư mục gốc dự án:

```bash
uvicorn backend.main:app --reload
```
Server sẽ khởi chạy tại `http://127.0.0.1:8000`. Cấu hình Swagger UI có thể xem tại `http://127.0.0.1:8000/docs`.

### Chạy Frontend (Web App)

Tại thư mục gốc dự án (mở terminal mới):

```bash
npm run dev
```
Ứng dụng web sẽ chạy tại `http://localhost:5173` (hoặc port hiển thị trên terminal).

## Hướng dẫn chạy Test & Debug

Dự án cung cấp một số script để kiểm tra chức năng thu thập dữ liệu (crawl) và gỡ lỗi. Các lệnh này nên được chạy từ thư mục gốc của dự án.

### 1. Chạy Test Crawl (Thu thập dữ liệu thử nghiệm)

Script này sẽ giả lập quá trình quét tin tức với danh sách từ khóa mẫu và in kết quả ra màn hình.

```bash
python -m backend.test_crawl
```

### 2. Kiểm tra nguồn RSS (Debug RSS)

Script này sẽ kiểm tra kết nối tới các RSS Feed đã cấu hình xem có hoạt động ổn định không.

```bash
python -m backend.debug_rss
```

### 3. Reset Database (Xóa & Tạo lại bảng)

**CẢNH BÁO**: Lệnh này sẽ xóa toàn bộ dữ liệu hiện có trong database và tạo lại các bảng rỗng.

```bash
python -m backend.reset_db
```

### 4. Kiểm tra Frontend (Lint)

Kiểm tra lỗi cú pháp và quy chuẩn code của Frontend:

```bash
npm run lint
```
