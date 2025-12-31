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

        texts = []
        for item in data.get("items", []):
            texts.append(f"{item.get('title')}: {item.get('snippet')}")

        return "\n".join(texts)

    except Exception:
        return ""


# ---------------------------
# ANA ENDPOINT
# ---------------------------
@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"answer": "Bir soru sorar mısın?", "used_web": False})

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"answer": "AI servisi şu anda hazır değil.", "used_web": False})

        client = OpenAI(api_key=api_key)

        web_context = web_search(text)

        prompt = f"""
Sen Leko adında, kullanıcıya net cevap veren bir asistansın.

KURALLAR:
- ASLA boş cevap verme.
- En az 1 cümle yazmak zorundasın.
- En güncel hangisiyse onu ssöyle.
-Popüler olanı hangisiyse onu söyle.
-Çocuk dostu ol.

Soru:
{text}

{"Güncel web bilgileri:" if web_context else ""}
{web_context}
"""

        r = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=200
        )

        answer = (r.choices[0].message.content or "").strip()

        # 🔒 MODEL GÜVENLİK KİLİDİ (heuristic değil)
        if not answer:
            answer = "Bu konuda net bir bilgi üretemedim ama istersen farklı şekilde sorabilirsin."

        return jsonify({
            "answer": answer,
            "used_web": bool(web_context)
        })

    except Exception as e:
        return jsonify({
            "error": "INTERNAL_ERROR",
            "detail": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
