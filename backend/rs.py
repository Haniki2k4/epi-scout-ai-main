import sys
from rapidfuzz import fuzz
import os
import io
import requests
import time
from datetime import datetime, timedelta
from dateutil import parser
import pytz
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
import feedparser
from http.client import IncompleteRead
import re
import base64
from urllib.parse import urlparse, urlunparse, unquote, urljoin
import json
from bs4 import BeautifulSoup
import argparse

nltk.download('punkt')

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S %Z')
        return json.JSONEncoder.default(self, obj)

TZ_INFOS = {
    "UTC": pytz.utc,
    "EDT": pytz.timezone("America/New_York"),
    "EST": pytz.timezone("America/New_York"),
    "PDT": pytz.timezone("America/Los_Angeles"),
    "PST": pytz.timezone("America/Los_Angeles"),
    "CST": pytz.timezone("America/Chicago"),
    "CDT": pytz.timezone("America/Chicago"),
    "MST": pytz.timezone("America/Denver"),
    "MDT": pytz.timezone("America/Denver"),
    "BST": pytz.timezone("Europe/London"),
    "GMT": pytz.utc,
    "CET": pytz.timezone("Europe/Paris"),
    "CEST": pytz.timezone("Europe/Paris"),
    "ICT": pytz.timezone("Asia/Bangkok"),
    "SGT": pytz.timezone("Asia/Singapore"),
    "JST": pytz.timezone("Asia/Tokyo"),
    "IST": pytz.timezone("Asia/Kolkata"),
}

predefined_keywords = {
    "sebs": "Bại liệt, cúm gia cầm, dịch hạch, đậu mùa, bệnh tả, tay chân miệng, sốt phát ban, sởi, sốt xuất huyết, bạch hầu, ho gà, viêm não nhật bản, viêm não vi rút, thủy đậu, cúm A, cúm B, cúm mùa, não mô cầu, bệnh lạ, viêm phổi nặng, bệnh mới nổi, chưa rõ tác nhân gây bệnh, bùng phát ca bệnh, gia tăng số ca bệnh, gia tăng số lượng người nhập viện, hàng loạt ca bệnh, ổ dịch, vụ dịch, phản ứng nặng sau tiêm vắc xin, tử vong do bệnh truyền nhiễm, tử vong không rõ nguyên nhân, tử vong sau tiêm vắc xin, động vật ốm chết hàng loạt, gia cầm ốm chết, unknown disease, emerging disease, re-emerging disease, reemerging disease, avian influenza, H5N1, Bird Flu, Ebola, MERS, public health emergency, pandemic threat",
    "sgain": "ChatGPT, OpenAI, trí tuệ nhân tạo sinh, GPT-4, học máy, chatbot, đạo đức trí tuệ nhân tạo, trợ lý ảo, học sâu, mạng nơ-ron, xử lý ngôn ngữ tự nhiên, DALL-E, công cụ trí tuệ nhân tạo, đổi mới trí tuệ nhân tạo, mô hình trí tuệ nhân tạo, Grok, Google Brain, tạo sinh văn bản, nội dung trí tuệ nhân tạo, vận hành bởi trí tuệ nhân tạo, ứng dụng trí tuệ nhân tạo, ngành công nghiệp trí tuệ nhân tạo, công nghệ trò chuyện, nhận diện giọng nói, nghiên cứu trí tuệ nhân tạo, cập nhật trí tuệ nhân tạo, mô hình transformer, học tăng cường, sáng tạo trí tuệ nhân tạo, quy định trí tuệ nhân tạo, quản trị trí tuệ nhân tạo, giáo dục trí tuệ nhân tạo, trí tuệ nhân tạo trong y tế, trí tuệ nhân tạo trong tài chính, an toàn trí tuệ nhân tạo, tạo sinh hình ảnh, mô hình ngôn ngữ, trí tuệ nhân tạo hội thoại, phương tiện tổng hợp, trí tuệ nhân tạo tương tác, doanh nghiệp trí tuệ nhân tạo, giải pháp trí tuệ nhân tạo, phát triển trí tuệ nhân tạo, tự động hóa trí tuệ nhân tạo, trò chuyện trí tuệ nhân tạo, ngôn ngữ trí tuệ nhân tạo, trí tuệ nhân tạo tự trị, mô hình ngôn ngữ lớn, bots trí tuệ nhân tạo, tiến bộ trí tuệ nhân tạo, triển khai trí tuệ nhân tạo, trí tuệ nhân tạo"
}

