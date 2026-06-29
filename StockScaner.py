import time
from datetime import datetime
import pytz  # ఇండియన్ టైమ్ జోన్ కోసం (pip install pytz)
import pandas as pd
import requests
import yfinance as yf
import urllib.parse
import xml.etree.ElementTree as ET
from deep_translator import GoogleTranslator  # 100% ఉచిత తెలుగు ట్రాన్స్‌లేటర్
import threading

# 🚀 FastAPI లైబ్రరీలు
from fastapi import FastAPI
import uvicorn
import os

# =====================================================================
# ⚙️ మీ టెలిగ్రామ్ వివరాలు ఇక్కడ ఎంటర్ చేయండి
# =====================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# FastAPI యాప్ క్రియేషన్ (Render కోసం)
app = FastAPI()

# ✅ కరెక్ట్ కోడ్ (దీన్ని రీప్లేస్ చేయండి సార్)
@app.api_route("/", methods=["GET", "HEAD"])
def home():
    return {"status": "running", "bot_name": "Chanti 50EMA AI Scanner", "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

def send_telegram_alert(message, disable_preview=True):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ BOT_TOKEN లేదా CHAT_ID సెట్ చేయలేదు!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": disable_preview}
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"⚠️ టెలిగ్రామ్ మెసేజ్ పంపడంలో విఫలం: {response.text}")
    except Exception as e:
        print(f"⚠️ టెలిగ్రామ్ నెట్‌వర్క్ ఎర్రర్: {e}")

