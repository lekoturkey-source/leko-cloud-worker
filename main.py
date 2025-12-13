import os
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()

    if not data or "text" not in data:
        return jsonify({"error": "text field required"}), 400

    user_text = data["text"]

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You are a friendly kids robot assistant."},
            {"role": "user", "content": user_text}
        ]
    )

    answer = response.choices[0].message.content

    return jsonify({
        "answer": answer
    })

