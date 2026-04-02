"""
StockScout AI - Flask Backend with Yahoo Finance
Deploy ל-Render:
  Build Command: pip install -r requirements.txt
  Start Command: gunicorn server:app
  Environment:   ANTHROPIC_API_KEY = sk-ant-...
"""

import os, json, logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import yfinance as yf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

def get_key():
    return os.environ.get("ANTHROPIC_API_KEY", "")

def get_stock_data(sym):
    """שולף נתונים אמיתיים מ-Yahoo Finance"""
    try:
        ticker = yf.Ticker(sym)
        info = ticker.info
        hist = ticker.history(period="3mo")

        if hist.empty:
            return None

        # נתונים בסיסיים
        price = round(hist["Close"].iloc[-1], 2)
        prev_close = round(hist["Close"].iloc[-2], 2)
        change_pct = round(((price - prev_close) / prev_close) * 100, 2)
        volume = int(hist["Volume"].iloc[-1])
        avg_volume = int(hist["Volume"].mean())
        high_52w = round(hist["High"].max(), 2)
        low_52w = round(hist["Low"].min(), 2)

        # ממוצעים נעים
        close = hist["Close"]
        ma20 = round(close.rolling(20).mean().iloc[-1], 2)
        ma50 = round(close.rolling(50).mean().iloc[-1], 2) if len(close) >= 50 else None

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi = round((100 - (100 / (1 + rs))).iloc[-1], 1)

        # Volume trend
        vol_trend = "Above average" if volume > avg_volume * 1.2 else "Below average" if volume < avg_volume * 0.8 else "Average"

        # נתוני חברה
        market_cap = info.get("marketCap", 0)
        if market_cap >= 1e12:
            cap_str = f"${round(market_cap/1e12,1)}T"
        elif market_cap >= 1e9:
            cap_str = f"${round(market_cap/1e9,1)}B"
        elif market_cap >= 1e6:
            cap_str = f"${round(market_cap/1e6,1)}M"
        else:
            cap_str = "N/A"

        return {
            "price": price,
            "change_pct": change_pct,
            "volume": volume,
            "avg_volume": avg_volume,
            "vol_trend": vol_trend,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "ma20": ma20,
            "ma50": ma50,
            "rsi": rsi,
            "market_cap": cap_str,
            "sector": info.get("sector", "Unknown"),
            "company_name": info.get("longName", sym),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "52w_position": round(((price - low_52w) / (high_52w - low_52w)) * 100, 1) if high_52w != low_52w else 50,
        }
    except Exception as e:
        logger.error(f"Yahoo Finance error for {sym}: {e}")
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

    # שלב 1: שלוף נתונים אמיתיים
    stock = get_stock_data(sym)

    if stock:
        data_context = f"""
REAL-TIME MARKET DATA for {sym} (as of today):
- Current Price: ${stock['price']} ({'+' if stock['change_pct'] >= 0 else ''}{stock['change_pct']}% today)
- 52-Week Range: ${stock['low_52w']} - ${stock['high_52w']} (currently at {stock['52w_position']}% of range)
- MA20: ${stock['ma20']} | MA50: {f"${stock['ma50']}" if stock['ma50'] else 'N/A'}
- RSI(14): {stock['rsi']}
- Volume: {stock['volume']:,} (avg: {stock['avg_volume']:,}) — {stock['vol_trend']}
- Market Cap: {stock['market_cap']}
- Sector: {stock['sector']}
- P/E Ratio: {stock['pe_ratio']}
"""
        name = stock['company_name']
        market_cap = stock['market_cap']
        sector = stock['sector']
    else:
        data_context = f"No real-time data available for {sym}, use your knowledge."
        name = data.get("name", sym)
        market_cap = "N/A"
        sector = "Unknown"

    prompt = f"""You are an expert stock analyst. Analyze {sym} ({name}) using these technical patterns: {patterns}.

{data_context}

Based on the REAL data above, provide a thorough analysis.
Respond ONLY with valid JSON (no markdown, no backticks):
{{"ticker":"{sym}","companyName":"{name}","signal":"BUY","signalReason":"one sentence based on real data","riskLevel":"Medium","riskExplanation":"2-3 sentences","entryPrice":"$X (based on current ${stock['price'] if stock else 'price'})",  "targetPrice1":"$X","targetPrice2":"$X","stopLoss":"$X","marketCap":"{market_cap}","sector":"{sector}","momentum":"Bullish","volumeTrend":"{stock['vol_trend'] if stock else 'Average'}","technicalAnalysis":"3-4 sentences referencing actual RSI={stock['rsi'] if stock else 'N/A'} MA20={stock['ma20'] if stock else 'N/A'}","fundamentalContext":"2-3 sentences","entryStrategy":"2-3 sentences with specific price levels","exitBullScenario":["TP1: $X — reason","TP2: $X — reason","Trail stop $X"],"exitBearScenario":["Cut at $X — reason","Bounce $X-$X","Recovery signal"],"patterns":["Pattern1","Pattern2"],"newsItems":[{{"headline":"relevant recent news 1","sentiment":"pos","date":"recent"}},{{"headline":"relevant recent news 2","sentiment":"neu","date":"recent"}},{{"headline":"relevant recent news 3","sentiment":"neg","date":"recent"}}],"timeHorizon":"Weeks","confidenceScore":75}}"""

    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        text = msg.content[0].text.replace("```json","").replace("```","").strip()
        result = json.loads(text)
        # הוסף נתוני שוק אמיתיים לתוצאה
        if stock:
            result["currentPrice"] = stock["price"]
            result["changeToday"] = stock["change_pct"]
            result["rsi"] = stock["rsi"]
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

        # הוסף מחיר אמיתי לכל מניה בסריקה
        for s in stocks:
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
    print(f"Key: {'SET' if get_key() else 'MISSING'}")
    print(f"Running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
