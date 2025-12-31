from flask import Flask, request, jsonify
import os
import requests
from openai import OpenAI

app = Flask(__name__)

# =========================
# ENV
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID  = os.getenv("GOOGLE_CSE_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# HEALTH
# =========================
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# =========================
# HELPERS
# =========================
def needs_fresh_info(text: str) -> bool:
    """
    Anahtar kelimeye bağlı kalmaz.
    Modelin kendisine sorarak karar verir.
    """
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Kullanıcı sorusu güncel / canlı bilgi "
                        "(haber, maç, fiyat, deprem, seçim, hava, son durum vb.) "
                        "gerektiriyor mu? Sadece EVET veya HAYIR de."
                    )
                },
                {"role": "user", "content": text}
            ],
            max_tokens=3
        )
        answer = r.choices[0].message.content.lower()
        return "evet" in answer
    except:
        return False


def google_search(query: str) -> str:
    """
    Google Custom Search
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return ""

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": 5,
        "hl": "tr"
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        snippets = []

        for item in data.get("items", []):
            snippets.append(
                f"{item.get('title')}: {item.get('snippet')}"
            )

        return "\n".join(snippets)

    except:
        return ""


def ask_llm(prompt: str) -> str:
    """
    Önce GPT-5 dene, yoksa GPT-4'e düş
    """
    for model in ["gpt-5", "gpt-4o"]:
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return r.choices[0].message.content
        except:
            continue

    return "Şu anda cevap veremiyorum."

# =========================
# MAIN ENDPOINT
# =========================
@app.route("/ask", methods=["POST"])
def ask():
    data = request.json or {}
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"answer": "Bir soru sorabilir misin?"})

    # 1️⃣ Güncel bilgi gerekiyor mu?
    fresh = needs_fresh_info(text)

    # 2️⃣ Gerekirse web'e çık
    web_context = ""
    if fresh:
        web_context = google_search(text)

    # 3️⃣ Final prompt
    if web_context:
        prompt = (
            "Aşağıda web'den alınmış güncel bilgiler var.\n\n"
            f"{web_context}\n\n"
            "Bu bilgilere dayanarak kullanıcıya kısa, net ve doğru bir cevap ver:\n"
            f"Soru: {text}"
        )
    else:
        prompt = text

    answer = ask_llm(prompt)

    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
