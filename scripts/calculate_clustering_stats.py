import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from sqlalchemy import func, text

# Thêm thư mục backend vào sys.path để import các module từ app
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.append(backend_dir)

from app.core.database import SessionLocal
from app.modules.news.models import ArticleIdentity, NewsEvent

def calculate_clustering_stats():
    db = SessionLocal()
    try:
        print("="*60)
        print(" THỐNG KÊ KẾT QUẢ GOM CỤM SỰ KIỆN ")
        print("="*60)
        
        # 1. Tổng số bài báo được lưu
        total_articles = db.query(ArticleIdentity).count()
        
        # 2. Tổng số NewsEvent tạo ra
        total_events = db.query(NewsEvent).count()
        
        # 3. Tỷ lệ nén trung bình
        avg_compression = total_articles / total_events if total_events > 0 else 0
        
        # 4. Phân tích chi tiết số bài viết trên mỗi sự kiện
        event_counts = db.query(
            ArticleIdentity.event_id, 
            func.count(ArticleIdentity.id).label('article_count')
        ).filter(ArticleIdentity.event_id != None)\
         .group_by(ArticleIdentity.event_id).all()
         
        events_multi = 0
        events_single = 0
        for ec in event_counts:
            if ec.article_count >= 2:
                events_multi += 1
            else:
                events_single += 1
                
        # Thêm những event không có bài nào liên kết (nếu có, đề phòng)
        event_ids_with_articles = set(ec.event_id for ec in event_counts)
        all_event_ids = set(e.id for e in db.query(NewsEvent.id).all())
        empty_events = len(all_event_ids - event_ids_with_articles)
        events_single += empty_events
        
        # 5. Số bài báo được gán vào event cũ (được gom cụm thành công)
        # Cách 1: Dựa trên cột dedupe_reason chứa "matched_existing_event"
        matched_articles_count = db.query(ArticleIdentity).filter(
            ArticleIdentity.dedupe_reason.like('%matched_existing_event%')
        ).count()
        
        # Tỷ lệ % bài viết được gom cụm
        percentage_matched = (matched_articles_count / total_articles * 100) if total_articles > 0 else 0
        
        # Tỷ lệ % event chỉ có 1 bài
        percentage_single = (events_single / total_events * 100) if total_events > 0 else 0
        
        print(f"- Tổng số bài báo được lưu: {total_articles} bài")
        print(f"- Tổng số NewsEvent tạo ra: {total_events} event")
        print(f"- Tỉ lệ nén trung bình: {avg_compression:.2f} bài/event")
        print(f"- Số event có từ 2 bài trở lên (>= 2 bài): {events_multi} event")
        print(f"- Số event chỉ chứa duy nhất 1 bài: {events_single} event ({percentage_single:.2f}%)")
        print(f"- Số bài được gán vào event cũ (gom cụm thành công): {matched_articles_count} bài ({percentage_matched:.2f}%)")
        print("="*60)
        
        # Top các sự kiện có số bài gom cụm nhiều nhất để làm minh họa
        print("\nTOP CÁC SỰ KIỆN CÓ SỐ BÀI BÁO GOM CỤM NHIỀU NHẤT:")
        top_events = db.query(
            NewsEvent.id,
            NewsEvent.canonical_title,
            NewsEvent.disease_name,
            NewsEvent.location,
            func.count(ArticleIdentity.id).label('article_count')
        ).join(ArticleIdentity, ArticleIdentity.event_id == NewsEvent.id)\
         .group_by(NewsEvent.id)\
         .order_by(text('article_count DESC')).limit(5).all()
         
        for idx, ev in enumerate(top_events, 1):
            print(f"{idx}. Event ID {ev.id}: {ev.disease_name} tại {ev.location or 'Không rõ'}")
            print(f"   - Tiêu đề tiêu biểu: \"{ev.canonical_title}\"")
            print(f"   - Số bài báo đã gom vào: {ev.article_count} bài")
            
        print("\nHoàn tất trích xuất số liệu gom cụm sự kiện.")
        
    finally:
        db.close()

if __name__ == "__main__":
    calculate_clustering_stats()
