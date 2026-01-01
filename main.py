from flask import Flask, request, jsonify
import os
from openai import OpenAI

app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})
print("MODEL:", "gpt-4o-mini")
@app.route("/ask", methods=["POST"])
def ask():
    data = request.json or {}
    text = (data.get("text") or "").strip()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY_NOT_FOUND"}), 500

    client = OpenAI(api_key=api_key)

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",  # hızlı ve yeterli
            messages=[{"role": "user", "content": text}]
        )
        return jsonify({"answer": resp.choices[0].message.content})
    except Exception:
        return jsonify({"answer": "Şu anda cevap veremiyorum."})
