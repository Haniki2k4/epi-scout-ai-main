---
title: EpiScout Backend
emoji: 🚀
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# EpiScout Backend

Hệ thống quét và tự động phân tích tin tức dịch tễ học, chạy trên môi trường Hugging Face Spaces bằng Docker.

## Cấu hình
Ứng dụng sử dụng Dockerfile tối ưu hóa, tự động cài đặt các thư viện Python, tải trước mô hình SentenceTransformer và chạy Uvicorn trên cổng `7860`.
