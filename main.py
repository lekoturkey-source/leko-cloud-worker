

from flask import Flask, request, jsonify
import os
from openai import OpenAI

app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok"
    })

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json or {}
        text = data.get("text", "")

        # 1️⃣ API KEY KONTROLÜ
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({
                "error": "OPENAI_API_KEY_NOT_FOUND"
            }), 500

        # 2️⃣ OpenAI client
        client = OpenAI(api_key=api_key)

        # 3️⃣ OpenAI çağrısı
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": text}
            ]
        )

        # 4️⃣ HER ZAMAN JSON DÖN
        return jsonify({
            "answer": response.choices[0].message.content
        })

    except Exception as e:
        # ❗ HATA OLURSA BİLE JSON
        return jsonify({
            "error": "INTERNAL_ERROR",
            "detail": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