def get_cnbc_news_free(stock_name):
    try:
        search_query = f"{stock_name} share news CNBC"
        encoded_query = urllib.parse.quote(search_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
        
        response = requests.get(rss_url, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            
            if items:
                first_item = items[0]
                english_title = first_item.find('title').text
                google_news_link = first_item.find('link').text
                
                original_link = google_news_link
                try:
                    res = requests.head(google_news_link, allow_redirects=True, timeout=5)
                    original_link = res.url
                except:
                    try:
                        res = requests.get(google_news_link, timeout=5)
                        original_link = res.url
                    except:
                        pass
                
                telugu_news = GoogleTranslator(source='en', target='te').translate(english_title)
                return telugu_news, original_link
                
        return "ఈరోజు ప్రత్యేకメディア వార్తలు ఏవీ లభించలేదు.", None
    except Exception as e:
        print(f"⚠️ వార్త సేకరించడంలో లోపం: {e}")
        return "వార్తలను సేకరించడంలో సాంకేతిక లోపం జరిగింది.", None

def scan_chanti_best_logic(df, boring_pct=50, lookback=50):
    if len(df) < lookback + 5:
        return df

    O = df['Open'].to_numpy().flatten()
    H = df['High'].to_numpy().flatten()
    L = df['Low'].to_numpy().flatten()
    C = df['Close'].to_numpy().flatten()
    N = len(df)

    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    ema_50 = df['EMA_50'].to_numpy().flatten()

    is_boring = [False] * N
    for i in range(N):
        body = abs(C[i] - O[i])
        range_val = H[i] - L[i]
        if range_val > 0 and (body / range_val) * 100 <= boring_pct:
            is_boring[i] = True

    long_signals = [False] * N
    short_signals = [False] * N

    zone_high = None
    zone_low = None
    price_was_outside_above = False
    price_was_outside_below = False

    for i in range(lookback, N):
        if C[i] > O[i]:
            boring_count = 0
            for b in range(1, 5):
                if is_boring[i - b]:
                    boring_count = b
                else:
                    break

            if boring_count > 0:
                idx_prev = i - (boring_count + 1)
                if C[idx_prev] > O[idx_prev] and C[i] > H[i - 1]:
                    float_max_h = H[i - 1]
                    float_min_l = L[i - 1]
                    
                    if boring_count > 1:
                        for k in range(1, boring_count + 1):
                            float_max_h = max(float_max_h, H[i - k])
                            float_min_l = min(float_min_l, L[i - k])

                    support_found = False
                    for j in range(boring_count + 2, lookback + 1):
                        idx_j = i - j
                        if idx_j < 0: break
                        if H[idx_j] > float_max_h or L[idx_j] < float_min_l: break
                        if L[idx_j] >= float_min_l and L[idx_j] <= float_max_h:
                            support_found = True
                            break

                    if support_found:
                        zone_high = float_max_h
                        zone_low = float_min_l
                        price_was_outside_above = False
                        price_was_outside_below = False

        if zone_high is not None and zone_low is not None:
            if C[i] > zone_high: price_was_outside_above = True
            if C[i] < zone_low: price_was_outside_below = True

            if price_was_outside_above and L[i] <= zone_high and C[i] > zone_high and C[i] > O[i] and C[i] > ema_50[i]:
                long_signals[i] = True
                price_was_outside_above = False

            if price_was_outside_below and H[i] >= zone_low and C[i] < zone_low and C[i] < O[i] and C[i] < ema_50[i]:
                short_signals[i] = True
                price_was_outside_below = False

    df['Long_Signal'] = long_signals
    df['Short_Signal'] = short_signals
    return df

combined_stocks = [
    "AARTIIND.NS", "ABB.NS", "ABBOTINDIA.NS", "ABCAPITAL.NS", "ABFRL.NS", "ACC.NS", 
    "ADANIENT.NS", "ADANIGREEN.NS", "ADANIPORTS.NS", "ADANIPOWER.NS", "ALKEM.NS", "AMBUJACEM.NS", 
    "APOLLOHOSP.NS", "APOLLOTYRE.NS", "ASHOKLEY.NS", "ASIANPAINT.NS", "ASTRAL.NS", "ATGL.NS", 
    "ATUL.NS", "AUBANK.NS", "AUROPHARMA.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", 
    "BAJFINANCE.NS", "BALKRISIND.NS", "BALRAMCHIN.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BANKINDIA.NS", 
    "BATAINDIA.NS", "BEL.NS", "BERGEPAINT.NS", "BHARATFORG.NS", "BHARTIARTL.NS", "BHEL.NS", 
    "BIOCON.NS", "BOSCHLTD.NS", "BPCL.NS", "BRITANNIA.NS", "BSOFT.NS", "CANBK.NS", 
    "CANFINHOME.NS", "CHAMBLFERT.NS", "CHOLAFIN.NS", "CIPLA.NS", "COALINDIA.NS", "COFORGE.NS", 
    "COLPAL.NS", "CONCOR.NS", "COROMANDEL.NS", "CROMPTON.NS", "CUB.NS", "CUMMINSIND.NS", 
    "DABUR.NS", "DALBHARAT.NS", "DEEPAKNTR.NS", "DELHIVERY.NS", "DIVISLAB.NS", "DIXON.NS", 
    "DLF.NS", "DMART.NS", "DRREDDY.NS", "EICHERMOT.NS", "ESCORTS.NS", "EXIDEIND.NS", 
    "FEDERALBNK.NS", "GAIL.NS", "GICRE.NS", "GLENMARK.NS", "GNFC.NS", "GODREJCP.NS", 
    "GODREJPROP.NS", "GRANULES.NS", "GRASIM.NS", "GUJGASLTD.NS", "HAL.NS", "HAVELLS.NS", 
    "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDPETRO.NS", 
    "HINDUNILVR.NS", "ICICIBANK.NS", "ICICIGI.NS", "ICICIPRULI.NS", "IDEA.NS", "IDFCFIRSTB.NS", 
    "IEX.NS", "IGL.NS", "INDHOTEL.NS", "INDIACEM.NS", "INDIAMART.NS", "INDIGO.NS", 
    "INDUSINDBK.NS", "INDUSTOWER.NS", "INFY.NS", "IOC.NS", "IPCALAB.NS", "IRCTC.NS", 
    "IREDA.NS", "IRFC.NS", "ITC.NS", "JINDALSTEL.NS", "JIOFIN.NS", "JKCEMENT.NS", 
    "JSWSTEEL.NS", "JUBLFOOD.NS", "KALYANKJIL.NS", "KFINTECH.NS", "KOTAKBANK.NS", "LALPATHLAB.NS", 
    "LICI.NS", "LICHSGFIN.NS", "LT.NS", "LTIMINDTREE.NS", "LTTS.NS", "LUPIN.NS", "M&M.NS", 
    "M&MFIN.NS", "MANAPPURAM.NS", "MARICO.NS", "MARUTI.NS", "MCX.NS", "METROPOLIS.NS", 
    "MFSL.NS", "MGL.NS", "MOTHERSON.NS", "MPHASIS.NS", "MRF.NS", "MUTHOOTFIN.NS", 
    "NATIONALUM.NS", "NAUKRI.NS", "NAVINFLUOR.NS", "NESTLEIND.NS", "NMDC.NS", "NTPC.NS", 
    "OBEROIRLTY.NS", "ONGC.NS", "PAGEIND.NS", "PERSISTENT.NS", "PETRONET.NS", "PFC.NS", 
    "PIDILITIND.NS", "PIIND.NS", "PNB.NS", "POLYCAB.NS", "POLYMED.NS", "POWERGRID.NS", 
    "PVRINOX.NS", "RAMCOCEM.NS", "RBLBANK.NS", "RECLTD.NS", "RELIANCE.NS", "SAIL.NS", 
    "SBICARD.NS", "SBILIFE.NS", "SBIN.NS", "SHREECEM.NS", "SHRIRAMFIN.NS", "SIEMENS.NS", 
    "SRF.NS", "SUNPHARMA.NS", "SUNTV.NS", "SYNGENE.NS", "TATACHEM.NS", "TATACOMM.NS", 
    "TATACONSUM.NS", "TATAMOTORPV.NS", "TATAMOTORCV.NS", "TATAPOWER.NS", "TATASTEEL.NS", "TCS.NS", 
    "TECHM.NS", "TITAN.NS", "TORNTPHARM.NS", "TORNTPOWER.NS", "TRENT.NS", "TVSMOTOR.NS", 
    "UBL.NS", "ULTRACEMCO.NS", "UNITDSPR.NS", "UPL.NS", "VBL.NS", "VEDL.NS", "VOLTAS.NS", 
    "WIPRO.NS", "YESBANK.NS", "ZEEL.NS", "ETERNAL.NS"
]

def run_scanner():
    print("📡 చంటి గెట్ ట్రేడర్ స్కానర్ ప్రారంభమైంది... [50 EMA ഫിൽటర్ ఆన్]")
    total_signals_found = 0

    print("📥 అన్ని స్టాక్స్ డేటాను ఒకేసారి బల్క్ డౌన్‌లోడ్ చేస్తున్నాను...")
    try:
        bulk_data = yf.download(combined_stocks, period="1y", interval="1d", group_by='ticker', progress=False, auto_adjust=False)
    except Exception as e:
        print(f"⚠️ బల్క్ డౌన్‌లోడ్ లోపం: {e}")
        return

    for stock in combined_stocks:
        try:
            if stock not in bulk_data.columns.levels[0]: continue
            df = bulk_data[stock].dropna(subset=['Close']).reset_index()
            
            # 🚀 సేఫ్టీ గార్డ్: కనీసం 55 క్యాండిల్స్ లేకపోతే తప్పుడు సిగ్నల్ రాకుండా స్కిప్ చేస్తుంది
            if df.empty or len(df) < 55:
                continue

            analyzed_df = scan_chanti_best_logic(df)
            if analyzed_df is None or len(analyzed_df) == 0: continue
            
            latest_row = analyzed_df.iloc[-1]
            is_long = bool(latest_row['Long_Signal'])
            is_short = bool(latest_row['Short_Signal'])
            
            if is_long or is_short:
                clean_name = stock.replace(".NS", "")
                close_price = float(latest_row['Close'])
                date_str = latest_row['Date'].strftime('%Y-%m-%d') if 'Date' in df.columns else datetime.now().strftime('%Y-%m-%d')
                
                telugu_news, news_url = get_cnbc_news_free(clean_name)
                
                if news_url:
                    news_section = f"📰 *ఈరోజు ముఖ్య వార్త:* {telugu_news}\n🔗 [అసలైన CNBC వార్త ఇక్కడ చూడండి]({news_url})"
                else:
                    news_section = f"📰 *ఈరోజు ముఖ్య వార్త:* {telugu_news}"

                tradingview_url = f"https://in.tradingview.com/chart/?symbol=NSE:{clean_name}"
                screener_url = f"https://www.screener.in/company/{clean_name}/"
                trendlyne_google = f"https://www.google.com/search?q={clean_name}+trendlyne+share+price"
                moneycontrol_google = f"https://www.google.com/search?q={clean_name}+moneycontrol+share+price"

                if is_long:
                    msg = (
                        f"🟢 *BUY CHANTI SIGNAL!*\n"
                        f"📌 *స్టాక్ పేరు:* `{clean_name}`\n"
                        f"📅 *తేదీ:* {date_str}\n"
                        f"💰 *Close Price:* ₹{close_price:.2f}\n\n"
                        f"{news_section}\n\n"
                        f"🛠️ *1-CLICK ANALYSIS LINKS:*\n"
                        f"📈 [TradingView చార్ట్ చూడండి]({tradingview_url})\n"
                        f"📊 [Screener ఫండమెంటల్స్ చూడండి]({screener_url})\n"
                        f"📰 [Trendlyne న్యూస్]({trendlyne_google})\n"
                        f"💰 [Moneycontrol]({moneycontrol_google})\n"
                    )
                    send_telegram_alert(msg, disable_preview=False)
                    total_signals_found += 1
                    
                elif is_short:
                    msg = (
                        f"🔴 *SELL CHANTI SIGNAL!*\n"
                        f"📌 *స్టాక్ పేరు:* `{clean_name}`\n"
                        f"📅 *తేదీ:* {date_str}\n"
                        f"💰 *Close Price:* ₹{close_price:.2f}\n\n"
                        f"{news_section}\n\n"
                        f"🛠️ *1-CLICK ANALYSIS LINKS:*\n"
                        f"📈 [TradingView చార్ట్ చూడండి]({tradingview_url})\n"
                        f"📊 [Screener ఫండమెంటల్స్ చూడండి]({screener_url})\n"
                        f"📰 [Trendlyne న్యూస్]({trendlyne_google})\n"
                        f"💰 [Moneycontrol]({moneycontrol_google})\n"
                    )
                    send_telegram_alert(msg, disable_preview=False)
                    total_signals_found += 1
                    
                time.sleep(1)
        except Exception:
            continue

    if total_signals_found == 0:
        success_msg = f"✅ *CHANTI SCANNER UPDATE*\n\nసార్, ఈరోజు స్కాన్ విజయవంతంగా పూర్తయింది.\n\n❌ కానీ మన లాజిక్ మరియు 50 EMA ప్రకారం ఏ సిగ్నల్స్ రాలేదు సార్."
        send_telegram_alert(success_msg)
    else:
        success_msg = f"✅ *CHANTI SCANNER UPDATE*\n\nసార్, ఈరోజు స్కాన్ విజయవంతంగా పూర్తయింది. మొత్తం *{total_signals_found}* స్టాక్స్‌లో సిగ్నల్స్ లభించాయి."
        send_telegram_alert(success_msg)

def background_scanner_loop():
    ist = pytz.timezone('Asia/Kolkata')
    already_run_today = False
    
    # సర్వర్ ఆన్ అయిన లింక్ ని పట్టుకోవడం (Self-Ping కోసం)
    app_url = f"https://stockscaner-py.onrender.com/" 
    
    last_ping_time = time.time()
    print("🚀 బాట్ బ్యాక్‌గ్రౌండ్‌లో యాక్టివ్‌గా రన్ అవుతోంది...")

    while True:
        now_ist = datetime.now(ist)
        current_hour = now_ist.hour
        current_minute = now_ist.minute
        current_weekday = now_ist.weekday()

        # 🚀 1. సెల్ఫ్-పింగ్ లాజిక్: ప్రతి 10 నిమిషాలకు (600 సెకన్లు) ఒకసారి తనని తనే టచ్ చేసుకుంటుంది సార్
        if time.time() - last_ping_time >= 600:
            try:
                requests.get(app_url, timeout=5)
                print(f"⏰ [Self-Ping] బాట్ నిద్రపోకుండా తనని తనే మేల్కొలుపుకుంది! సమయం: {now_ist.strftime('%I:%M:%S %p')}")
            except:
                pass
            last_ping_time = time.time()

        # 📊 2. రోజువారీ సాయంత్రం 5:20 PM స్కానర్ ట్రిగ్గర్
        if current_weekday < 5:
            if (current_hour > 17 or (current_hour == 4 and current_minute >= 0)) and not already_run_today:
                print(f"⏰ సమయం సాయంత్రం 5:20 PM దాటింది. స్కాన్ స్టార్ట్ చేస్తున్నాను...")
                run_scanner()
                already_run_today = True
            
            if current_hour == 0:
                already_run_today = False
        else:
            already_run_today = False

        time.sleep(10) # లూప్ కరెక్ట్ గా రన్ అవ్వడానికి చిన్న స్లీప్

if __name__ == "__main__":
    ist = pytz.timezone('Asia/Kolkata')
    startup_time = datetime.now(ist).strftime('%Y-%m-%d %I:%M:%S %p')
    
    start_msg = f"🚀 *CHANTI 50-EMA LIVE BOT STARTED!*\n\nసార్, బాట్ మరియు సెల్ఫ్-పింగ్ సర్వర్ నిద్రపోకుండా పక్కాగా రన్ అయ్యాయి.\n📅 *సమయం:* `{startup_time} (IST)`"
    send_telegram_alert(start_msg)

    scanner_thread = threading.Thread(target=background_scanner_loop, daemon=True)
    scanner_thread.start()

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
