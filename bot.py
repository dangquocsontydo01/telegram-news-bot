#!/usr/bin/env python3
import os, json, hashlib, logging, feedparser, requests, time
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL_ID"]
POSTED_FILE      = Path("data/posted.json")
MAX_POST         = int(os.environ.get("MAX_POST", "8"))

RSS_FEEDS = [
    # Quốc tế
    {"name": "Reuters World",    "url": "https://feeds.reuters.com/reuters/worldNews",           "cat": "🌍 THẾ GIỚI",    "vi": False},
    {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews",        "cat": "💹 TÀI CHÍNH",   "vi": False},
    {"name": "BBC World",        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",            "cat": "🌍 THẾ GIỚI",    "vi": False},
    {"name": "CNBC",             "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "cat": "💹 TÀI CHÍNH",   "vi": False},
    {"name": "Al Jazeera",       "url": "https://www.aljazeera.com/xml/rss/all.xml",             "cat": "🏛️ CHÍNH TRỊ",  "vi": False},
    {"name": "AP Top News",      "url": "https://rsshub.app/apnews/topics/ap-top-news",          "cat": "🌍 THẾ GIỚI",    "vi": False},
    {"name": "Financial Times",  "url": "https://www.ft.com/rss/home",                           "cat": "💹 TÀI CHÍNH",   "vi": False},
    {"name": "Bloomberg Mkts",   "url": "https://feeds.bloomberg.com/markets/news.rss",          "cat": "💹 TÀI CHÍNH",   "vi": False},
    # Việt Nam
    {"name": "VnExpress",        "url": "https://vnexpress.net/rss/kinh-doanh.rss",              "cat": "🇻🇳 VIỆT NAM",   "vi": True},
    {"name": "Tuoi Tre",         "url": "https://tuoitre.vn/rss/kinh-te.rss",                    "cat": "🇻🇳 VIỆT NAM",   "vi": True},
    {"name": "Dan Tri",          "url": "https://dantri.com.vn/kinh-doanh.rss",                  "cat": "🇻🇳 VIỆT NAM",   "vi": True},
    {"name": "Zing News",        "url": "https://zingnews.vn/kinh-te.rss",                       "cat": "🇻🇳 VIỆT NAM",   "vi": True},
    {"name": "CafeF",            "url": "https://cafef.vn/rss/thi-truong-chung-khoan.rss",       "cat": "📈 CHỨNG KHOÁN", "vi": True},
    {"name": "Vietstock",        "url": "https://vietstock.vn/rss/tai-chinh.rss",                "cat": "📈 CHỨNG KHOÁN", "vi": True},
    # Twitter - Chính trị & Kinh tế
    {"name": "Donald Trump",     "url": "https://nitter.poast.org/realDonaldTrump/rss",          "cat": "🏛️ CHÍNH TRỊ",  "vi": False},
    {"name": "Elon Musk",        "url": "https://nitter.poast.org/elonmusk/rss",                 "cat": "🐦 TWITTER",     "vi": False},
    {"name": "Jim Cramer",       "url": "https://nitter.poast.org/jimcramer/rss",                "cat": "🐦 TWITTER",     "vi": False},
    {"name": "Cathie Wood",      "url": "https://nitter.poast.org/CathieDWood/rss",              "cat": "🐦 TWITTER",     "vi": False},
    {"name": "Raoul Pal",        "url": "https://nitter.poast.org/RaoulGMI/rss",                 "cat": "🐦 TWITTER",     "vi": False},
    # Twitter - Crypto KOLs
    {"name": "Michael Saylor",   "url": "https://nitter.poast.org/saylor/rss",                   "cat": "₿ CRYPTO",       "vi": False},
    {"name": "CZ Binance",       "url": "https://nitter.poast.org/cz_binance/rss",               "cat": "₿ CRYPTO",       "vi": False},
    {"name": "Vitalik Buterin",  "url": "https://nitter.poast.org/VitalikButerin/rss",           "cat": "₿ CRYPTO",       "vi": False},
    {"name": "PlanB",            "url": "https://nitter.poast.org/100trillionUSD/rss",           "cat": "₿ CRYPTO",       "vi": False},
    {"name": "Pompliano",        "url": "https://nitter.poast.org/APompliano/rss",               "cat": "₿ CRYPTO",       "vi": False},
    {"name": "Altcoin Daily",    "url": "https://nitter.poast.org/AltcoinDailyio/rss",           "cat": "₿ CRYPTO",       "vi": False},
    {"name": "Willy Woo",        "url": "https://nitter.poast.org/woonomic/rss",                 "cat": "₿ CRYPTO",       "vi": False},
]

KEYWORDS_EN = [
    "fed", "federal reserve", "interest rate", "inflation", "gdp", "recession",
    "war", "sanction", "tariff", "trade", "opec", "oil", "dollar", "euro",
    "yuan", "stock", "nasdaq", "s&p", "imf", "world bank", "nato", "g7", "g20",
    "china", "russia", "ukraine", "middle east", "election", "policy",
    "central bank", "economy", "market", "geopolit",
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "crypto",
    "blockchain", "defi", "nft", "altcoin", "bull", "bear", "halving",
    "binance", "coinbase", "wallet", "token", "web3",
]

KEYWORDS_VI = [
    "kinh tế", "tài chính", "chứng khoán", "lãi suất", "lạm phát",
    "ngân hàng", "đầu tư", "thị trường", "cổ phiếu", "vnindex",
    "gdp", "xuất khẩu", "nhập khẩu", "doanh nghiệp", "tăng trưởng",
    "tỷ giá", "usd", "vàng", "bất động sản", "crypto", "fed",
    "bitcoin", "tiền ảo", "tiền điện tử", "chính sách", "thuế",
]

SKIP_KEYWORDS = ["celebrity", "oscar", "grammy", "football", "nfl", "nba"]

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
            for entry in parsed.entries[:10]:
                url     = entry.get("link", "").strip()
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                if not url or not title:
                    continue
                if url_hash(url) in posted:
                    continue
                text = (title + " " + summary).lower()
                if any(k in text for k in SKIP_KEYWORDS):
                    continue
                if feed["vi"]:
                    if not any(k in text for k in KEYWORDS_VI):
                        continue
                else:
                    if not any(k in text for k in KEYWORDS_EN):
                        continue
                articles.append({
                    "url":     url,
                    "title":   title,
                    "summary": summary[:400],
                    "source":  feed["name"],
                    "cat":     feed["cat"],
                    "hash":    url_hash(url),
                })
        except Exception as e:
            logger.warning(f"Feed error {feed['name']}: {e}")
    logger.info(f"Found {len(articles)} new relevant articles")
    return articles

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def format_message(article: dict) -> str:
    hour   = (datetime.utcnow().hour + 7) % 24
    minute = datetime.utcnow().minute
    summary = article["summary"][:300] if article["summary"] else ""
    return (
        f"{article['cat']}\n\n"
        f"<b>{article['title']}</b>\n\n"
        f"{summary}\n\n"
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
        logger.info("No new articles.")
        return
    for article in articles[:MAX_POST]:
        msg = format_message(article)
        if tg_post(msg):
            logger.info(f"Posted: {article['title'][:60]}")
            posted.add(article["hash"])
        time.sleep(3)
    save_posted(posted)
    logger.info("Done.")

if __name__ == "__main__":
    main()
