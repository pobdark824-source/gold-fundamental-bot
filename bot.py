import os
import time
import threading
import datetime
import requests
import yfinance as yf
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- راه‌اندازی وب‌سرور Flask برای حفظ اتصال در Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Gold Fundamental, Calendar & Health Check Bot is Active!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- دریافت متغیرهای محیطی ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

notified_events = set()

def send_telegram_alert_sync(message):
    """تابع کمکی برای ارسال پیام همگام (Sync) به تلگرام"""
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
    now_time = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    status_message = f"""
🛟 **گزارش سلامت و وضعیت ربات (Health Check)**
---
🤖 **وضعیت سرویس:** ربات کاملاً زنده و آنلاین است (`Online`)
🌐 **وضعیت اتصال بازار (Yahoo):** {market_status}
🧠 **وضعیت هوش مصنوعی (OpenAI):** {ai_status}
⏰ **زمان سرور:** {now_time}
⚙️ **پلتفرم میزبان:** Render (Web Service)

تمام سیستم‌های نظارتی و هشدار فعال هستند! 🚀
    """
    await update.message.reply_text(status_message, parse_mode="Markdown")

def fetch_economic_calendar():
    """دریافت داده‌های تقویم اقتصادی روز جاری"""
    try:
        url = "https://n8n.w-trade.org/webhook/calendar"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"خطا در دریافت تقویم اقتصادی: {e}")
    return []

def check_pre_news_alerts():
    """بررسی اخبار مهم آینده و ارسال آلارم ۱ ساعت قبل از انتشار"""
    now = datetime.datetime.now(datetime.timezone.utc)
    calendar = fetch_economic_calendar()
    
    for event in calendar:
        if event.get("impact") == "High" and event.get("currency") in ["USD", "XAU"]:
            event_id = f"{event.get('title')}_{event.get('date')}"
            try:
                event_time = datetime.datetime.fromisoformat(event.get("date").replace("Z", "+00:00"))
                time_diff = (event_time - now).total_seconds() / 60.0
                
                if 50 <= time_diff <= 65 and event_id not in notified_events:
                    title = event.get("title", "خبر مهم اقتصادی")
                    forecast = event.get("forecast", "نامشخص")
                    previous = event.get("previous", "نامشخص")
                    
                    alert_msg = f"""
⏰ **هشدار انتشار خبر مهم (۱ ساعت آینده)**
---
📌 **عنوان خبر:** {title}
🔴 **درجه اهمیت:** بسیار بالا (High Impact)
📊 **پیش‌بینی بازار:** {forecast}
آمار دوره قبل: {previous}

⚠️ **توصیه تریدینگ:**
حدود ۱ ساعت دیگر نوسانات شدید روی نماد طلا (XAU/USD) پیش‌بینی می‌شود. پوزیشن‌های باز خود را مدیریت کنید.
                    """
                    send_telegram_alert_sync(alert_msg)
                    notified_events.add(event_id)
            except Exception as e:
                print(f"خطا در پردازش زمان خبر: {e}")

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
    """حلقه پس‌زمینه برای بررسی دوره‌ای اخبار و تقویم اقتصادی"""
    print("⏳ حلقه پس‌زمینه اخبار و آلارم‌ها شروع به کار کرد...")
    while True:
        try:
            check_pre_news_alerts()
            check_weekend_warnings()
        except Exception as e:
            print(f"خطا در حلقه پس‌زمینه: {e}")
        time.sleep(180)  # هر ۳ دقیقه یک‌بار

def main():
    # ۱. راه‌اندازی ترد وب‌سرور Flask برای Render
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()

    # ۲. راه‌اندازی ترد وظایف پس‌زمینه (تقویم اقتصادی و آلارم‌ها)
    bg_thread = threading.Thread(target=background_tasks_loop, daemon=True)
    bg_thread.start()

    # ۳. راه‌اندازی ربات تلگرام و ثبت دستور /status
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("status", health_check_command))

    print("🚀 ربات کامل تلگرام با موفقیت اجرا شد و منتظر دستورات است...")
    application.run_polling()

if __name__ == "__main__":
    main()
