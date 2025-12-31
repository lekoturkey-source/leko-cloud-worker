from flask import Flask, request, jsonify
import os
import requests
from openai import OpenAI

app = Flask(__name__)

# ---------------------------
# HEALTH
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

        snippets = []
        for item in data.get("items", []):
            snippets.append(f"{item.get('title')}: {item.get('snippet')}")

        return "\n".join(snippets)

    except Exception:
        return ""


# ---------------------------
# WEB GEREKİR Mİ?
# ---------------------------
def needs_web(text: str) -> bool:
    triggers = [
        "bugün", "şu an", "şimdi", "en son", "son",
        "sonuç", "maç", "ne oldu", "kaç oldu", "güncel"
    ]
    return any(t in text.lower() for t in triggers)


# ---------------------------
# ASK ENDPOINT
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
            return jsonify({"answer": "AI servisi hazır değil."})

        client = OpenAI(api_key=api_key)

        use_web = needs_web(text)
        web_context = web_search(text) if use_web else ""

        prompt = f"""
Aşağıda web bilgileri varsa, cevabını SADECE bu bilgilere dayanarak ver.
Cevap BOŞ OLAMAZ.
Tahmin yapma ama mutlaka özet çıkar.

Soru:
{text}

WEB:
{web_context if web_context else "Web bilgisi bulunamadı."}
"""

        response = client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=200
        )

        answer = response.choices[0].message.content.strip()

        # 🔥 KRİTİK KORUMA
        if not answer:
            if web_context:
                answer = "Web sonuçlarına göre bu konuda net bir özet bulunamadı."
            else:
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
