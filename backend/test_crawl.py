from backend import crawler, database, models, crud
from backend.database import SessionLocal, engine

# Ensure tables exist
models.Base.metadata.create_all(bind=engine)

def test_crawl():
    db = SessionLocal()
    try:
        # Full list of disease keywords provided by user
        TEST_KEYWORDS = [
            'Bại liệt', 'cúm gia cầm', 'dịch hạch', 'đậu mùa', 'bệnh tả', 'tay chân miệng', 
            'sốt phát ban', 'sởi', 'sốt xuất huyết', 'bạch hầu', 'ho gà', 'viêm não nhật bản', 
            'viêm não vi rút', 'thủy đậu', 'cúm A', 'cúm B', 'cúm mùa', 'não mô cầu', 
            'bệnh lạ', 'viêm phổi nặng', 'bệnh mới nổi', 'chưa rõ tác nhân gây bệnh', 
            'bùng phát ca bệnh', 'gia tăng số ca bệnh', 'gia tăng số lượng người nhập viện', 
            'hàng loạt ca bệnh', 'ổ dịch', 'vụ dịch', 'phản ứng nặng sau tiêm vắc xin', 
            'tử vong do bệnh truyền nhiễm', 'tử vong không rõ nguyên nhân', 'tử vong sau tiêm vắc xin', 
            'động vật ốm chết hàng loạt', 'gia cầm ốm chết', 'unknown disease', 'emerging disease', 
            're-emerging disease', 'avian influenza', 'H5N1', 'Bird Flu', 'Ebola', 'MERS', 
            'public health emergency', 'pandemic threat'
        ]
        
        print(f"--- Bắt đầu Test Crawl với {len(TEST_KEYWORDS)} từ khóa dịch bệnh ---")
        
        # 1. Add Test Keywords to DB
        print("1. Đang thêm danh sách từ khóa vào Database...")
        count_new = 0
        for kw in TEST_KEYWORDS:
            if not crud.get_keyword_by_text(db, kw):
                crud.create_keyword(db, models.Keyword(text=kw))
                count_new += 1
        print(f"   -> Đã thêm mới {count_new} từ khóa.")
        
        # 2. Run Scan (fetch_unknown=True to see all results)
        print("2. Đang quét RSS từ các nguồn uy tín (VnExpress, DanTri, TuoiTre, ThanhNien, LaoDong, TienPhong...)...")
        result = crawler.scan_news(db, fetch_unknown=True)
        
        print(f"\n--- KẾT QUẢ ---")
        print(f"Số bài viết Uy tín (Tự động lưu): {result.saved_trusted_count}")
        print(f"Số bài viết Nguồn khác (Chờ duyệt): {len(result.unknown_articles)}")
        
        if result.saved_trusted_count > 0:
            print("\n[Bài viết QUAN TRỌNG đã lưu]:")
            # Fetch last few saved
            saved = crud.get_articles(db, limit=5)
            for s in saved:
                print(f" - [{s.source}] {s.title}")
                print(f"   (Link: {s.link})")
                
        if result.unknown_articles:
            print("\n[Bài viết TỪ NGUỒN KHÁC tìm thấy (Top 5)]: ")
            for a in result.unknown_articles[:5]:
                print(f" - [{a.source}] {a.title}")
                print(f"   (Link: {a.link})")
                
        if result.saved_trusted_count == 0 and len(result.unknown_articles) == 0:
            print("CẢNH BÁO: Không tìm thấy tin tức nào khớp với từ khóa.")

    except Exception as e:
        print(f"LỖI: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_crawl()
