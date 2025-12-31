from flask import Flask, request, jsonify
import os
import re
import requests
from datetime import datetime
from openai import OpenAI

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID  = os.getenv("GOOGLE_CSE_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------------------
# Yardımcılar
# -------------------------------

def is_sports_question(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in [
        "maç", "kaç kaç", "skor", "kiminle", "son maç", "yendi", "berabere"
    ])

def clean_child_answer(text: str) -> str:
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"http\S+", "", text)
    text = text.strip()
    return text[:300]

def extract_score_from_html(html: str):
    patterns = [
        r"(\d+)\s*-\s*(\d+)",
        r"(\d+)\s*–\s*(\d+)"
    ]
    for p in patterns:
        m = re.search(p, html)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
    return None

def google_search(query: str):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "sort": "date",
        "num": 5
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("items", [])

def find_latest_match_answer(query: str):
    items = google_search(query)

    now = datetime.now()
    best = None
    best_date = None

    for item in items:
        snippet = item.get("snippet", "")
        link = item.get("link")

        year_match = re.search(r"(20\d{2})", snippet)
        if year_match:
            year = int(year_match.group(1))
            if abs(now.year - year) > 1:
                continue

        try:
            html = requests.get(link, timeout=10).text
        except:
            continue

        score = extract_score_from_html(html)
        if score:
            best = f"En son maç {score} bitti."
            break

    return best

# -------------------------------
# Routes
# -------------------------------

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"answer": "Bir şey sorabilir misin?"})

        # 1️⃣ Spor / maç sorusuysa → Google + sayfa içi skor
        if is_sports_question(text):
            match_answer = find_latest_match_answer(text)
            if match_answer:
                return jsonify({"answer": match_answer})

        # 2️⃣ Genel güncel bilgi → GPT + Web Tool mantığı
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sen çocuklara konuşan bir yardımcı robottun. "
                        "Cevaplar kısa, net ve güvenilir olmalı. "
                        "Bilmiyorsan uydurma. "
                        "Kaynak, site adı veya link söyleme."
                    )
                },
                {"role": "user", "content": text}
            ]
        )

        answer = response.choices[0].message.content
        return jsonify({"answer": clean_child_answer(answer)})

    except Exception as e:
        return jsonify({
            "error": "INTERNAL_ERROR",
            "detail": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
