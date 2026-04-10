# 🆓 Telegram News Bot — Miễn Phí 100%

## Chi phí: $0/tháng

| Thành phần | Dịch vụ | Giới hạn miễn phí |
|---|---|---|
| AI tóm tắt | Google Gemini 1.5 Flash | 1,500 req/ngày ✅ |
| Chạy tự động | GitHub Actions | 2,000 phút/tháng ✅ |
| Lưu lịch sử | GitHub repo (JSON file) | Không giới hạn ✅ |
| Đăng bài | Telegram Bot API | Không giới hạn ✅ |
| Nguồn tin | RSS Feeds | Miễn phí hoàn toàn ✅ |

---

## Cấu trúc project

```
telegram-news-bot/           ← Tên repo GitHub của bạn
├── bot.py                   ← Code chính
├── requirements.txt         ← Chỉ 2 thư viện nhỏ
├── .gitignore
├── data/
│   └── posted.json          ← Tự tạo khi chạy lần đầu
└── .github/
    └── workflows/
        └── bot.yml          ← Lịch chạy tự động
```

---

## BƯỚC 1 — Lấy 3 key cần thiết

### 🤖 Telegram Bot Token (5 phút)
1. Mở Telegram → tìm **@BotFather**
2. Gõ `/newbot`
3. Đặt tên → đặt username (phải kết thúc bằng `_bot`)
4. Copy token dạng: `7123456789:AAHxxxxxx`

### 📢 Tạo kênh Telegram
1. Tạo kênh mới → đặt username (ví dụ `@vn_finance_news`)
2. Vào Info kênh → Administrators → thêm bot của bạn
3. Cấp quyền **Post Messages**

### 🧠 Gemini API Key (3 phút — hoàn toàn miễn phí)
1. Vào https://aistudio.google.com
2. Đăng nhập Google
3. Click **Get API Key** → **Create API key**
4. Copy key dạng: `AIzaSyxxxxxx`

---

## BƯỚC 2 — Tạo GitHub repo

1. Vào https://github.com → **New repository**
2. Đặt tên: `telegram-news-bot`
3. Chọn **Private** (để bảo vệ code)
4. **Không** tick "Add README" (sẽ upload file lên)

### Upload code lên repo:

```bash
# Trên máy tính của bạn
git clone https://github.com/TEN_BAN/telegram-news-bot
cd telegram-news-bot

# Copy tất cả file vào đây:
# bot.py, requirements.txt, .gitignore
# Tạo thư mục: .github/workflows/
# Copy bot.yml vào .github/workflows/

git add .
git commit -m "Initial bot setup"
git push
```

---

## BƯỚC 3 — Thêm Secrets vào GitHub

> **Secrets** = nơi lưu API key an toàn, không lộ trong code

1. Vào repo GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** và thêm lần lượt:

| Secret Name | Giá trị |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token từ BotFather |
| `TELEGRAM_CHANNEL_ID` | `@ten_kenh_cua_ban` |
| `GEMINI_API_KEY` | Key từ Google AI Studio |

---

## BƯỚC 4 — Kích hoạt GitHub Actions

1. Vào repo → tab **Actions**
2. Nếu thấy thông báo "Workflows aren't being run" → click **I understand, enable workflows**
3. Click vào workflow **Telegram News Bot** → **Run workflow** để test ngay

✅ Nếu thành công, bạn sẽ thấy tin đăng lên kênh Telegram!

---

## Lịch chạy tự động

| Giờ Việt Nam | Loại |
|---|---|
| 07:00 | 📋 Digest sáng — tổng hợp tin qua đêm |
| 12:00 | ⚡ Flash — tin nóng buổi sáng |
| 15:00 | ⚡ Flash — tin nóng buổi chiều |
| 18:00 | 📋 Digest tối — tổng hợp phiên giao dịch |
| 22:00 | 📋 Digest đêm — sự kiện quốc tế |

---

## Ví dụ tin sẽ đăng

```
💹 TÀI CHÍNH 🔴

Fed giữ nguyên lãi suất, phát tín hiệu cắt giảm cuối năm

Cục Dự trữ Liên bang Mỹ giữ nguyên lãi suất 5.25%-5.5% tại
cuộc họp tháng 4. Jerome Powell nói cần thêm bằng chứng lạm phát
hạ nhiệt. Thị trường tăng nhẹ sau quyết định, S&P 500 +0.4%.

💡 Fed cần thêm dữ liệu trước khi cắt lãi suất lần đầu.

🔗 Đọc thêm · 📡 Reuters · 🕐 10:30 (VN)

#FederalReserve #InterestRate #USD
```

---

## Tùy chỉnh nguồn tin

Mở `bot.py`, tìm `RSS_FEEDS` và thêm/bớt nguồn:

```python
RSS_FEEDS = [
    {"name": "VnExpress Kinh tế",
     "url": "https://vnexpress.net/rss/kinh-doanh.rss",
     "cat": "💹 TÀI CHÍNH"},
    # Thêm nguồn tại đây...
]
```

### Một số RSS feeds khác có thể thêm:
- VnExpress: `https://vnexpress.net/rss/the-gioi.rss`
- CafeF: `https://cafef.vn/rss/thi-truong-chung-khoan.rss`
- Nikkei Asia: `https://asia.nikkei.com/rss/feed/nar`
- The Economist: `https://www.economist.com/finance-and-economics/rss.xml`

---

## Gỡ lỗi

**Xem log chạy:**
GitHub → Actions → click vào lần chạy → click job `run-bot`

**Bot không đăng bài:**
- Kiểm tra bot đã là Admin kênh chưa
- Kiểm tra TELEGRAM_CHANNEL_ID có dấu `@` không

**Gemini trả lỗi 429 (too many requests):**
- Giảm MAX_POST xuống 3
- Thêm `time.sleep(2)` giữa các lần gọi API

**posted.json không commit được:**
- Vào Settings → Actions → General → Workflow permissions
- Chọn **Read and write permissions**
