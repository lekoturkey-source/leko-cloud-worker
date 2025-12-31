from flask import Flask, request, jsonify
import os
import requests
from openai import OpenAI

app = Flask(__name__)


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# ---------------------------
# GOOGLE WEB SEARCH
# ---------------------------
def web_search(query: str) -> str:
    google_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")

    if not google_key or not cse_id:
        return "Web araması yapılamıyor (Google API ayarlı değil)."

    try:
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": google_key,
                "cx": cse_id,
                "q": query,
                "hl": "tr",
                "num": 5
            },
            timeout=8
        )
        r.raise_for_status()
        data = r.json()

        results = []
        for item in data.get("items", []):
            results.append(f"{item.get('title')}: {item.get('snippet')}")

        return "\n".join(results) if results else "Web sonucu bulunamadı."

    except Exception as e:
        return f"Web araması hatası: {str(e)}"


# ---------------------------
# WEB GEREKİR Mİ?
# ---------------------------
def needs_web(text: str) -> bool:
    time_words = [
        "bugün", "şu an", "şimdi", "en son", "son",
        "sonuç", "maç", "ne oldu", "kaç oldu", "güncel"
    ]

    lower = text.lower()
    if any(w in lower for w in time_words):
        return True

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False

    client = OpenAI(api_key=api_key)

    prompt = f"""
Kullanıcı sorusu:
{text}

Bu soru cevaplanırken güncel internet bilgisi gerekir mi?
SADECE EVET veya HAYIR yaz.
"""

    r = client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3
    )

    return "EVET" in r.choices[0].message.content.upper()


# ---------------------------
# ANA ENDPOINT
# ---------------------------
@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"answer": "Bir soru sorar mısın?"})

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"answer": "AI servisi şu anda hazır değil."})

        client = OpenAI(api_key=api_key)

        use_web = needs_web(text)
        web_context = web_search(text) if use_web else ""

        final_prompt = f"""
Kısa, net ve anlaşılır cevap ver.

Soru:
{text}

{"Güncel web bilgileri:" if web_context else ""}
{web_context}
"""

        response = client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": final_prompt}]
        )

        return jsonify({
            "answer": response.choices[0].message.content,
            "used_web": use_web
        })

    except Exception as e:
        return jsonify({
            "error": "INTERNAL_ERROR",
            "detail": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
