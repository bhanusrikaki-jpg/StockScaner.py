import os
import time
from datetime import datetime
import pytz  # ఇండియన్ టైమ్ జోన్ కోసం
import pandas as pd
import requests
import yfinance as yf

# =====================================================================
# ⚙️ Render Environment Variables నుండి వివరాలను సురక్షితంగా తీసుకుంటుంది
# =====================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_alert(message):
    # టోకెన్స్ లోడ్ అవ్వకపోతే ఎర్రర్ రాకుండా ప్రొటెక్షన్
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ ఎర్రర్: Render లో BOT_TOKEN లేదా CHAT_ID సెట్ చేయలేదు సార్!")
        return
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"⚠️ టెలిగ్రామ్ మెసేజ్ పంపడంలో విఫలం: {response.text}")
    except Exception as e:
        print(f"⚠️ టెలిగ్రామ్ నెట్‌వర్క్ ఎర్రర్: {e}")

def scan_chanti_best_logic(df, boring_pct=50, lookback=50):
    if len(df) < lookback + 5:
        return df

    O = df['Open'].to_numpy().flatten()
    H = df['High'].to_numpy().flatten()
    L = df['Low'].to_numpy().flatten()
    C = df['Close'].to_numpy().flatten()
    N = len(df)

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

            if price_was_outside_above and L[i] <= zone_high and C[i] > zone_high and C[i] > O[i]:
                long_signals[i] = True
                price_was_outside_above = False

            if price_was_outside_below and H[i] >= zone_low and C[i] < zone_low and C[i] < O[i]:
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
    "LICI.NS", "LICHSGFIN.NS", "LT.NS", "LTIM.NS", "LTTS.NS", "LUPIN.NS", "M&M.NS", 
    "M&MFIN.NS", "MANAPPURAM.NS", "MARICO.NS", "MARUTI.NS", "MCX.NS", "METROPOLIS.NS", 
    "MFSL.NS", "MGL.NS", "MOTHERSON.NS", "MPHASIS.NS", "MRF.NS", "MUTHOOTFIN.NS", 
    "NATIONALUM.NS", "NAUKRI.NS", "NAVINFLUOR.NS", "NESTLEIND.NS", "NMDC.NS", "NTPC.NS", 
    "OBEROIRLTY.NS", "ONGC.NS", "PAGEIND.NS", "PERSISTENT.NS", "PETRONET.NS", "PFC.NS", 
    "PIDILITIND.NS", "PIIND.NS", "PNB.NS", "POLYCAB.NS", "POLYMED.NS", "POWGRID.NS", 
    "PVRINOX.NS", "RAMCOCEM.NS", "RBLBANK.NS", "RECLTD.NS", "RELIANCE.NS", "SAIL.NS", 
    "SBICARD.NS", "SBILIFE.NS", "SBIN.NS", "SHREECEM.NS", "SHRIRAMFIN.NS", "SIEMENS.NS", 
    "SRF.NS", "SUNPHARMA.NS", "SUNTV.NS", "SYNGENE.NS", "TATACHEM.NS", "TATACOMM.NS", 
    "TATACONSUM.NS", "TATAMOTORS.NS", "TATAPOWER.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS", 
    "TITAN.NS", "TORNTPHARM.NS", "TORNTPOWER.NS", "TRENT.NS", "TVSMOTOR.NS", "UBL.NS", 
    "ULTRACEMCO.NS", "UNITDSPR.NS", "UPL.NS", "VBL.NS", "VEDL.NS", "VOLTAS.NS", 
    "WIPRO.NS", "YESBANK.NS", "ZEEL.NS", "ZOMATO.NS"
]