def parse_date(date_string):
    try:
        dt = parser.parse(date_string, tzinfos=TZ_INFOS)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.utc)
        return dt
    except ValueError:
        return None

def summarize_text(text, max_sentences=3):
    sentences = sent_tokenize(text)
    return ' '.join(sentences[:max_sentences])

def fetch_and_filter_article(url):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        description = ""
        for tag in ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']:
            desc = soup.select_one(tag)
            if desc and desc.get('content'):
                description = desc['content'].strip()
                break
        if not description:
            paragraphs = soup.find_all("p")
            for p in paragraphs:
                text = p.get_text().strip()
                if len(word_tokenize(text)) > 10:
                    description = text
                    break
        return summarize_text(description)
    except:
        return None

def trim_url(url):
    decoded_url = unquote(url)
    parsed_url = urlparse(decoded_url)
    return urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))

def extract_original_link(url):
    match = re.search(r'url=(https?://[^&]+)', url)
    return match.group(1) if match else url

def get_source_url(source_url):
    url = urlparse(source_url)
    path = url.path.split('/')
    if url.hostname == "news.google.com" and len(path) > 1 and path[-2] == "articles":
        base64_str = path[-1]
        decoded_bytes = base64.urlsafe_b64decode(base64_str + '==')
        decoded_str = decoded_bytes.decode('latin1')
        prefix = bytes([0x08, 0x13, 0x22]).decode('latin1')
        if decoded_str.startswith(prefix):
            decoded_str = decoded_str[len(prefix):]
        suffix = bytes([0xd2, 0x01, 0x00]).decode('latin1')
        if decoded_str.endswith(suffix):
            decoded_str = decoded_str[:-len(suffix)]
        bytes_array = bytearray(decoded_str, 'latin1')
        length = bytes_array[0]
        decoded_str = decoded_str[2:length+1] if length >= 0x80 else decoded_str[1:length+1]
        return decoded_str
    return source_url

def process_keywords(keywords):
    processed = []
    for keyword in keywords:
        key = keyword.strip().lower()
        if key in predefined_keywords:
            processed.extend([kw.strip() for kw in predefined_keywords[key].split(",")])
        else:
            processed.append(keyword.strip())
    return processed

def run_news_search(keywords, ndays=3):
    feed_urls = [
    'https://yoururllist/rss/home.rss',
    'https://yoururllist.rss',
    'https://yoururllist/rss'
    ]
    keywords = process_keywords(keywords)
    seen_titles = {}
    totalCount = 0
    date_threshold = datetime.now(pytz.utc) - timedelta(days=ndays)
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"Failed to parse {url}: {e}")
            continue
        for entry in feed.entries:
            title = entry.title.strip() if 'title' in entry else None
            link = trim_url(get_source_url(extract_original_link(entry.link))) if 'link' in entry else None
            pub_date = parse_date(entry.get("published", ""))
            if not title or not link or not pub_date or pub_date < date_threshold:
                continue
            normalized_title = title.lower().strip()
            if any(fuzz.ratio(normalized_title, existing) >= 95 for existing in seen_titles):
                continue
            if not any(k.lower() in normalized_title for k in keywords):
                continue
            seen_titles[normalized_title] = title
            snippet = fetch_and_filter_article(link)
            if not snippet or len(word_tokenize(snippet)) < 10:
                continue
            totalCount += 1
            print(f"\n[{totalCount}] {title}")
            print(f"Ngày: {pub_date.strftime('%Y-%m-%d %H:%M')}")
            print(f"Link: {link}")
            print(f"Tóm tắt: {snippet}")
            print("-" * 80)

def run_as_script():
    parser = argparse.ArgumentParser(description="RSS news keyword filter tool")
    parser.add_argument("--keywords", type=str, required=True,
                        help='Comma-separated keywords (e.g., "sốt xuất huyết, bạch hầu") or predefined key like "sebs"')
    parser.add_argument("--days", type=int, default=3,
                        help="Number of past days to include in the search (default: 3)")
    args = parser.parse_args()

    keywords_input = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]
    ndays = args.days

    print(f"Searching news for keywords: {keywords_input}")
    print(f"Searching past {ndays} days\n")

    run_news_search(keywords_input, ndays)

if __name__ == "__main__":
    run_as_script()
