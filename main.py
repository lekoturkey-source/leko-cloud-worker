from flask import Flask, request, jsonify
import os
import re
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


def google_search_text(query: str, num: int = 5) -> str:
    """
    Google Custom Search:
    - En yeni sonuçlar üstte
    - Sadece anlamlı metinleri döndürür
    """
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": num,
        "sort": "date",
        "hl": "tr",
        "gl": "tr",
    }

    r = requests.get(url, params=params, timeout=6)
    r.raise_for_status()
    data = r.json()

    texts = []
    for item in data.get("items", []):
        t = item.get("title", "")
        s = item.get("snippet", "")
        combined = f"{t} {s}".strip()

        # SADECE tarih / sezon olan şeyleri at
        if re.fullmatch(r"(19|20)\d{2}[-–/](19|20)\d{2}", combined):
            continue
        if re.fullmatch(r"(19|20)\d{2}[-–/]\d{1,2}", combined):
            continue

        texts.append(combined)

    return " ".join(texts)


def ask_llm_short_child(question: str, context: str) -> str:
    """
    GENEL – kısa – çocuk dostu
    """
    system_prompt = (
        "7 yaşındaki bir çocuğa anlatır gibi cevap ver.\n"
        "Tek cümle olsun.\n"
        "Kısa olsun.\n"
        "Kaynak, tarih, site adı, link yazma.\n"
        "Emin değilsen 'Bunu net bulamadım.' de.\n"
        "Uydurma yapma."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Soru: {question}\nBilgi: {context}"}
    ]

    resp = client.chat.completions.create(
        model="gpt-5",
        messages=messages
    )

    answer = (resp.choices[0].message.content or "").strip()

    # Güvenlik: cevap sadece tarih gibi kalmışsa iptal et
    if re.fullmatch(r"(19|20)\d{2}([-–/]\d{1,2})?", answer):
        return "Bunu net bulamadım."

    return answer


@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json or {}
        text = (data.get("text") or "").strip()

        if not text:
            return jsonify({"answer": "Bunu anlayamadım."})

        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            return jsonify({"answer": "Şu anda internete bağlanamıyorum."}), 500

        context = google_search_text(text)

        if not context.strip():
            return jsonify({"answer": "Bunu net bulamadım."})

        answer = ask_llm_short_child(text, context)

        if not answer:
            answer = "Bunu net bulamadım."

        return jsonify({"answer": answer})

    except Exception:
        return jsonify({"answer": "Şu anda buna cevap veremiyorum."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
