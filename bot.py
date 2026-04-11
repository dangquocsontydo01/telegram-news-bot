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
    {"name": "Reuters World",   "url": "https://feeds.reuters.com/reuters/worldNews",           "cat": "🏛️ CHÍNH TRỊ"},
    {"name": "AP Top News",     "url": "https://rsshub.app/apnews/topics/ap-top-news",          "cat": "🏛️ CHÍNH TRỊ"},
    {"name": "BBC World",       "url": "http://feeds.bbci.co.uk/news/world/rss.xml",            "cat": "🏛️ CHÍNH TRỊ"},
    {"name": "Reuters Business","url": "https://feeds.reuters.com/reuters/businessNews",        "cat": "💹 FED & KINH TẾ"},
    {"name": "CNBC",            "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "cat": "💹 FED & KINH TẾ"},
    {"name": "Bloomberg Mkts",  "url": "https://feeds.bloomberg.com/markets/news.rss",          "cat": "💹 FED & KINH TẾ"},
    {"name": "Financial Times", "url": "https://www.ft.com/rss/home",                           "cat": "💹 FED & KINH TẾ"},
    {"name": "CoinDesk",        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",       "cat": "₿ CRYPTO"},
    {"name": "CoinTelegraph",   "url": "https://cointelegraph.com/rss",                         "cat": "₿ CRYPTO"},
    {"name": "Decrypt",         "url": "https://decrypt.co/feed",                               "cat": "₿ CRYPTO"},
    {"name": "The Block",       "url": "https://www.theblock.co/rss/all",                       "cat": "₿ CRYPTO"},
    {"name": "VnExpress",       "url": "https://vnexpress.net/rss/kinh-doanh.rss",              "cat": "🇻🇳 VIỆT NAM"},
    {"name": "CafeF",           "url": "https://cafef.vn/rss/thi-truong-chung-khoan.rss",       "cat": "🇻🇳 VIỆT NAM"},
    {"name": "Tuoi Tre",        "url": "https://tuoitre.vn/rss/kinh-te.rss",                    "cat": "🇻🇳 VIỆT NAM"},
]

KEYWORDS_TRUMP = [
    "trump said", "trump says", "trump announced", "trump signed",
    "trump stated", "trump declared", "trump warned", "trump claimed",
    "donald trump said", "donald trump says", "president trump said",
]

KEYWORDS_FED = [
    "federal reserve", "fed rate", "interest rate", "inflation", "cpi",
    "jerome powell", "powell", "fomc", "monetary policy", "rate hike",
    "rate cut", "basis point", "quantitative",
]

KEYWORDS_KOLS = [
    "cz", "changpeng zhao", "binance",
    "elon musk", "elon",
    "vitalik", "vitalik buterin",
    "michael saylor", "saylor", "microstrategy",
]

KEYWORDS_VN_BANK = [
    "ngân hàng nhà nước", "thống đốc", "lãi suất", "tỷ giá",
    "nguyễn thị hồng", "chính sách tiền tệ", "nhnn",
    "lạm phát", "tín dụng",
]

def is_relevant(title, summary):
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

def clean_html(text):
    return re.sub(r"<[^>]+>", "", text).strip()

def load_posted():
    if POSTED_FILE.exists():
        return set(json.loads(POSTED_FILE.read_text(encoding="utf-8")))
    return set()

def save_posted(hashes):
    POSTED_FILE.parent.mkdir(exist_ok=True)
    recent = list(hashes)[-2000:]
    POSTED_FILE.write_text(json.dumps(recent), encoding="utf-8")

def url_hash(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]

def get_market_prices():
    def chg(c):
        arrow = "🔺" if c > 0 else "🔻"
        return f"{arrow}{abs(c):.1f}%"
    lines = []
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin,ethereum", "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=10,
        )
        d = r.json()
        lines.append(f"BTC ${d['bitcoin']['usd']:,.0f} {chg(d['bitcoin']['usd_24h_change'])}")
        lines.append(f"ETH ${d['ethereum']['usd']:,.0f} {chg(d['ethereum']['usd_24h_change'])}")
    except:
        lines.append("BTC --  ETH --")
    for symbol, label in [("^GSPC","SPX"),("GC=F","XAU"),("CL=F","OIL")]:
        try:
            r = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"interval": "1d", "range": "2d"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            res = r.json()["chart"]["result"][0]
            closes = [c for c in res["indicators"]["quote"][0]["close"] if c]
            price = closes[-1]
            prev = closes[-2] if len(closes) > 1 else price
            change = ((price - prev) / prev) * 100
            fmt = f"{price:,.0f}" if price > 100 else f"{price:.2f}"
            lines.append(f"{label} {fmt} {chg(change)}")
        except:
            lines.append(f"{label} --")
    try:
        r = requests.get(
            "https://iboard-query.ssi.com.vn/v2/stock/indices/VNINDEX",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        d = r.json()["data"]
        lines.append(f"VNI {float(d['indexValue']):,.2f} {chg(float(d['percentChange']))}")
    except:
        lines.append("VNI --")
    return "  |  ".join(lines)

def fetch_articles(posted):
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
                    "url": url, "title": title,
                    "summary": summary[:800],
                    "source": feed["name"],
                    "cat": feed["cat"],
                    "hash": url_hash(url),
                    "topic": topic,
                })
        except Exception as e:
            logger.warning(f"Feed error {feed['name']}: {e}")
    logger.info(f"Found {len(articles)} relevant articles")
    return articles

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

