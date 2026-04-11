#!/usr/bin/env python3
import os, json, hashlib, logging, feedparser, requests, time, re
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL_ID"]
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
POSTED_FILE      = Path("data/posted.json")

RSS_FEEDS = [
    # Trump & Chính trị Mỹ
    {"name": "Reuters World",  "url": "https://feeds.reuters.com/reuters/worldNews",           "cat": "🏛️ CHÍNH TRỊ"},
    {"name": "AP Top News",    "url": "https://rsshub.app/apnews/topics/ap-top-news",          "cat": "🏛️ CHÍNH TRỊ"},
    {"name": "BBC World",      "url": "http://feeds.bbci.co.uk/news/world/rss.xml",            "cat": "🏛️ CHÍNH TRỊ"},
    # FED & Kinh tế Mỹ
    {"name": "Reuters Business","url": "https://feeds.reuters.com/reuters/businessNews",       "cat": "💹 FED & KINH TẾ"},
    {"name": "CNBC",           "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "cat": "💹 FED & KINH TẾ"},
    {"name": "Bloomberg Mkts", "url": "https://feeds.bloomberg.com/markets/news.rss",          "cat": "💹 FED & KINH TẾ"},
    {"name": "Financial Times","url": "https://www.ft.com/rss/home",                           "cat": "💹 FED & KINH TẾ"},
    # Crypto KOLs
    {"name": "CoinDesk",       "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",       "cat": "₿ CRYPTO"},
    {"name": "CoinTelegraph",  "url": "https://cointelegraph.com/rss",                         "cat": "₿ CRYPTO"},
    {"name": "Decrypt",        "url": "https://decrypt.co/feed",                               "cat": "₿ CRYPTO"},
    {"name": "The Block",      "url": "https://www.theblock.co/rss/all",                       "cat": "₿ CRYPTO"},
    # Việt Nam - Ngân hàng Nhà nước
    {"name": "VnExpress",      "url": "https://vnexpress.net/rss/kinh-doanh.rss",              "cat": "🇻🇳 VIỆT NAM"},
    {"name": "CafeF",          "url": "https://cafef.vn/rss/thi-truong-chung-khoan.rss",       "cat": "🇻🇳 VIỆT NAM"},
    {"name": "Tuoi Tre",       "url": "https://tuoitre.vn/rss/kinh-te.rss",                    "cat": "🇻🇳 VIỆT NAM"},
]

# Từ khoá lọc tin - CHỈ đăng những tin liên quan
KEYWORDS_TRUMP = [
    "trump said", "trump says", "trump announced", "trump signed",
    "trump stated", "trump declared", "trump warned", "trump claimed",
    "donald trump said", "donald trump says", "president trump said",
    "trump phát biểu", "trump tuyên bố",
]

KEYWORDS_FED = [
    "federal reserve", "fed rate", "interest rate", "inflation", "cpi",
    "jerome powell", "powell", "fomc", "monetary policy", "rate hike",
    "rate cut", "basis point", "quantitative",
]

KEYWORDS_KOLS = [
    "cz", "changpeng zhao", "binance",
    "elon musk", "elon", "tesla", "spacex",
    "vitalik", "vitalik buterin", "ethereum",
    "michael saylor", "saylor", "microstrategy",
]

KEYWORDS_VN_BANK = [
    "ngân hàng nhà nước", "thống đốc", "lãi suất", "tỷ giá",
    "nguyễn thị hồng", "chính sách tiền tệ", "nhnn",
    "lạm phát", "tín dụng", "dự trữ ngoại hối",
]

def is_relevant(title: str, summary: str) -> tuple[bool, str]:
    text = (title + " " + summary).lower()
    if any(k in text for k in KEYWORDS_TRUMP):
        return True, "trump"
    if any(k in text for k in KEYWORDS_FED):
        return True, "fed"
    if any(k in text for k in KEYWORDS_KOLS):
        return True, "kol"
    if any(k in text for k in KEYWORDS_VN_BANK):
        return True, "vnbank"
    return False, ""

def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()

def load_posted() -> set:
    if POSTED_FILE.exists():
        return set(json.loads(POSTED_FILE.read_text(encoding="utf-8")))
    return set()

def save_posted(hashes: set):
    POSTED_FILE.parent.mkdir(exist_ok=True)
    recent = list(hashes)[-2000:]
    POSTED_FILE.write_text(json.dumps(recent), encoding="utf-8")

def url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]

def fetch_articles(posted: set) -> list:
    articles = []
    for feed in RSS_FEEDS:
        try:
            logger.info(f"Fetching {feed['name']}...")
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries[:15]:
                url     = entry.get("link", "").strip()
                title   = entry.get("title", "").strip()
                summary = clean_html(entry.get("summary", entry.get("description", "")).strip())
                if not url or not title:
                    continue
                if url_hash(url) in posted:
                    continue
                relevant, topic = is_relevant(title, summary)
                if not relevant:
                    continue
                articles.append({
                    "url":     url,
                    "title":   title,
                    "summary": summary[:800],
                    "source":  feed["name"],
                    "cat":     feed["cat"],
                    "hash":    url_hash(url),
                    "topic":   topic,
                })
        except Exception as e:
            logger.warning(f"Feed error {feed['name']}: {e}")
    logger.info(f"Found {len(articles)} relevant articles")
    return articles

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

