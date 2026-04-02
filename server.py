"""
StockScout AI - Flask Backend
Deploy ל-Render:
  Build Command: pip install -r requirements.txt
  Start Command: gunicorn server:app
  Environment:   ANTHROPIC_API_KEY = sk-ant-...
"""

import os, json, logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

def get_key():
    return os.environ.get("ANTHROPIC_API_KEY", "")

@app.route("/")
def index():
    k = get_key()
    logger.info(f"index called, key set: {bool(k)}")
    return jsonify({"status": "StockScout AI", "api_key_set": bool(k)})

@app.route("/api/status")
def status():
    k = get_key()
    return jsonify({"status": "ok", "api_key_set": bool(k)})

@app.route("/api/analyze", methods=["POST"])
def analyze():
    key = get_key()
    logger.info(f"analyze called, key set: {bool(key)}")
    if not key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set on server"}), 500

    data = request.json or {}
    sym = data.get("sym", "")
    name = data.get("name", sym)
    patterns = data.get("patterns", "Support/Resistance, RSI, Candlestick")
    logger.info(f"Analyzing {sym}")

    prompt = f"""You are an expert stock analyst. Analyze {sym} ({name}) using: {patterns}.
Respond ONLY with valid JSON (no markdown):
{{"ticker":"{sym}","companyName":"Full name","signal":"BUY","signalReason":"one sentence","riskLevel":"Medium","riskExplanation":"2-3 sentences","entryPrice":"$X","targetPrice1":"$X","targetPrice2":"$X","stopLoss":"$X","marketCap":"$XB","sector":"Sector","momentum":"Bullish","volumeTrend":"Above average","technicalAnalysis":"3-4 sentences","fundamentalContext":"2-3 sentences","entryStrategy":"2-3 sentences","exitBullScenario":["TP1: $X","TP2: $X","Trail stop $X"],"exitBearScenario":["Cut at $X","Bounce $X-$X","Recovery signal"],"patterns":["Pattern1","Pattern2"],"newsItems":[{{"headline":"h1","sentiment":"pos","date":"2 days ago"}},{{"headline":"h2","sentiment":"neu","date":"5 days ago"}},{{"headline":"h3","sentiment":"neg","date":"1 week ago"}}],"timeHorizon":"Weeks","confidenceScore":75}}"""

    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        text = msg.content[0].text.replace("```json","").replace("```","").strip()
        logger.info(f"Got response for {sym}")
        return jsonify(json.loads(text))
    except Exception as e:
        logger.error(f"Error analyzing {sym}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/scan", methods=["POST"])
def scan():
    key = get_key()
    logger.info(f"scan called, key set: {bool(key)}")
    if not key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set on server"}), 500

    data = request.json or {}
    caps = data.get("caps", "Small and Mid cap")
    patterns = data.get("patterns", "technical analysis")
    logger.info(f"Scanning caps: {caps}")

    prompt = f"""Stock screener: find 6 interesting stocks in market cap: {caps}. Criteria: {patterns}.
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
        logger.info(f"Scan response: {text[:100]}")
        return jsonify(json.loads(text))
    except Exception as e:
        logger.error(f"Scan error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    k = get_key()
    print(f"Key: {'SET' if k else 'MISSING'}")
    print(f"Running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