PROMPT = "Ban la chuyen gia tai chinh va chinh tri quoc te 20 nam kinh nghiem. Doc bai bao va viet lai bang tieng Viet theo JSON (chi JSON thuan, khong markdown, khong giai thich): {{\"tieu_de\": \"tieu de tieng Viet toi da 15 tu\", \"tom_tat\": \"3-4 cau tom tat su kien chinh\", \"phan_tich\": \"2-3 cau phan tich tac dong thi truong\", \"du_bao\": \"1-2 cau du bao xu huong\", \"muc_do\": \"RAT QUAN TRONG hoac QUAN TRONG hoac DANG CHU Y\"}}. Bai bao: Tieu de: {title}. Nguon: {source}. Noi dung: {content}"

def deepseek_analyze(article):
    prompt = PROMPT.format(
        title=article["title"],
        source=article["source"],
        content=article["summary"][:1500],
    )
    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "max_tokens": 800},
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"DeepSeek error: {e}")
        return None

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def format_message(article, analysis):
    hour   = (datetime.utcnow().hour + 7) % 24
    minute = datetime.utcnow().minute
    muc_do = analysis.get("muc_do", "DANG CHU Y")
    if "RAT QUAN TRONG" in muc_do:
        emoji = "🔴"
    elif "QUAN TRONG" in muc_do:
        emoji = "🟡"
    else:
        emoji = "🟢"
    prices = get_market_prices()
    tieu_de  = analysis.get("tieu_de", article["title"])
    tom_tat  = analysis.get("tom_tat", "")
    phan_tich= analysis.get("phan_tich", "")
    du_bao   = analysis.get("du_bao", "")
    url      = article["url"]
    source   = article["source"]

    msg  = "⚡ <b>Aura Capital 24/7</b>\n"
    msg += "━━━━━━━━━━━━━━━━\n"
    msg += f"<code>{prices}</code>\n"
    msg += "━━━━━━━━━━━━━━━━\n\n"
    msg += f"{emoji} {muc_do}\n\n"
    msg += f"<b>{tieu_de}</b>\n\n"
    msg += f"📌 <b>Tom tat:</b>\n{tom_tat}\n\n"
    msg += f"📊 <b>Phan tich chuyen gia:</b>\n<i>{phan_tich}</i>\n\n"
    msg += f"🔮 <b>Du bao:</b>\n{du_bao}\n\n"
    msg += f"🔗 <a href=\"{url}\">Doc bai goc</a> · 📡 {source} · 🕐 {hour:02d}:{minute:02d} (VN)"
    return msg

def format_fallback(article):
    hour   = (datetime.utcnow().hour + 7) % 24
    minute = datetime.utcnow().minute
    prices = get_market_prices()
    msg  = "⚡ <b>Aura Capital 24/7</b>\n"
    msg += "━━━━━━━━━━━━━━━━\n"
    msg += f"<code>{prices}</code>\n"
    msg += "━━━━━━━━━━━━━━━━\n\n"
    msg += f"<b>{article['title']}</b>\n\n"
    msg += f"{article['summary'][:300]}\n\n"
    msg += f"🔗 <a href=\"{article['url']}\">Doc bai goc</a> · 📡 {article['source']} · 🕐 {hour:02d}:{minute:02d} (VN)"
    return msg

def tg_post(text):
    try:
        r = requests.post(
            f"{TG_API}/sendMessage",
            json={"chat_id": TELEGRAM_CHANNEL, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False},
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
        msg = format_message(article, analysis) if analysis else format_fallback(article)
        if tg_post(msg):
            logger.info(f"Posted: [{article['source']}] {article['title'][:50]}")
            posted.add(article["hash"])
        time.sleep(3)
    save_posted(posted)
    logger.info("Done.")

if __name__ == "__main__":
    main()