PROMPT = """Bạn là chuyên gia tài chính và chính trị quốc tế với hơn 20 năm kinh nghiệm phân tích thị trường toàn cầu, từng làm việc tại IMF, Goldman Sachs và các tổ chức tài chính hàng đầu thế giới.

Nhiệm vụ: Đọc bài báo bên dưới, hiểu sâu nội dung, rồi viết lại hoàn toàn bằng tiếng Việt với giọng văn của một chuyên gia đang phân tích cho nhà đầu tư Việt Nam.

Trả về JSON (chỉ JSON thuần, không markdown, không giải thích):
{{
  "tieu_de": "Tiêu đề tiếng Việt súc tích, hấp dẫn, ≤15 từ, phản ánh đúng nội dung cốt lõi",
  "tom_tat": "3-4 câu tóm tắt: (1) Sự kiện chính là gì? (2) Ai nói/làm gì? (3) Số liệu cụ thể nếu có. Viết rõ ràng, dễ hiểu cho người Việt",
  "phan_tich": "2-3 câu phân tích chuyên sâu: Tại sao sự kiện này quan trọng? Tác động đến thị trường tài chính, kinh tế Việt Nam và thế giới như thế nào? Góc nhìn của chuyên gia",
  "du_bao": "1-2 câu dự báo cụ thể: Xu hướng tiếp theo sẽ ra sao? Nhà đầu tư cần chú ý điều gì?",
  "muc_do": "QUAN TRỌNG hoặc RẤT QUAN TRỌNG hoặc ĐÁNG CHÚ Ý"
}}

Bài báo cần phân tích:
Tiêu đề: {title}
Nguồn: {source}
Nội dung: {content}
"""

def deepseek_analyze(article: dict) -> dict | None:
    prompt = PROMPT.format(
        title=article["title"],
        source=article["source"],
        content=article["summary"][:1500],
    )
    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 800,
                "temperature": 0.7,
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"DeepSeek error: {e}")
        return None

TOPIC_EMOJI = {
    "trump":  "🇺🇸 TRUMP",
    "fed":    "🏦 FED",
    "kol":    "💬 KOL",
    "vnbank": "🇻🇳 NHNN",
}

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def format_message(article: dict, analysis: dict) -> str:
    hour   = (datetime.utcnow().hour + 7) % 24
    minute = datetime.utcnow().minute
    cat    = TOPIC_EMOJI.get(article["topic"], article["cat"])
    muc_do = analysis.get("muc_do", "ĐÁNG CHÚ Ý")
    muc_do_emoji = "🔴" if "RẤT QUAN TRỌNG" in muc_do else "🟡" if "QUAN TRỌNG" in muc_do else "🟢"

    return (
        f"{cat} {muc_do_emoji} {muc_do}\n\n"
        f"<b>{analysis.get('tieu_de', article['title'])}</b>\n\n"
        f"📌 <b>Tóm tắt:</b>\n{analysis.get('tom_tat', '')}\n\n"
        f"📊 <b>Phân tích chuyên gia:</b>\n<i>{analysis.get('phan_tich', '')}</i>\n\n"
        f"🔮 <b>Dự báo:</b>\n{analysis.get('du_bao', '')}\n\n"
        f"🔗 <a href=\"{article['url']}\">Đọc bài gốc</a>"
        f" · 📡 {article['source']} · 🕐 {hour:02d}:{minute:02d} (VN)"
    ).strip()

def format_fallback(article: dict) -> str:
    hour   = (datetime.utcnow().hour + 7) % 24
    minute = datetime.utcnow().minute
    cat    = TOPIC_EMOJI.get(article["topic"], article["cat"])
    return (
        f"{cat}\n\n"
        f"<b>{article['title']}</b>\n\n"
        f"{article['summary'][:300]}\n\n"
        f"🔗 <a href=\"{article['url']}\">Đọc thêm</a>"
        f" · 📡 {article['source']} · 🕐 {hour:02d}:{minute:02d} (VN)"
    ).strip()

def tg_post(text: str) -> bool:
    try:
        r = requests.post(
            f"{TG_API}/sendMessage",
            json={"chat_id": TELEGRAM_CHANNEL, "text": text,
                  "parse_mode": "HTML", "disable_web_page_preview": False},
            timeout=20,
        )
        ok = r.json().get("ok", False)
        if not ok:
            logger.error(f"Telegram error: {r.json()}")
        return ok
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

def main():
    logger.info("Starting bot")
    posted   = load_posted()
    articles = fetch_articles(posted)

    if not articles:
        logger.info("No relevant articles found.")
        return

    MAX_POST = int(os.environ.get("MAX_POST", "5"))
    for article in articles[:MAX_POST]:
        logger.info(f"Analyzing: {article['title'][:60]}")
        analysis = deepseek_analyze(article)
        time.sleep(2)

        if analysis:
            msg = format_message(article, analysis)
        else:
            msg = format_fallback(article)

        if tg_post(msg):
            logger.info(f"Posted: [{article['source']}] {article['title'][:50]}")
            posted.add(article["hash"])
        time.sleep(3)

    save_posted(posted)
    logger.info("Done.")

if __name__ == "__main__":
    main()
