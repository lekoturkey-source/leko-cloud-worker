from flask import Flask, request, jsonify
import os
import requests
from openai import OpenAI

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

client = OpenAI(api_key=OPENAI_API_KEY)


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


def google_search(query, num=5):
    """
    Google Custom Search ile güncel veri çeker.
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": num,
        "hl": "tr"
    }

    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        return data.get("items", [])
    except Exception:
        return []


@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json or {}
        user_text = data.get("text", "").strip()

        if not user_text:
            return jsonify({"answer": "Bir soru sorar mısın?"})

        # 1️⃣ Önce internete çık
        search_results = google_search(user_text)

        context_blocks = []
        for item in search_results:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            context_blocks.append(
                f"Başlık: {title}\nÖzet: {snippet}\nKaynak: {link}"
            )

        context_text = "\n\n".join(context_blocks)

        # 2️⃣ Modele verilecek mesaj
        system_prompt = (
            "Sen bir çocuk robotu (Leko) için çalışan yardımcı bir asistansın.\n"
            "GÜNCEL bilgi gerekiyorsa sadece verilen kaynaklara dayan.\n"
            "Emin değilsen bunu açıkça söyle.\n"
            "ASLA tahmin uydurma.\n"
            "Kısa, net ve anlaşılır cevap ver."
        )

        if context_text:
            user_prompt = (
                f"Kullanıcının sorusu:\n{user_text}\n\n"
                f"Aşağıda internetten bulunan GÜNCEL bilgiler var:\n\n"
                f"{context_text}\n\n"
                "Bu bilgilere dayanarak cevap ver."
            )
        else:
            user_prompt = (
                f"Kullanıcının sorusu:\n{user_text}\n\n"
                "İnternetten güvenilir ve güncel bir bilgi bulunamadı.\n"
                "Eğer emin değilsen bunu açıkça belirt."
            )

        # ❗ temperature VERME
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        answer = response.choices[0].message.content.strip()

        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({
            "error": "INTERNAL_ERROR",
            "detail": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
