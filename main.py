from flask import Flask, request, jsonify
import os
import requests
from openai import OpenAI

# ==============================
# CONFIG
# ==============================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID  = os.getenv("GOOGLE_CSE_ID")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing")

client = OpenAI(api_key=OPENAI_API_KEY)

MODEL_MAIN   = "gpt-5"        # gpt-4 / gpt-4o-mini / gpt-5 → değiştirilebilir
MODEL_DECIDE = "gpt-4o-mini" # hızlı ve ucuz karar modeli

app = Flask(__name__)

# ==============================
# HEALTH
# ==============================

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# ==============================
# LLM: GÜNCEL Mİ?
# ==============================
def llm_needs_live_data(text: str) -> bool:
    r = client.chat.completions.create(
        model=MODEL_DECIDE,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "Bir kullanıcı sorusu alacaksın.\n\n"
                    "Eğer soru:\n"
                    "- zaman bağımlıysa\n"
                    "- 'en son', 'şu an', 'bugün', 'güncel', 'ne oldu', 'son durum'\n"
                    "- sonuç, skor, fiyat, olay, haber gibi DEĞİŞEBİLEN bilgi istiyorsa\n\n"
                    "Bu soruya cevap verebilmek için MUTLAKA internet gerekir.\n\n"
                    "Bu durumda sadece EVET yaz.\n"
                    "Aksi halde sadece HAYIR yaz."
                )
            },
            {"role": "user", "content": text}
        ]
    )

    return "EVET" in r.choices[0].message.content.upper()



# ==============================
# GOOGLE CSE
# ==============================

def web_search(query: str):
    r = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": query,
            "hl": "tr",
            "num": 5
        },
        timeout=10
    )
    r.raise_for_status()
    return r.json().get("items", [])

# ==============================
# WEB SONUÇLARINI ANLAT
# ==============================

def summarize_web(question: str, items: list) -> str:
    sources = "\n\n".join(
        f"Kaynak: {i.get('title','')}\n{i.get('snippet','')}"
        for i in items
    )

    r = client.chat.completions.create(
        model=MODEL_MAIN,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Aşağıda güncel internet kaynaklarından alınmış bilgiler var.\n"
                    "Yanlış veya uydurma bilgi ekleme.\n"
                    "Sadece bu bilgilerden yola çıkarak cevap ver.\n"
                    "Emin değilsen bunu açıkça söyle."
                )
            },
            {
                "role": "user",
                "content": f"Soru: {question}\n\nBilgiler:\n{sources}"
            }
        ]
    )

    return r.choices[0].message.content.strip()

# ==============================
# NORMAL CHAT
# ==============================

def normal_answer(text: str) -> str:
    r = client.chat.completions.create(
        model=MODEL_MAIN,
        temperature=0.4,
        messages=[{"role": "user", "content": text}]
    )
    return r.choices[0].message.content.strip()

# ==============================
# ASK ENDPOINT
# ==============================

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"answer": "Bir soru sorabilir misin?"})

        # 1️⃣ Model karar versin
        needs_live = llm_needs_live_data(text)

        # 2️⃣ GÜNCEL BİLGİ
        if needs_live and GOOGLE_API_KEY and GOOGLE_CSE_ID:
            items = web_search(text)

            if not items:
                return jsonify({
                    "answer": "Bu konuda internette güncel ve güvenilir bir bilgi bulamadım."
                })

            answer = summarize_web(text, items)
            return jsonify({"answer": answer})

        # 3️⃣ STATİK BİLGİ
        answer = normal_answer(text)
        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({
            "error": "INTERNAL_ERROR",
            "detail": str(e)
        }), 500

# ==============================
# MAIN
# ==============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
