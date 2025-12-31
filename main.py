from flask import Flask, request, jsonify
import os
import requests
from openai import OpenAI

app = Flask(__name__)

# -------------------------------------------------
# HEALTH
# -------------------------------------------------
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# -------------------------------------------------
# GOOGLE WEB SEARCH
# -------------------------------------------------
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
                "num": 5,
            },
            timeout=8
        )
        r.raise_for_status()
        data = r.json()

        results = []
        for item in data.get("items", []):
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            results.append(f"{title} – {snippet}")

        return "\n".join(results)

    except Exception:
        return ""


# -------------------------------------------------
# WEB GEREKİR Mİ?
# -------------------------------------------------
def needs_web(text: str) -> bool:
    # Hızlı heuristik (ilk filtre)
    keywords = [
        "bugün", "şu an", "şimdi", "en son", "son",
        "sonuç", "maç", "ne oldu", "kaç oldu",
        "güncel", "haber", "dolar", "euro", "altın",
        "deprem", "seçim"
    ]

    lower = text.lower()
    if any(k in lower for k in keywords):
        return True

    # İkinci aşama: modele sor (güvenli)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False

    client = OpenAI(api_key=api_key)

    judge_prompt = f"""
Soru:
{text}

Bu soru cevaplanırken GÜNCEL internet bilgisi gerekir mi?
SADECE EVET veya HAYIR yaz.
"""

    try:
        r = client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": judge_prompt}],
            max_completion_tokens=5
        )
        return "EVET" in r.choices[0].message.content.upper()
    except Exception:
        return False


# -------------------------------------------------
# ASK ENDPOINT
# -------------------------------------------------
@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"answer": "Bir soru sorar mısın?"})

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"answer": "AI servisi şu anda hazır değil."})

        client = OpenAI(api_key=api_key)

        use_web = needs_web(text)
        web_context = web_search(text) if use_web else ""

        # 🔥 KRİTİK PROMPT (WEB OTORİTE)
        final_prompt = f"""
Aşağıdaki kurallara UYMAK ZORUNDASIN:

- Eğer "Güncel Web Bilgileri" varsa:
  → Cevabını SADECE bu bilgilere dayanarak ver
  → "erişemiyorum", "bilemiyorum" DEME
  → Web bilgisini özetle

- Eğer web bilgisi yoksa:
  → Normal genel bilginle cevapla

- Tahmin yapma
- Kısa, net ve anlaşılır yaz

Soru:
{text}

{"GÜNCEL WEB BİLGİLERİ:" if web_context else ""}
{web_context}
"""

        response = client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": final_prompt}],
            max_completion_tokens=300
        )

        return jsonify({
            "answer": response.choices[0].message.content.strip(),
            "used_web": use_web
        })

    except Exception as e:
        return jsonify({
            "error": "INTERNAL_ERROR",
            "detail": str(e)
        }), 500


# -------------------------------------------------
# LOCAL RUN
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
