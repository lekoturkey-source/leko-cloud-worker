from flask import Flask, request, jsonify
import os
import requests
from openai import OpenAI

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

client = OpenAI(api_key=OPENAI_API_KEY)


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


def google_search(query):
    """
    Google Custom Search:
    - en yeni sonuçlar üstte
    - tarih sadece sıralama için
    """
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": query,
            "num": 5,
            "sort": "date"
        }
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()

        snippets = []
        for item in data.get("items", []):
            snippet = item.get("snippet")
            if snippet:
                snippets.append(snippet)

        return " ".join(snippets)

    except Exception:
        return ""


def ask_llm(question, context):
    """
    KISA + ÇOCUK DOSTU + KAYNAKSIZ
    """
    system_prompt = (
        "7 yaşındaki bir çocuğa anlatır gibi cevap ver.\n"
        "Tek cümle olsun.\n"
        "Kısa olsun.\n"
        "Kaynak, tarih, site adı yazma.\n"
        "Emin değilsen açıkça 'Bunu net bulamadım.' de."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Soru: {question}\nBilgi: {context}"}
    ]

    response = client.chat.completions.create(
        model="gpt-5",
        messages=messages
    )

    return response.choices[0].message.content.strip()


@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"answer": "Bunu anlayamadım."})

        # 1️⃣ Google'dan en güncel bilgiyi çek
        context = google_search(text)

        # 2️⃣ Hiçbir şey bulunamazsa
        if not context:
            return jsonify({"answer": "Bunu net bulamadım."})

        # 3️⃣ LLM ile kısa çocuk dostu cevap üret
        answer = ask_llm(text, context)

        return jsonify({"answer": answer})

    except Exception:
        return jsonify({
            "answer": "Şu anda buna cevap veremiyorum."
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
