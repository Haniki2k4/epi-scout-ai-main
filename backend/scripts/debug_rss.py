import feedparser
from datetime import datetime
import time

RSS_FEEDS = [
    "https://vnexpress.net/rss/suc-khoe.rss",
    "https://dantri.com.vn/rss/suc-khoe.rss",
    "https://tuoitre.vn/rss/suc-khoe.rss",
    "https://thanhnien.vn/rss/suc-khoe.rss",
    "https://suckhoedoisong.vn/rss/suc-khoe.rss",
    "https://vov.vn/rss/suc-khoe.rss"
]

def debug_rss():
    print(f"--- Đang kiểm tra {len(RSS_FEEDS)} nguồn RSS ---")
    current_time = datetime.utcnow()
    print(f"Thời gian hiện tại (UTC): {current_time}")

    for url in RSS_FEEDS:
        print(f"\n[Checking] {url}...")
        try:
            feed = feedparser.parse(url)
            if feed.bozo:
                print(f"  -> CẢNH BÁO: Lỗi phân tích feed (bozo exception): {feed.bozo_exception}")
            
            print(f"  -> Tìm thấy {len(feed.entries)} bài viết.")
            
            # Print top 3 articles
            for i, entry in enumerate(feed.entries[:3]):
                print(f"    {i+1}. {entry.title}")
                # Try to print published date
                if hasattr(entry, 'published'):
                     print(f"       Published: {entry.published}")
                if hasattr(entry, 'published_parsed'):
                     dt = datetime(*entry.published_parsed[:6])
                     print(f"       Parsed Date (UTC): {dt}")
                else:
                     print("       [!] Không tìm thấy parsed_date")

        except Exception as e:
            print(f"  -> LỖI KẾT NỐI: {e}")

if __name__ == "__main__":
    debug_rss()