def run_scanner():
    print("📡 చంటి గెట్ ట్రేడర్ స్కానర్ ప్రారంభమైంది... [F&O + Nifty 100]")
    total_signals_found = 0

    for stock in combined_stocks:
        try:
            df = yf.download(stock, period="1y", interval="1d", progress=False, auto_adjust=True)
            if df.empty: continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()

            analyzed_df = scan_chanti_best_logic(df)
            if analyzed_df is None or len(analyzed_df) == 0: continue
            
            latest_row = analyzed_df.iloc[-1]
            is_long = bool(latest_row['Long_Signal']) if not isinstance(latest_row['Long_Signal'], pd.Series) else bool(latest_row['Long_Signal'].iloc[0])
            is_short = bool(latest_row['Short_Signal']) if not isinstance(latest_row['Short_Signal'], pd.Series) else bool(latest_row['Short_Signal'].iloc[0])
            
            if is_long or is_short:
                clean_name = stock.replace(".NS", "")
                date_str = latest_row['Date'].strftime('%Y-%m-%d') if 'Date' in analyzed_df.columns else datetime.now().strftime('%Y-%m-%d')
                
                try:
                    close_price = float(latest_row['Close'].iloc[0]) if hasattr(latest_row['Close'], 'iloc') else float(latest_row['Close'])
                except:
                    close_price = float(latest_row['Close'])

                tradingview_url = f"https://in.tradingview.com/chart/?symbol=NSE:{clean_name}"
                screener_url = f"https://www.screener.in/company/{clean_name}/"
                trendlyne_google = f"https://www.google.com/search?q={clean_name}+trendlyne+share+price"
                moneycontrol_google = f"https://www.google.com/search?q={clean_name}+moneycontrol+share+price"

                if is_long:
                    msg = (
                        f"🟢 *CHANTI BUY SIGNAL!*\n"
                        f"📌 *స్టాక్ పేరు:* `{clean_name}`\n"
                        f"📅 *తేదీ:* {date_str}\n"
                        f"💰 *Close Price:* ₹{close_price:.2f}\n\n"
                        f"🛠️ *1-CLICK ANALYSIS LINKS:*\n"
                        f"📈 [TradingView చార్ట్ చూడండి]({tradingview_url})\n"
                        f"📊 [Screener ఫండమెంటల్స్ చూడండి]({screener_url})\n"
                        f"📰 [Trendlyne న్యూస్]({trendlyne_google})\n"
                        f"💰 [Moneycontrol]({moneycontrol_google})\n"
                    )
                    send_telegram_alert(msg)
                    total_signals_found += 1
                    
                elif is_short:
                    msg = (
                        f"🔴 *CHANTI SELL SIGNAL!*\n"
                        f"📌 *స్టాక్ పేరు:* `{clean_name}`\n"
                        f"📅 *తేదీ:* {date_str}\n"
                        f"💰 *Close Price:* ₹{close_price:.2f}\n\n"
                        f"🛠️ *1-CLICK ANALYSIS LINKS:*\n"
                        f"📈 [TradingView చార్ట్ చూడండి]({tradingview_url})\n"
                        f"📊 [Screener ఫండమెంటల్స్ చూడండి]({screener_url})\n"
                        f"📰 [Trendlyne న్యూస్]({trendlyne_google})\n"
                        f"💰 [Moneycontrol]({moneycontrol_google})\n"
                    )
                    send_telegram_alert(msg)
                    total_signals_found += 1
                    
            time.sleep(0.3)
        except Exception:
            continue

    if total_signals_found == 0:
        success_msg = f"✅ *CHANTI SCANNER UPDATE*\n\nసార్, ఈరోజు స్కాన్ విజయవంతంగా పూర్తయింది.\n\n❌ కానీ మన పక్కా లాజిక్ ప్రకారం ఈరోజు *ఏ స్టాక్‌లోనూ సిగ్నల్స్ దొరకలేదు*."
        send_telegram_alert(success_msg)
    else:
        success_msg = f"✅ *CHANTI SCANNER UPDATE*\n\nసార్, ఈరోజు స్కాన్ పూర్తయింది. మొత్తం *{total_signals_found}* స్టాక్స్‌లో తాజా సిగ్నల్స్ దొరికాయి. వివరాలు పైన పంపాను."
        send_telegram_alert(success_msg)

if __name__ == "__main__":
    ist = pytz.timezone('Asia/Kolkata')
    start_time_str = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
    
    # బాట్ రన్ అవ్వడం స్టార్ట్ కాగానే టెలిగ్రామ్‌కు వెళ్లే Welcome Note
    welcome_msg = f"🚀 *CHANTI SCANNER START అయింది సార్!*\n\n" \
                  f"బాట్ Render లో విజయవంతంగా ప్రారంభమైంది.\n" \
                  f"📅 *ప్రారంభమైన సమయం:* `{start_time_str} IST`\n\n" \
                  f"💡 _గమనిక: ఇక నుండి ప్రతిరోజూ సాయంత్రం కరెక్ట్‌గా *5:00 PM IST* కి బాట్ ఆటోమేటిక్‌గా 242 స్టాక్స్‌ను స్కాన్ చేసి మీకు ఇక్కడే అప్‌డేట్ పంపుతుంది సార్._"
    
    print("🚀 బాట్ ఆన్ అయింది. టెలిగ్రామ్‌కు వెల్‌కమ్ నోట్ పంపుతున్నాను...")
    send_telegram_alert(welcome_msg)
    
    already_run_today = False

    while True:
        now_ist = datetime.now(ist)
        current_hour = now_ist.hour
        current_minute = now_ist.minute
        current_weekday = now_ist.weekday()  # 0=Monday, 5=Saturday, 6=Sunday

        if current_weekday < 5:
            # సాయంత్రం 5:00 PM (Hour == 17, Minute == 00)
            if current_hour == 17 and current_minute == 0 and not already_run_today:
                print(f"⏰ సమయం సాయంత్రం 5:00 PM అయింది. స్కాన్ స్టార్ట్ చేస్తున్నాను... తేదీ: {now_ist.strftime('%Y-%m-%d')}")
                run_scanner()
                already_run_today = True  
            
            if current_hour == 0:
                already_run_today = False
        else:
            already_run_today = False

        time.sleep(30)