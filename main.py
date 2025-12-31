from flask import Flask, request, jsonify
import os
import requests
from openai import OpenAI
from datetime import datetime

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

client = OpenAI(api_key=OPENAI_API_KEY)


def search_latest_fenerbahce_match():
    """
    Google CSE üzerinden Fenerbahçe'nin en son futbol maçını bulur
    """
    query = "Fenerbahçe son oynanan futbol maçı sonucu"

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": 5,
        "hl": "tr"
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    latest_event = None
    latest_date = None

    for item in data.get("items", []):
        pagemap = item.get("pagemap", {})

        for event in pagemap.get("SportsEvent", []):
            name = event.get("name", "")
            start = event.get("startDate")

            if not name or not start:
                continue

            try:
                event_date = datetime.fromisoformat(start.replace("Z", ""))
            except Exception:
                continue

            if latest_date is None or event_date > latest_date:
                latest_date = event_date
                latest_event = {
                    "name": name,
                    "date": event_date.strftime("%d %B %Y"),
                    "url": event.get("url")
                }

    return latest_event


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/ask", methods=["POST"])
def ask():
    data = request.json or {}
    user_text = data.get("text", "").strip()

    try:
        match_info = None

        if "fenerbahçe" in user_text.lower() and "maç" in user_text.lower():
            match_info = search_latest_fenerbahce_match()

        if match_info:
            system_prompt = f"""
Aşağıda internetten alınmış GÜNCEL ve DOĞRU bir maç bilgisi var.

Maç: {match_info['name']}
Tarih: {match_info['date']}

Bu bilgiye dayanarak kullanıcıya NET ve KISA cevap ver.
Tahmin yapma, uydurma ekleme.
"""

        else:
            system_prompt = """
Kullanıcının sorusuna genel bilgiyle cevap ver.
Güncel veri yoksa bunu açıkça söyle.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # gpt-5 yoksa bile hata vermez
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0.2
        )

        return jsonify({
            "answer": response.choices[0].message.content
        })

    except Exception as e:
        return jsonify({
            "error": "INTERNAL_ERROR",
            "detail": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
