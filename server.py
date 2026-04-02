"""
StockScout AI - Flask Backend with Alpha Vantage
Deploy ל-Render:
  Build Command: pip install -r requirements.txt
  Start Command: gunicorn server:app
  Environment:   ANTHROPIC_API_KEY = sk-ant-...
                 ALPHA_VANTAGE_KEY = your-key
"""

import os, json, logging, requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

def get_key():
    return os.environ.get("ANTHROPIC_API_KEY", "")

def get_av_key():
    return os.environ.get("ALPHA_VANTAGE_KEY", "")

def get_stock_data(sym):
    """שולף נתונים אמיתיים מ-Alpha Vantage"""
    av_key = get_av_key()
    if not av_key:
        logger.warning("ALPHA_VANTAGE_KEY not set")
        return None
    try:
        # מחיר נוכחי + שינוי יומי
        quote_url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={sym}&apikey={av_key}"
        quote_res = requests.get(quote_url, timeout=10).json()
        quote = quote_res.get("Global Quote", {})

        if not quote or not quote.get("05. price"):
            logger.error(f"No quote data for {sym}: {quote_res}")
            return None

        price = round(float(quote["05. price"]), 2)
        change_pct = round(float(quote["10. change percent"].replace("%", "")), 2)
        volume = int(quote["06. volume"])
        prev_close = round(float(quote["08. previous close"]), 2)
        high = round(float(quote["03. high"]), 2)
        low = round(float(quote["04. low"]), 2)

        # נתונים טכניים - RSI
        rsi_url = f"https://www.alphavantage.co/query?function=RSI&symbol={sym}&interval=daily&time_period=14&series_type=close&apikey={av_key}"
        rsi_res = requests.get(rsi_url, timeout=10).json()
        rsi_data = rsi_res.get("Technical Analysis: RSI", {})
        rsi = None
        if rsi_data:
            latest_date = sorted(rsi_data.keys())[-1]
            rsi = round(float(rsi_data[latest_date]["RSI"]), 1)

        # ממוצע נע - MA20
        ma_url = f"https://www.alphavantage.co/query?function=SMA&symbol={sym}&interval=daily&time_period=20&series_type=close&apikey={av_key}"
        ma_res = requests.get(ma_url, timeout=10).json()
        ma_data = ma_res.get("Technical Analysis: SMA", {})
        ma20 = None
        if ma_data:
            latest_date = sorted(ma_data.keys())[-1]
            ma20 = round(float(ma_data[latest_date]["SMA"]), 2)

        # נתוני חברה
        overview_url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={sym}&apikey={av_key}"
        overview = requests.get(overview_url, timeout=10).json()

        market_cap_raw = overview.get("MarketCapitalization", "0")
        market_cap_val = int(market_cap_raw) if market_cap_raw.isdigit() else 0
        if market_cap_val >= 1e12:
            cap_str = f"${round(market_cap_val/1e12,1)}T"
        elif market_cap_val >= 1e9:
            cap_str = f"${round(market_cap_val/1e9,1)}B"
        elif market_cap_val >= 1e6:
            cap_str = f"${round(market_cap_val/1e6,1)}M"
        else:
            cap_str = "N/A"

        week_high = overview.get("52WeekHigh", "N/A")
        week_low = overview.get("52WeekLow", "N/A")
        pe = overview.get("TrailingPE", "N/A")
        sector = overview.get("Sector", "Unknown")
        company_name = overview.get("Name", sym)

        vol_trend = "Above average" if volume > 0 else "Average"

        logger.info(f"Got real data for {sym}: ${price} RSI:{rsi} MA20:{ma20}")

        return {
            "price": price,
            "change_pct": change_pct,
            "volume": volume,
            "vol_trend": vol_trend,
            "high_today": high,
            "low_today": low,
            "prev_close": prev_close,
            "week_high": week_high,
            "week_low": week_low,
            "rsi": rsi,
            "ma20": ma20,
            "market_cap": cap_str,
            "sector": sector,
            "company_name": company_name,
            "pe": pe,
        }
    except Exception as e:
        logger.error(f"Alpha Vantage error for {sym}: {e}")
        return None


@app.route("/")
def index():
    return jsonify({"status": "StockScout AI", "api_key_set": bool(get_key())})

