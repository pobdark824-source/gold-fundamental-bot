import os
import time
import threading
import datetime
import requests
import yfinance as yf
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import openai

# --- راه‌اندازی وب‌سرور Flask برای حفظ اتصال در Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Gold Fundamental, News & Health Check Bot is Active!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- دریافت متغیرهای محیطی ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

openai.api_key = OPENAI_API_KEY
processed_news = set()
notified_events = set()

def send_telegram_alert_sync(message):
    """تابع کمکی برای ارسال پیام همگام به تلگرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"خطا در ارسال پیام به تلگرام: {e}")

# --- دستور بررسی سلامت ربات (/status) ---
async def health_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ به دستور /status برای چک کردن سلامت و اتصال اجزای ربات"""
    market_status = "❌ خطا یا عدم دسترسی"
    try:
        test_ticker = yf.Ticker("GC=F")
        hist = test_ticker.history(period="1d")
        if not hist.empty:
            market_status = "✅ متصل و فعال"
    except Exception:
        pass

    ai_status = "✅ فعال (کلید تنظیم شده)" if OPENAI_API_KEY else "❌ تنظیم نشده"
    news_status = "✅ فعال" if NEWS_API_KEY else "❌ تنظیم نشده"
    now_time = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    status_message = f"""
🛟 **گزارش سلامت و وضعیت ربات (Health Check)**
---
🤖 **وضعیت سرویس:** ربات کاملاً زنده و آنلاین است (`Online`)
🌐 **وضعیت اتصال بازار (Yahoo):** {market_status}
🧠 **وضعیت هوش مصنوعی (OpenAI):** {ai_status}
📰 **وضعیت سرویس اخبار (NewsAPI):** {news_status}
⏰ **زمان سرور:** {now_time}
⚙️ **پلتفرم میزبان:** Render (Web Service)

تمام سیستم‌های نظارتی و هشدار فعال هستند! 🚀
    """
    await update.message.reply_text(status_message, parse_mode="Markdown")

def analyze_with_ai(news_title, news_desc):
    """تحلیل خبر با استفاده از هوش مصنوعی OpenAI"""
    if not OPENAI_API_KEY:
        return f"📌 **عنوان:** {news_title}\n\n{news_desc}"
    
    try:
        prompt = f"""
تو یک تحلیلگر حرفه‌ای بازارهای مالی (طلا و فارکس) هستی. خبر زیر منتشر شده است:
عنوان: {news_title}
توضیحات: {news_desc}

لطفاً به زبان فارسی، به صورت کوتاه و حرفه‌ای تحلیل کن که این خبر چه تاثیری روی قیمت طلا (XAU/USD) و شاخص دلار می‌گذارد. ساختار پاسخ شامل:
۱. خلاصه خبر
۲. تاثیر روی طلا (صعودی/نزولی/خنثی)
۳. سطح اهمیت
"""
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"خطا در تحلیل هوش مصنوعی: {e}")
        return f"📌 **{news_title}**\n\n{news_desc}"

def fetch_and_send_live_news():
    """دریافت اخبار لحظه‌ای از NewsAPI و ارسال تحلیل به تلگرام"""
    if not NEWS_API_KEY:
        return
    
    try:
        url = f"https://newsapi.org/v2/everything?q=gold+OR+federal+reserve+OR+inflation+OR+forex&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            articles = response.json().get("articles", [])
            for article in articles[:3]: # بررسی ۳ خبر آخر
                title = article.get("title")
                desc = article.get("description") or ""
                url_link = article.get("url")
                
                if title and title not in processed_news:
                    processed_news.add(title)
                    # محدودسازی حجم حافظه پردازش‌شده‌ها
                    if len(processed_news) > 100:
                        processed_news.pop()
                        
                    # تحلیل با هوش مصنوعی
                    ai_analysis = analyze_with_ai(title, desc)
                    
                    message = f"""
🚨 **تحلیل خبر جدید بازار**
---
{ai_analysis}

🔗 [مشاهده خبر اصلی]({url_link})
                    """
                    send_telegram_alert_sync(message)
                    break # هر بار یک خبر جدید برای جلوگیری از اسپم
    except Exception as e:
        print(f"خطا در دریافت اخبار لحظه‌ای: {e}")

def check_weekend_warnings():
    """ارسال یادآوری بسته‌شدن بازار و آخر هفته"""
    now = datetime.datetime.now(datetime.timezone.utc)
    if now.weekday() == 4 and now.hour == 20 and now.minute < 5:
        event_id = f"weekend_warning_{now.strftime('%Y-%m-%d')}"
        if event_id not in notified_events:
            msg = """
🔔 **یادآوری پایان هفته کاری بازار (Weekend Warning)**
---
💡 بازار جهانی طلا به‌زودی بسته خواهد شد.
⚠️ به دلیل احتمال گپ‌های قیمتی (Gap) در بازگشایی روز یکشنبه/دوشنبه، توصیه می‌شود پوزیشن‌های پرریسک را مدیریت یا تسویه کنید.
            """
            send_telegram_alert_sync(msg)
            notified_events.add(event_id)

def background_tasks_loop():
    """حلقه پس‌زمینه برای بررسی دوره‌ای اخبار و هشدارها"""
    print("⏳ حلقه پس‌زمینه اخبار و مانیتورینگ شروع به کار کرد...")
    while True:
        try:
            fetch_and_send_live_news()
            check_weekend_warnings()
        except Exception as e:
            print(f"خطا در حلقه پس‌زمینه: {e}")
        time.sleep(300)  # بررسی هر ۵ دقیقه یک‌بار

def main():
    # ۱. راه‌اندازی ترد وب‌سرور Flask برای Render
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()

    # ۲. راه‌اندازی ترد وظایف پس‌زمینه (اخبار و مانیتورینگ)
    bg_thread = threading.Thread(target=background_tasks_loop, daemon=True)
    bg_thread.start()

    # ۳. راه‌اندازی ربات تلگرام و ثبت دستور /status
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("status", health_check_command))

    print("🚀 ربات کامل تلگرام با موفقیت اجرا شد و منتظر دستورات است...")
    application.run_polling()

if __name__ == "__main__":
    main()
