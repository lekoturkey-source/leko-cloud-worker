from flask import Flask, request, jsonify
import os
import requests
from openai import OpenAI

app = Flask(__name__)

# ENV
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

client = OpenAI(api_key=OPENAI_API_KEY)


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# ---------------------------
# GOOGLE WEB SEARCH
# ---------------------------
def web_search(query: str) -> str:
    try:
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": GOOGLE_API_KEY,
                "cx": GOOGLE_CSE_ID,
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
            results.append(
                f"{item.get('title')}: {item.get('snippet')}"
            )

        return "\n".join(results) if results else "Web sonucu bulunamadı."

    except Exception as e:
        return f"Web araması yapılamadı: {str(e)}"


# ---------------------------
# AKIL: WEB GEREKİYOR MU?
# ---------------------------
def needs_web(text: str) -> bool:
    # Güvenlik kilidi: zamansal belirsizlik varsa WEB ZORUNLU
    time_words = [
        "bugün", "şu an", "şimdi", "en son", "son", "sonuç",
        "maç", "ne oldu", "kaç oldu", "güncel"
    ]

    lower = text.lower()
    if any(w in lower for w in time_words):
        return True

    # Modelden ikinci görüş
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



@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"answer": "Bir soru sorar mısın?"})

        # 1️⃣ Web gerekir mi?
        use_web = needs_web(text)

        web_context = ""
        if use_web:
            web_context = web_search(text)

        # 2️⃣ Ana cevap
        final_prompt = f"""
Bir çocuğa veya sade bir kullanıcıya konuşuyorsun.
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

