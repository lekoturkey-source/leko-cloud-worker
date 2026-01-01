from flask import Flask, request, jsonify
import os
from openai import OpenAI

app = Flask(__name__)

HIKAYE_KEYWORDS = [
    "hikaye", "hikâye", "hikaye anlat", "beraber hikaye", "masal"
]

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/ask", methods=["POST"])
def ask():
    data = request.json or {}
    text = (data.get("text") or "").lower()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY_NOT_FOUND"}), 500

    client = OpenAI(api_key=api_key)

    # 👉 MODEL SEÇİMİ
    is_story = any(k in text for k in HIKAYE_KEYWORDS)
    model = "gpt-5" if is_story else "gpt-4o-mini"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": text}],
            timeout=8 if not is_story else 20
        )
        return jsonify({"answer": response.choices[0].message.content})

    except Exception:
        return jsonify({
            "answer": "Şu anda buna cevap veremiyorum, biraz sonra tekrar deneyebiliriz."
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