@app.route("/api/status")
def status():
    return jsonify({"status": "ok", "api_key_set": bool(get_key())})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    key = get_key()
    if not key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set on server"}), 500

    data = request.json or {}
    sym = data.get("sym", "").upper()
    patterns = data.get("patterns", "Support/Resistance, RSI, Candlestick")
    logger.info(f"Analyzing {sym}")

    stock = get_stock_data(sym)

    if stock:
        data_context = f"""
REAL-TIME MARKET DATA for {sym} (live from Alpha Vantage):
- Current Price: ${stock['price']} ({'+' if stock['change_pct'] >= 0 else ''}{stock['change_pct']}% today)
- Today Range: ${stock['low_today']} - ${stock['high_today']}
- Previous Close: ${stock['prev_close']}
- 52-Week Range: ${stock['week_low']} - ${stock['week_high']}
- RSI(14): {stock['rsi'] if stock['rsi'] else 'N/A'}
- MA20: {f"${stock['ma20']}" if stock['ma20'] else 'N/A'}
- Volume: {stock['volume']:,} — {stock['vol_trend']}
- Market Cap: {stock['market_cap']}
- P/E Ratio: {stock['pe']}
- Sector: {stock['sector']}
"""
        name = stock['company_name']
        market_cap = stock['market_cap']
        sector = stock['sector']
        vol_trend = stock['vol_trend']
        rsi_val = stock['rsi'] or 'N/A'
        ma20_val = stock['ma20'] or 'N/A'
    else:
        data_context = f"No real-time data available for {sym}, use your knowledge."
        name = data.get("name", sym)
        market_cap = "N/A"
        sector = "Unknown"
        vol_trend = "Average"
        rsi_val = "N/A"
        ma20_val = "N/A"

    price_now = f"${stock['price']}" if stock else "current price"

    prompt = f"""You are an expert stock analyst. Analyze {sym} ({name}) using these technical patterns: {patterns}.

{data_context}

Based on the REAL data above, provide analysis with SPECIFIC price levels.
Respond ONLY with valid JSON (no markdown, no backticks):
{{"ticker":"{sym}","companyName":"{name}","signal":"BUY","signalReason":"one sentence based on real data","riskLevel":"Medium","riskExplanation":"2-3 sentences","entryPrice":"{price_now}","targetPrice1":"$X","targetPrice2":"$X","stopLoss":"$X","marketCap":"{market_cap}","sector":"{sector}","momentum":"Bullish","volumeTrend":"{vol_trend}","technicalAnalysis":"3-4 sentences referencing actual RSI={rsi_val} MA20={ma20_val}","fundamentalContext":"2-3 sentences","entryStrategy":"2-3 sentences with specific price levels","exitBullScenario":["TP1: $X — reason","TP2: $X — reason","Trail stop $X"],"exitBearScenario":["Cut at $X — reason","Bounce $X-$X","Recovery signal"],"patterns":["Pattern1","Pattern2"],"newsItems":[{{"headline":"relevant news 1","sentiment":"pos","date":"recent"}},{{"headline":"relevant news 2","sentiment":"neu","date":"recent"}},{{"headline":"relevant news 3","sentiment":"neg","date":"recent"}}],"timeHorizon":"Weeks","confidenceScore":75}}"""

    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        text = msg.content[0].text.replace("```json","").replace("```","").strip()
        result = json.loads(text)
        if stock:
            result["currentPrice"] = stock["price"]
            result["changeToday"] = stock["change_pct"]
            result["rsi"] = stock["rsi"]
            result["ma20"] = stock["ma20"]
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error analyzing {sym}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/scan", methods=["POST"])
def scan():
    key = get_key()
    if not key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set on server"}), 500

    data = request.json or {}
    caps = data.get("caps", "Small and Mid cap")
    patterns = data.get("patterns", "technical analysis")
    logger.info(f"Scanning caps: {caps}")

    prompt = f"""Stock screener: find 6 interesting stocks right now in market cap: {caps}. Criteria: {patterns}.
Respond ONLY with valid JSON (no markdown, no backticks):
{{"stocks":[{{"sym":"TICKER","name":"Name","marketCap":"$XB","signal":"BUY","score":80,"reason":"reason","sector":"Sector"}}]}}"""

    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        text = msg.content[0].text.replace("```json","").replace("```","").strip()
        stocks = json.loads(text).get("stocks", [])

        # הוסף מחיר אמיתי לכל מניה — רק לראשונות (מגבלת API)
        for s in stocks[:3]:
            try:
                sd = get_stock_data(s["sym"])
                if sd:
                    s["price"] = sd["price"]
                    s["changeToday"] = sd["change_pct"]
                    s["rsi"] = sd["rsi"]
            except:
                pass

        return jsonify({"stocks": stocks})
    except Exception as e:
        logger.error(f"Scan error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Anthropic Key: {'SET' if get_key() else 'MISSING'}")
    print(f"Alpha Vantage Key: {'SET' if get_av_key() else 'MISSING'}")
    print(f"Running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
