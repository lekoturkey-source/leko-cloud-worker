from flask import Flask, request, jsonify
import os
import requests
from openai import OpenAI

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID  = os.getenv("GOOGLE_CSE_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# GOOGLE WEB SEARCH
# =========================
def google_search(query):
    r = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": query,
            "num": 5,
            "sort": "date"
        },
        timeout=6
    )
    return r.json().get("items", [])

# =========================
# LLM – SADE ÖZET
# =========================
def summarize_for_child(question, web_text):
    system_prompt = (
        "7 yaşındaki bir çocuğa anlatır gibi cevap ver. "
        "Kısa olsun. Kaynak, site adı veya tarih söyleme. "
        "en güncel hangisi ise onu söyle"
        "şuan tarihin kaç olduğu bul ve aramaya bu tarihten geriye doğru başla"
    )

    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Soru: {question}\n\nİnternetten bulunan bilgiler:\n{web_text}"
            }
        ]
    )
    return response.choices[0].message.content.strip()

# =========================
# ROUTES
# =========================
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/ask", methods=["POST"])
def ask():
    q = (request.json or {}).get("text", "").strip()
    if not q:
        return jsonify({"answer": "Anlayamadım."})

    items = google_search(q)

    if not items:
        return jsonify({"answer": "Bunu internette bulamadım."})

    # Web içeriğini topla
    web_text = " ".join(
        f"{it.get('title','')} {it.get('snippet','')}"
        for it in items
    )

    answer = summarize_for_child(q, web_text)
    return jsonify({"answer": answer})

# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
