from flask import Flask, request, jsonify
import os
import requests
import urllib.parse
from openai import OpenAI
from datetime import datetime

app = Flask(__name__)

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE = os.getenv("GOOGLE_CSE_ID")

client = OpenAI(api_key=OPENAI_KEY)

# -----------------------------
# Güncel soru mu?
# -----------------------------
def is_current_question(text: str) -> bool:
    keywords = [
        "bugün", "dün", "yarın", "şimdi", "son", "en son",
        "hava", "maç", "kaç oldu", "dolar", "euro",
        "okul", "tatil", "bakan", "başkan"
    ]
    t = text.lower()
    return any(k in t for k in keywords)

# -----------------------------
# Google Search
# -----------------------------
def google_search(query: str):
    if not GOOGLE_KEY or not GOOGLE_CSE:
        return None

    q = urllib.parse.quote(query)
    url = (
        f"https://www.googleapis.com/customsearch/v1"
        f"?key={GOOGLE_KEY}&cx={GOOGLE_CSE}&q={q}&num=5"
    )

    try:
        r = requests.get(url, timeout=6)
        data = r.json()
        items = data.get("items", [])
        if not items:
            return None

        # En üst sonucu al
        return items[0].get("snippet")
    except:
        return None

# -----------------------------
# Routes
# -----------------------------
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/ask", methods=["POST"])
def ask():
    data = request.json or {}
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"answer": "Bir şey sorar mısın?"})

    # 🔥 GÜNCEL SORU → WEB
    if is_current_question(text):
        snippet = google_search(text)

        if snippet:
            # çocuk dostu, kısa
            return jsonify({
                "answer": snippet.split(".")[0] + "."
            })
        else:
            return jsonify({
                "answer": "Bunu şu an net bulamadım."
            })

    # 🔹 NORMAL BİLGİ → GPT
    try:
        resp = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {
                    "role": "system",
                    "content": "7 yaşındaki bir çocuğa kısa ve net cevap ver."
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        )

        return jsonify({
            "answer": resp.choices[0].message.content.strip()
        })

    except Exception:
        return jsonify({
            "answer": "Şu an cevap veremedim."
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
