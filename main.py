from flask import Flask, request, jsonify
import os
from openai import OpenAI

app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/ask", methods=["POST"])
def ask():
    data = request.json or {}
    text = (data.get("text") or "").strip()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY_NOT_FOUND"}), 500

    if not text:
        return jsonify({"answer": ""})

    client = OpenAI(api_key=api_key)

    try:
        # ✅ GPT-5 DOĞRU ÇAĞRI
        response = client.responses.create(
            model="gpt-5",
            input=text
        )

        # GPT-5 output alma (en güvenli yol)
        answer = response.output_text

        if not answer:
            answer = "Tamam, anladım."

        return jsonify({"answer": answer})

    except Exception as e:
        # ❗ Bu mesaj LEKO'YA GİTMEZ, sadece HTTP
        return jsonify({
            "error": "OPENAI_ERROR",
            "detail": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
