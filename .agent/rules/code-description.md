---
trigger: always_on
---

- Loại Project: Project tìm kiếm tin tức về các ca dịch bệnh tại việt nam theo từ khóa được nhập và từ khóa mặc định, trích xuất thông tin số ca mắc mới, hiển thị thống kê các ca bệnh, giả lập trích xuất dữ liệu theo Thông tư 54 của Bộ y tế, phân tích và lập biểu đồ trực quan xu hướng và so sánh.
A. Data Ingestion Layer (Thu thập Dữ liệu)
News Crawler: Các script (Python/Node.js) tự động quét tin tức tổng hợp số ca dịch bệnh từ các báo (VnExpress, Dân Trí...) theo danh sách whitelist. Cách crawl cố thể tham khảo file rspy trong thư mục backend.
Social Listening: Tool quét dữ liệu từ Mạng xã hội.
TT54 Data: Module import/API connector để lấy số liệu báo cáo bệnh truyền nhiễm từ hệ thống TT54 của Bộ Y tế.
B. Processing Layer (Xử lý & Phân tích - Phần quan trọng còn thiếu)
Data Cleaning: Làm sạch rác, lọc trùng lặp.
NLP Model (AI):
Relevance Filtering: Đọc nội dung bài báo xem có thực sự nói về dịch bệnh không.
User Intent: Phân loại mức độ nghiêm trọng (Cảnh báo/Bình thường - như trường status: "alert" trong mock data).
Keyword Extraction: Trích xuất từ khóa bệnh (Cúm A, Sốt xuất huyết...).
Case Extraction: Trích xuất số ca bệnh.
Summary: Tổng hợp số ca bệnh trong thời gian quét.
Data Storage: Lưu kết quả vào Database.
C. Presentation Layer 
API Server: Backend cung cấp API cho Frontend.
Frontend App: Gọi API lấy dữ liệu đã xử lý để vẽ biểu đồ và hiển thị danh sách cảnh báo.
- Framework: React (sử dụng Vite để build).
- Nhất quán ngôn ngữ: TypeScript.
- Giao diện: Tailwind CSS (style), Shadcn UI (component), Lucide React (icon).
Biểu đồ: Recharts.