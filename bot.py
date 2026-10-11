import os
import time
import threading
import requests
import yfinance as yf
from telegram import Bot
import openai
from flask import Flask

# راه‌اندازی یک وب‌سرور کوچک برای سازگاری با Render Web Service
app = Flask(__name__)

@app.route('/')
def home():
    return "Gold Fundamental Bot is Running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- خواندن کلیدها از متغیرهای محیطی سرور ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

openai.api_key = OPENAI_API_KEY
bot = Bot(token=TELEGRAM_BOT_TOKEN)
processed_news = set()

def get_market_context():
    """دریافت قیمت لحظه‌ای طلا و داده‌های بازار با مدیریت خطای پیشرفته"""
    gold_price = "N/A"
    dxy_index = "N/A"
    us10y_yield = "N/A"
    
    for symbol in ["GC=F", "XAU=X"]:
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d")
            if not data.empty:
                gold_price = round(float(data['Close'].iloc[-1]), 2)
                break
        except Exception:
            continue

    try:
        dxy = yf.Ticker("DX-Y.NYB").history(period="1d")['Close'].iloc[-1]
        dxy_index = round(float(dxy), 2)
    except Exception:
        pass

    try:
        us10y = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
        us10y_yield = round(float(us10y), 2)
    except Exception:
        pass
        
    return {
        "gold_price": gold_price,
        "dxy_index": dxy_index,
        "us10y_yield": us10y_yield
    }

def analyze_advanced_fundamental(news_title, news_desc, market_data):
    prompt = f"""
تو یک تحلیل‌گر ارشد و مدیریت ریسک بازار طلا (XAU/USD) هستی.
خبر جدید:
- عنوان: {news_title}
- شرح: {news_desc}

وضعیت لحظه‌ای بازار:
- قیمت طلا: {market_data['gold_price']} دلار
- شاخص دلار (DXY): {market_data['dxy_index']}
- نرخ بازدهی اوراق ۱۰ ساله آمریکا: {market_data['us10y_yield']}%

لطفاً خروجی را دقیقاً در قالب فرمت زیر به زبان فارسی تنظیم کن:

📊 **تحلیل جامع فاندامنتال طلا**
---
📌 **خبر:** [ترجمه روان عنوان]
🔥 **درجه اهمیت:** [کم / متوسط / بسیار بالا (بحرانی)]

💡 **تحلیل تأثیر بر بازار:**
[توضیح کامل اثر خبر بر تورم، نرخ بهره، دلار و در نهایت طلا]

🌐 **تطبیق با وضعیت لحظه‌ای:**
[توضیح نحوه واکنش طلا با توجه به داده‌های لحظه‌ای بازار]

📈 **سناریوهای احتمالی حرکت:**
- **سناریوی صعودی:** [شرایط و محدوده تقریبی هدف]
- **سناریوی نزولی:** [شرایط و محدوده تقریبی حمایت]

⚠️ **توصیه مدیریت ریسک:**
[مثلاً: عدم معامله در ۱۰ دقیقه اول / کاهش حجم پوزیشن]
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"خطا در پردازش تحلیل هوش مصنوعی: {e}"

def fetch_latest_news():
    try:
        url = f"https://newsapi.org/v2/everything?q=gold+fed+inflation+interest+rate&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
        response = requests.get(url)
        data = response.json()
        return data.get("articles", [])[:2]
    except Exception as e:
        print(f"خطا در دریافت اخبار: {e}")
        return []

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

def send_test_message():
    """ارسال پیام تست اولیه برای بررسی اتصال تلگرام"""
    test_text = "🎉 **ربات تحلیل فاندامنتال طلا با موفقیت روشن شد!**\n\nسیستم آماده رصد اخبار و تحلیل بازار است."
    send_telegram_alert(test_text)

def bot_main_loop():
    print("🚀 حلقه پردازش اخبار طلا شروع به کار کرد...")
    while True:
        news_list = fetch_latest_news()
        market_data = get_market_context()
        
        for news in news_list:
            news_id = news.get("url")
            if news_id and news_id not in processed_news:
                title = news.get("title") or "بدون عنوان"
                desc = news.get("description") or "بدون توضیحات"
                
                analysis_report = analyze_advanced_fundamental(title, desc, market_data)
                send_telegram_alert(analysis_report)
                
                processed_news.add(news_id)
                time.sleep(3)
                
        time.sleep(180)

if __name__ == "__main__":
    # اجرای وب‌سرور در یک نخ جداگانه برای جلوگیری از خطای پورت Render
    t = threading.Thread(target=run_web)
    t.start()
    
    # ارسال پیام تست برای اطمینان از صحت اتصال تلگرام
    print("⏳ در حال ارسال پیام تست به تلگرام...")
    send_test_message()
    
    # اجرای حلقه اصلی ربات
    bot_main_loop()
