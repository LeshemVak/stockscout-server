"""
StockScout AI - Flask Backend
==============================
Deploy ל-Render:
  1. העלה את הקבצים ל-GitHub (server.py + requirements.txt)
  2. Render → New Web Service → חבר repo
  3. Build Command:  pip install -r requirements.txt
  4. Start Command:  gunicorn server:app
  5. Environment → ANTHROPIC_API_KEY = sk-ant-...

הרצה מקומית:
  pip install -r requirements.txt
  set ANTHROPIC_API_KEY=sk-ant-...
  python server.py
"""

import os, json
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic

app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


@app.route("/")
def index():
    return jsonify({"status": "StockScout AI", "api_key_set": bool(API_KEY)})


@app.route("/api/status")
def status():
    return jsonify({"status": "ok", "api_key_set": bool(API_KEY)})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    if not API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY not set on server"}), 500

    data = request.json or {}
    sym = data.get("sym", "")
    name = data.get("name", sym)
    patterns = data.get("patterns", "Support/Resistance, RSI, Candlestick")

    prompt = f"""You are an expert stock analyst. Analyze {sym} ({name}) using: {patterns}.
Respond ONLY with valid JSON (no markdown):
{{"ticker":"{sym}","companyName":"Full name","signal":"BUY","signalReason":"one sentence","riskLevel":"Medium","riskExplanation":"2-3 sentences","entryPrice":"$X","targetPrice1":"$X","targetPrice2":"$X","stopLoss":"$X","marketCap":"$XB","sector":"Sector","momentum":"Bullish","volumeTrend":"Above average","technicalAnalysis":"3-4 sentences","fundamentalContext":"2-3 sentences","entryStrategy":"2-3 sentences","exitBullScenario":["TP1: $X","TP2: $X","Trail stop $X"],"exitBearScenario":["Cut at $X","Bounce $X-$X","Recovery signal"],"patterns":["Pattern1","Pattern2"],"newsItems":[{{"headline":"h1","sentiment":"pos","date":"2 days ago"}},{{"headline":"h2","sentiment":"neu","date":"5 days ago"}},{{"headline":"h3","sentiment":"neg","date":"1 week ago"}}],"timeHorizon":"Weeks","confidenceScore":75}}"""

    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        msg = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=1024,
                                     messages=[{"role": "user", "content": prompt}])
        text = msg.content[0].text.replace("```json","").replace("```","").strip()
        return jsonify(json.loads(text))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scan", methods=["POST"])
def scan():
    if not API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY not set on server"}), 500

    data = request.json or {}
    caps = data.get("caps", "Small and Mid cap")
    patterns = data.get("patterns", "technical analysis")

    prompt = f"""Stock screener: find 6 interesting stocks in market cap: {caps}. Criteria: {patterns}.
Respond ONLY with valid JSON: {{"stocks":[{{"sym":"T","name":"Name","marketCap":"$XB","signal":"BUY","score":80,"reason":"reason","sector":"Sector"}}]}}"""

    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        msg = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=1024,
                                     messages=[{"role": "user", "content": prompt}])
        text = msg.content[0].text.replace("```json","").replace("```","").strip()
        return jsonify(json.loads(text))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"✅ Key: {'מוגדר' if API_KEY else '❌ חסר'}")
    print(f"🚀 http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
