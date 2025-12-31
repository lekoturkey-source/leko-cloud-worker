from flask import Flask, request, jsonify
import os
import requests
from openai import OpenAI

app = Flask(__name__)

# ---------------------------
# HEALTH CHECK
# ---------------------------
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
        return "Güncel web bilgisine erişilemiyor."

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

        return "\n".join(results) if results else "Güncel sonuç bulunamadı."

    except Exception:
        return "Web araması sırasında hata oluştu."


# ---------------------------
# WEB GEREKİR Mİ? (KESİN KARAR)
# ---------------------------
def needs_web(text: str) -> bool:
    t = text.lower()

    if any(w in t for w in [
        "kim", "nedir", "ne oldu", "kaç",
        "bugün", "şimdi", "en son", "haftaya",
        "yarın", "hava", "maç", "bakan",
        "seçim", "sonuç", "deprem", "kur"
    ]):
        return True

    # Varsayılan: WEB'E ÇIK
    return True


# ---------------------------
# ANA ENDPOINT
# ---------------------------
@app.route("/ask", methods=["POST"])
print("### LEKO CLOUD WORKER v2 – WEB ALWAYS ON ###")
def ask():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"answer": "Bir soru sorar mısın?"})

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"answer": "AI servisi hazır değil."})

        client = OpenAI(api_key=api_key)

        use_web = needs_web(text)
        web_context = web_search(text) if use_web else ""

        prompt = f"""
Kısa, net ve doğru cevap ver.
Emin değilsen bunu açıkça söyle, uydurma.

Soru:
{text}

{"Güncel web bilgileri:" if web_context else ""}
{web_context}
"""

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=200
        )

        answer = response.choices[0].message.content.strip()

        if not answer:
            answer = "Bu soruya şu anda net bir cevap veremiyorum."

        return jsonify({
            "answer": answer,
            "used_web": use_web
        })

    except Exception as e:
        return jsonify({
            "error": "INTERNAL_ERROR",
            "detail": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
