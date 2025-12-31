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
        return ""

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
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            if title or snippet:
                results.append(f"{title}: {snippet}")

        return "\n".join(results)

    except Exception:
        return ""


# ---------------------------
# WEB GEREKİR Mİ?
# ---------------------------
def needs_web(text: str) -> bool:
    keywords = [
        "bugün", "şu an", "şimdi", "en son",
        "son", "sonuç", "maç", "kaç oldu", "güncel"
    ]
    return any(k in text.lower() for k in keywords)


# ---------------------------
# ANA ENDPOINT
# ---------------------------
@app.route("/ask", methods=["POST"])
def ask():
    try:
        payload = request.json or {}
        text = payload.get("text", "").strip()

        if not text:
            return jsonify({"answer": "Bir soru sorar mısın?"})

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"answer": "AI servisi hazır değil."})

        client = OpenAI(api_key=api_key)

        use_web = needs_web(text)
        web_context = web_search(text) if use_web else ""

        prompt = f"""
Aşağıdaki soruya MUTLAKA cevap ver.
Cevap boş OLAMAZ.
Türkçe yaz.
Kısa ve net ol.

Soru:
{text}

Güncel bilgiler:
{web_context if web_context else "Web bilgisi yok."}
"""

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=300
        )

        # 🔒 Güvenli cevap çıkarma
        answer = ""
        if response.choices:
            msg = response.choices[0].message
            if msg and msg.content:
                answer = msg.content.strip()

        # 🔥 Son emniyet (ASLA boş dönmez)
        if not answer:
            if web_context:
                answer = "Güncel web kaynaklarında bu soruya dair net bir bilgi bulunamadı."
            else:
                answer = "Bu soruya şu anda güvenilir bir cevap veremiyorum."

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
