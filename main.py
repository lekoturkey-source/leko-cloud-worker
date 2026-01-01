# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import os
import re
import requests
from openai import OpenAI

app = Flask(__name__)

# =========================
# ENV
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID  = os.getenv("GOOGLE_CSE_ID", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

HTTP_TIMEOUT = 8
MAX_SENTENCES = 2

# =========================
# HEALTH
# =========================
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# =========================
# TOPIC DETECTION
# =========================
def detect_topic(q: str) -> str:
    q = q.lower()

    if any(k in q for k in ["dolar", "euro", "kur", "tl"]):
        return "fx"

    if any(k in q for k in ["hava", "yağmur", "kar", "sıcaklık"]):
        return "weather"

    if any(k in q for k in [
        "maç", "skor", "gol",
        "fener", "beşiktaş", "galatasaray"
    ]):
        return "sport"

    if any(k in q for k in [
        "kimdir", "bakan", "başkanı", "sahibi"
    ]):
        return "wiki"

    return "general"

# =========================
# SITE RULES (KİLİTLİ)
# =========================
SITE_RULES = {
    "fx": "site:tcmb.gov.tr",
    "weather": "site:mgm.gov.tr",
    "sport": "site:tff.org OR site:mackolik.com OR site:beinsports.com.tr",
    "wiki": "site:tr.wikipedia.org",
    "general": "site:aa.com.tr OR site:trthaber.com"
}

# =========================
# GOOGLE SEARCH
# =========================
def google_search(query: str):
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": 5
    }

    try:
        r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json().get("items", [])
    except:
        return []

# =========================
# BUILD CONTEXT
# =========================
def build_context(items):
    blocks = []
    for it in items[:5]:
        title = it.get("title", "")
        snippet = it.get("snippet", "")
        blocks.append(f"{title}. {snippet}")
    return "\n".join(blocks)

# =========================
# OPENAI ANSWER
# =========================
def openai_answer(question: str, context: str) -> str:
    client = OpenAI(api_key=OPENAI_API_KEY)

    system_prompt = (
        "Sen Leko adında bir çocuk robotsun.\n"
        f"Cevapların en fazla {MAX_SENTENCES} kısa cümle olsun.\n"
        "7 yaşındaki çocuk anlayacak şekilde konuş.\n"
        "Kaynak, site adı, link, tarih, analiz anlatma.\n"
        "‘Bulamadım’, ‘emin değilim’, ‘internet yok’ ASLA deme.\n"
        "En olası doğru bilgiyi net söyle.\n"
    )

    user_prompt = f"""
Aşağıdaki bilgiler web sitelerinden alınmıştır.
Bunları kullanarak soruya cevap ver.

BİLGİLER:
{context}

SORU:
{question}
"""

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
    )

    answer = resp.choices[0].message.content.strip()
    answer = re.sub(r"https?://\S+", "", answer)
    answer = re.sub(r"\s+", " ", answer)

    return answer

# =========================
# MAIN ENDPOINT
# =========================
@app.route("/ask", methods=["POST"])
def ask():
    q = (request.json or {}).get("text", "").strip()
    if not q:
        return jsonify({"answer": "Tekrar sorar mısın?"})

    topic = detect_topic(q)
    site_filter = SITE_RULES[topic]

    search_query = f"{site_filter} {q}"
    items = google_search(search_query)

    context = build_context(items)

    answer = openai_answer(q, context)

    return jsonify({"answer": answer})

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
