from flask import Flask, request, jsonify
import os
import requests
from datetime import datetime
from openai import OpenAI

app = Flask(__name__)

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE = os.getenv("GOOGLE_CSE_ID")

client = OpenAI(api_key=OPENAI_KEY)

# -------------------------
# Google "En Son" Arama
# -------------------------
def google_latest_search(query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_KEY,
        "cx": GOOGLE_CSE,
        "q": query,
        "num": 5,
        "sort": "date"   # 🔥 Google'daki "En Son"
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    items = data.get("items", [])
    if not items:
        return None

    return items[0]  # 🥇 En güncel sonuç


# -------------------------
# GPT cevap üretimi
# -------------------------
def ask_gpt(prompt):
    try:
        return client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content
    except Exception:
        # 🔁 Otomatik GPT-4 fallback
        return client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/ask", methods=["POST"])
def ask():
    data = request.json or {}
    question = data.get("text", "").strip()

    if not question:
        return jsonify({"error": "EMPTY_QUESTION"}), 400

    try:
        item = google_latest_search(question)

        if not item:
            return jsonify({
                "answer": "Güncel ve tarihli bir kaynak bulamadım."
            })

        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")

        prompt = f"""
Aşağıdaki kaynak en güncel Google sonucudur.

Başlık: {title}
Özet: {snippet}
Kaynak: {link}

Bu bilgiye dayanarak soruya NET, KISA ve TARİHLİ cevap ver.
Tahmin etme. Bilgi yoksa açıkça söyle.
"""

        answer = ask_gpt(prompt)

        return jsonify({
            "answer": answer,
            "source": link
        })

    except Exception as e:
        return jsonify({
            "error": "INTERNAL_ERROR",
            "detail": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
