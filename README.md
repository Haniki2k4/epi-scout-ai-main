# Epi Scout AI

Hệ thống giám sát tin tức dịch bệnh từ RSS, gồm:

- `frontend/`: giao diện React + Vite
- `backend/`: API FastAPI + crawler RSS
- `docker-compose.yml`: MySQL phục vụ lưu trữ dữ liệu

Mục tiêu của project là:

- quản lý danh sách từ khóa giám sát như `H5N1`, `sốt xuất huyết`, `não mô cầu`
- quét các nguồn RSS tin tức
- lọc bài viết theo từ khóa
- tự động lưu bài từ nguồn tin được whitelist
- hiển thị thống kê và danh sách bài viết đã lưu

## Kiến trúc nhanh

Luồng chạy chính:

1. Người dùng thêm từ khóa trên giao diện.
2. Frontend gọi `POST /api/keywords` để lưu keyword vào database.
3. Khi bấm quét, frontend gọi `POST /api/scan`.
4. Backend đọc keyword từ database, crawl các RSS feed, lọc bài phù hợp.
5. Bài từ nguồn whitelist được lưu tự động vào MySQL.
6. Frontend gọi lại `GET /api/articles` và `GET /api/stats/*` để cập nhật màn hình.

## Cấu trúc thư mục

```text
.
├── backend
│   ├── app
│   │   ├── core
│   │   │   └── database.py
│   │   ├── modules
│   │   │   └── news
│   │   │       ├── crawler.py
│   │   │       ├── crud.py
│   │   │       ├── models.py
│   │   │       ├── schemas.py
│   │   │       └── stats.py
│   │   └── main.py
│   ├── requirements.txt
│   └── scripts
├── frontend
│   ├── src
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
└── .env
```

## Yêu cầu môi trường

- Python 3.12+
- Node.js 18+
- Docker + Docker Compose

## Biến môi trường

Project dùng file `.env` ở root repo.

Ví dụ:

```env
DB_SERVER=localhost
DB_PORT=3306
DB_NAME=EpiScoutDB
DB_USER=epi_scout
DB_PASSWORD=epi_scout_dev_pw
```

`backend/app/core/database.py` sẽ tự đọc file `.env` ở root repo.

## Cách chạy local

### 1. Chạy database

Từ thư mục root:

```bash
docker compose up -d
```

Kiểm tra trạng thái:

```bash
docker compose ps
```

### 2. Chạy backend

Tạo virtualenv:

```bash
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Chạy API:

```bash
cd /path/to/epi-scout-ai-main
backend/venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Backend mặc định chạy ở:

- `http://127.0.0.1:8000`

### 3. Chạy frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend mặc định chạy ở:

- `http://localhost:8080`

Trong chế độ dev, Vite proxy mọi request `/api` sang:

- `http://127.0.0.1:8000`

## API chính

### Keywords

- `GET /api/keywords`: lấy danh sách keyword đang lưu
- `POST /api/keywords`: thêm keyword mới
- `DELETE /api/keywords/{keyword_id}`: xóa keyword

### Scan và bài viết

- `POST /api/scan`: chạy crawler RSS
- `GET /api/articles`: lấy danh sách bài đã lưu
- `POST /api/articles/save`: lưu bài viết thủ công

### Whitelist

- `GET /api/whitelist`
- `POST /api/whitelist`

### Stats

- `GET /api/stats/overview`
- `GET /api/stats/trends?days=7`

## Crawler hiện hoạt động thế nào

Logic chính nằm ở [backend/app/modules/news/crawler.py](/home/suno/Github/epi-scout-ai-main/backend/app/modules/news/crawler.py).

Crawler hiện:

- đọc keyword từ database
- quét danh sách RSS feed Việt Nam
- match keyword trên cả `title` và `summary`
- chuẩn hóa text trước khi match
- bỏ qua bài quá cũ
- gắn tag như `Mới`, `Cảnh báo`
- tự động lưu bài nếu domain thuộc whitelist

Lưu ý:

- nếu database chưa có keyword nào thì scan sẽ không ra kết quả
- việc chỉ gõ keyword vào ô input trên UI là chưa đủ, phải nhấn dấu `+` để lưu
- với keyword rất hẹp như `H5N1`, có thể không có bài mới trong feed tại thời điểm quét
- RSS của một số báo không nằm ở chuyên mục `sức khỏe`, nên crawler đã được mở rộng thêm feed `thời sự` và `thế giới`

## Quy trình sử dụng đúng

1. Mở giao diện frontend.
2. Nhập keyword.
3. Nhấn `+` để lưu keyword vào hệ thống.
4. Kiểm tra keyword xuất hiện dưới dạng badge.
5. Bấm `Bắt đầu quét`.
6. Xem bài đã lưu và thống kê.

## Các lỗi thường gặp

### 1. Frontend báo `http proxy error` hoặc `ECONNREFUSED 127.0.0.1:8000`

Nguyên nhân:

- backend chưa chạy
- backend chạy lỗi do không kết nối được MySQL

Cách xử lý:

```bash
docker compose up -d
backend/venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### 2. Quét xong nhưng không có bài nào

Kiểm tra:

- đã lưu keyword chưa
- keyword có quá hẹp không
- feed hiện tại có bài phù hợp hay không

Ví dụ:

- `H5N1` có thể không xuất hiện trong feed hôm đó
- `não mô cầu` hoặc `sốt xuất huyết` thường dễ có kết quả hơn

### 3. MySQL chạy nhưng backend không đăng nhập được

Kiểm tra `.env` và user database có khớp nhau không:

- `DB_SERVER`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

## Script hỗ trợ debug

Trong `backend/scripts/` có một số script để kiểm tra crawler:

- `debug_rss.py`: kiểm tra RSS feed còn sống không
- `test_crawl.py`: chạy thử luồng crawl
- `rs.py`: script thử nghiệm tìm tin theo keyword

Ví dụ:

```bash
backend/venv/bin/python backend/scripts/debug_rss.py
```

## Trạng thái hiện tại

Project đang ở mức demo/dev, chưa phải production-ready. Một số điểm còn cần hoàn thiện:

- chất lượng nguồn RSS còn phụ thuộc từng báo
- chưa crawl full article content một cách ổn định
- thống kê trend còn đơn giản
- chưa có auth
- chưa có migration database
- chưa có test tự động

## Gợi ý cải tiến tiếp theo

- thêm `README` cho từng thư mục con `backend/` và `frontend/`
- thêm migration bằng Alembic
- thêm `.env.example`
- thêm seed dữ liệu mẫu
- thêm integration test cho `/api/scan`
- thêm nguồn tổng hợp theo keyword thay vì chỉ RSS theo chuyên mục

## Tóm tắt lệnh hay dùng

Chạy DB:

```bash
docker compose up -d
```

Chạy backend:

```bash
backend/venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Chạy frontend:

```bash
cd frontend
npm run dev
```

Kiểm tra RSS:

```bash
backend/venv/bin/python backend/scripts/debug_rss.py
```
