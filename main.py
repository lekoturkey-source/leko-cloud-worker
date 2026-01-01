# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import os
import re
from openai import OpenAI, OpenAIError

app = Flask(__name__)

# =========================
# ENV
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Önce GPT-5 denenecek, olmazsa GPT-4
PRIMARY_MODEL  = os.getenv("OPENAI_MODEL_PRIMARY", "gpt-5")
FALLBACK_MODEL = os.getenv("OPENAI_MODEL_FALLBACK", "gpt-4o")

MAX_SENTENCES = 2

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# HEALTH
# =========================
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# =========================
# OPENAI CALL (WITH FALLBACK)
# =========================
def ask_openai(question: str) -> str:
    system_prompt = (
        "Sen Leko adında bir çocuk robotsun.\n"
        "‘Bilmiyorum’, ‘emin değilim’ deme.\n"
        "En olası doğru bilgiyi net ve sade anlat.\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    # 1️⃣ GPT-5 dene
    try:
        resp = client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=messages,
            timeout=10
        )
        answer = resp.choices[0].message.content.strip()
        return clean_answer(answer)

    except OpenAIError:
        pass  # sessizce fallback'e geç

    # 2️⃣ GPT-4 fallback
    try:
        resp = client.chat.completions.create(
            model=FALLBACK_MODEL,
            messages=messages,
            timeout=10
        )
        answer = resp.choices[0].message.content.strip()
        return clean_answer(answer)

    except OpenAIError:
        return "Bunu biraz daha basit sorar mısın?"

# =========================
# CLEAN OUTPUT
# =========================
def clean_answer(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# =========================
# MAIN ENDPOINT
# =========================
@app.route("/ask", methods=["POST"])
def ask():
    q = (request.json or {}).get("text", "").strip()

    if not q:
        return jsonify({"answer": "Tekrar sorar mısın?"})

    answer = ask_openai(q)
    return jsonify({"answer": answer})

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
