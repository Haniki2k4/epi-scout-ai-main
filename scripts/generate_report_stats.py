import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from sqlalchemy import func, text
from datetime import datetime

# Add the backend directory to sys.path so we can import from app
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.append(backend_dir)

from app.core.database import SessionLocal
from app.modules.news.models import RssSource, Keyword, ArticleIdentity, ArticleDetails, NewsEvent, DiseaseCase
from app.modules.evaluation.models import ArticleEvaluation

def generate_report_stats():
    db = SessionLocal()
    try:
        print("="*60)
        print(" THỐNG KÊ DỮ LIỆU CHƯƠNG 4 - MỤC 4.1 ")
        print("="*60)
        
        # 1. RSS Sources
        total_rss = db.query(RssSource).count()
        active_rss = db.query(RssSource).filter(RssSource.is_active == True).count()
        print(f"- Số nguồn RSS đã cấu hình: {total_rss}")
        print(f"- Số nguồn đang active: {active_rss}")
        
        # 2. Time Range
        earliest_article = db.query(func.min(ArticleIdentity.published_date)).scalar()
        latest_article = db.query(func.max(ArticleIdentity.published_date)).scalar()
        if earliest_article and latest_article:
            print(f"- Thời gian thu thập: từ {earliest_article.strftime('%Y-%m-%d')} đến {latest_article.strftime('%Y-%m-%d')}")
        else:
            print("- Thời gian thu thập: Chưa có dữ liệu bài viết")

        # 3. Crawler metrics (Note: "Tổng số bài đọc" and "Bài qua Stage 1" are not persisted directly unless tracked via logs)
        print("- Tổng số bài đọc từ RSS/Google News: (Vui lòng lấy từ kết quả hiển thị lúc bấm Quét tin)")
        print("- Tổng số bài lọt qua Stage 1: (Vui lòng lấy từ kết quả hiển thị lúc bấm Quét tin)")

        # 4. Database metrics
        total_saved = db.query(ArticleIdentity).count()
        print(f"- Tổng số bài được lưu (vượt qua Stage 2/LLM): {total_saved}")
        
        total_events = db.query(NewsEvent).count()
        print(f"- Tổng số event tạo mới: {total_events}")

        # 5. False positive rates
        suspected_fp = db.query(ArticleDetails).filter(ArticleDetails.is_suspected_false_positive == True).count()
        fp_rate = (suspected_fp / total_saved * 100) if total_saved > 0 else 0
        print(f"- Số bài nghi ngờ False Positive: {suspected_fp} (Chiếm {fp_rate:.2f}%)")

        # 6. Evaluation metrics
        total_verified = db.query(ArticleEvaluation).filter(ArticleEvaluation.is_verified == True).count()
        print(f"- Số bài đã được người dùng xác minh nhãn thủ công: {total_verified}")

        print("\n" + "="*60)
        print(" GỢI Ý CHO PHẦN NHẬN XÉT EDA ")
        print("="*60)

        # Top sources
        top_sources = db.query(ArticleDetails.source, func.count(ArticleDetails.id).label('count'))\
                        .filter(ArticleDetails.source != None)\
                        .group_by(ArticleDetails.source)\
                        .order_by(text('count DESC')).limit(3).all()
        print("\n1. Top nguồn tin lưu nhiều bài nhất:")
        for src, cnt in top_sources:
            print(f"   - {src}: {cnt} bài")

        # Top diseases
        top_diseases = db.query(DiseaseCase.disease_name, func.count(DiseaseCase.id).label('count'))\
                         .group_by(DiseaseCase.disease_name)\
                         .order_by(text('count DESC')).limit(3).all()
        print("\n2. Top bệnh/từ khóa xuất hiện nhiều nhất:")
        for dis, cnt in top_diseases:
            print(f"   - {dis}: {cnt} lần nhắc đến")

        # Top locations
        top_locations = db.query(DiseaseCase.location, func.count(DiseaseCase.id).label('count'))\
                          .filter(DiseaseCase.location != None, DiseaseCase.location != 'unknown')\
                          .group_by(DiseaseCase.location)\
                          .order_by(text('count DESC')).limit(3).all()
        print("\n3. Top địa phương có tín hiệu dịch tễ nhiều nhất:")
        for loc, cnt in top_locations:
            print(f"   - {loc}: {cnt} tín hiệu")

        # Top missing summary sources
        # We assume if fetch_sapo was used, summary might be short or we can just find sources with missing summaries
        empty_summaries = db.query(ArticleDetails.source, func.count(ArticleDetails.id).label('count'))\
                            .filter((ArticleDetails.summary == None) | (ArticleDetails.summary == ''))\
                            .group_by(ArticleDetails.source)\
                            .order_by(text('count DESC')).limit(3).all()
        print("\n4. Nguồn tin thường xuyên thiếu summary (nếu có):")
        if empty_summaries:
            for src, cnt in empty_summaries:
                print(f"   - {src}: {cnt} bài")
        else:
            print("   - Đa số các nguồn đều lấy được nội dung tóm tắt.")

        print("\nHoàn tất trích xuất dữ liệu.")

    finally:
        db.close()

if __name__ == "__main__":
    generate_report_stats()
