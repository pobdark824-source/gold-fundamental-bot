import os
import time
import threading
import datetime
import requests
import yfinance as yf
from telegram import Bot
import openai
from flask import Flask

# راه‌اندازی وب‌سرور برای حفظ اتصال در Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Gold Fundamental & Calendar Bot is Active!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- دریافت متغیرهای محیطی ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

openai.api_key = OPENAI_API_KEY
bot = Bot(token=TELEGRAM_BOT_TOKEN)

processed_news = set()
notified_events = set()

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload)
    except Exception as e:
        print(f"خطا در ارسال پیام به تلگرام: {e}")

def get_market_context():
    """دریافت قیمت پیش‌فرض یا زنده طلا"""
    gold_price = 2650.0
    try:
        ticker = yf.Ticker("GC=F")
        data = ticker.history(period="1d")
        if not data.empty:
            gold_price = round(float(data['Close'].iloc[-1]), 2)
    except Exception:
        pass
    return {"gold_price": gold_price, "dxy_index": 103.5, "us10y_yield": 4.2}

def fetch_economic_calendar():
    """دریافت داده‌های تقویم اقتصادی روز جاری"""
    try:
        # منبع دریافت تقویم اقتصادی روزانه
        url = "https://n8n.w-trade.org/webhook/calendar"  # یا هر API جایگزین تقویم اقتصادی
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
        # تنها اخبار مهم مرتبط با USD / طلا (High Impact)
        if event.get("impact") == "High" and event.get("currency") in ["USD", "XAU"]:
            event_id = f"{event.get('title')}_{event.get('date')}"
            
            # تبدیل زمان خبر به datetime
            try:
                event_time = datetime.datetime.fromisoformat(event.get("date").replace("Z", "+00:00"))
                time_diff = (event_time - now).total_seconds() / 60.0  # اختلاف زمان به دقیقه
                
                # اگر بین ۵۰ تا ۶۵ دقیقه به خبر مانده باشد و قبلاً آلارم نرفته باشد
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
                    send_telegram_alert(alert_msg)
                    notified_events.add(event_id)
            except Exception as e:
                print(f"خطا در پردازش زمان خبر: {e}")

def check_weekend_warnings():
    """ارسال یادآوری بسته‌شدن بازار و آخر هفته"""
    now = datetime.datetime.now(datetime.timezone.utc)
    # روز جمعه (weekday == 4) ساعت ۲۰:۰۰ گرینویچ
    if now.weekday() == 4 and now.hour == 20 and now.minute < 5:
        event_id = f"weekend_warning_{now.strftime('%Y-%m-%d')}"
        if event_id not in notified_events:
            msg = """
🔔 **یادآوری پایان هفته کاری بازار (Weekend Warning)**
---
💡 بازار جهانی طلا به‌زودی بسته خواهد شد.
⚠️ به دلیل احتمال گپ‌های قیمتی (Gap) در بازگشایی روز یکشنبه/دوشنبه، توصیه می‌شود پوزیشن‌های پرریسک را مدیریت یا تسویه کنید.
            """
            send_telegram_alert(msg)
            notified_events.add(event_id)

def bot_main_loop():
    print("🚀 سیستم مدیریت اخبار، تقویم اقتصادی و آلارم‌ها فعال شد...")
    while True:
        try:
            # ۱. بررسی آلارم ۱ ساعت قبل از اخبار مهم
            check_pre_news_alerts()
            
            # ۲. بررسی یادآوری آخر هفته
            check_weekend_warnings()
            
            # ۳. بررسی اخبار لحظه‌ای منتشرشده
            # (کد تحلیل‌گر AI اخبار)
            
        except Exception as e:
            print(f"خطا در حلقه اصلی: {e}")
            
        time.sleep(180)  # چک کردن هر ۳ دقیقه

if __name__ == "__main__":
    t = threading.Thread(target=run_web)
    t.start()
    bot_main_loop()
