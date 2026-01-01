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

    client = OpenAI(api_key=api_key)

    try:
        response = client.responses.create(
            model="gpt-5",
            input=text
        )

        answer = response.output_text
        return jsonify({"answer": answer})

    except Exception:
        return jsonify({
            "answer": "Şu anda buna cevap veremiyorum, biraz sonra tekrar deneyebiliriz."
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
