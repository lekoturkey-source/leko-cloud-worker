
from flask import Flask, request, jsonify
import os
from openai import OpenAI

app = Flask(__name__)

# -------------------------------------------------
# GÜNCEL BİLGİ GEREKİYOR MU?
# (MODEL KENDİ KARAR VERİR)
# -------------------------------------------------
def model_needs_web(client: OpenAI, text: str) -> bool:
    """
    Bu fonksiyon kelime listesi kullanmaz.
    Modelden sadece EVET / HAYIR cevabı alır.
    """
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Aşağıdaki soruya SADECE 'EVET' veya 'HAYIR' diye cevap ver. "
                        "Bu soru zaman-duyarlı veya güncel bilgi gerektiriyor mu?"
                    )
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            max_tokens=3,
        )

        answer = resp.choices[0].message.content.strip().upper()
        return answer.startswith("E")

    except Exception:
        # Karar alınamazsa güvenli tarafta kal
        return False


# -------------------------------------------------
# SAĞLIK KONTROLÜ
# -------------------------------------------------
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# -------------------------------------------------
# ANA API
# -------------------------------------------------
@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json or {}
        text = (data.get("text") or "").strip()

        if not text:
            return jsonify({"answer": "Bir soru sorabilir misin?"})

        # API KEY
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"error": "OPENAI_API_KEY_NOT_FOUND"}), 500

        client = OpenAI(api_key=api_key)

        # -------------------------------------------------
        # MODEL KARARI: GÜNCEL Mİ?
        # -------------------------------------------------
        needs_web = model_needs_web(client, text)

        # -------------------------------------------------
        # SİSTEM PROMPT
        # -------------------------------------------------
        system_prompt = (
            "Sen çocuklara konuşan güvenli bir asistansın. "
            "Cevapların kısa, sade ve anlaşılır olsun. "
        )

        if needs_web:
            system_prompt += (
                "Bu soru GÜNCEL bilgi gerektiriyor. "
                "Emin olmadığın yerde tahmin yapma. "
                "Kesin bilgi yoksa bunu açıkça söyle. "
                "Yanlış veya uydurma bilgi verme."
            )
        else:
            system_prompt += (
                "Bu soru genel bilgidir. "
                "Net ve doğru cevap ver."
            )

        # -------------------------------------------------
        # MODEL SEÇİMİ (GERİYE DÖNÜŞ GÜVENLİ)
        # -------------------------------------------------
        model_name = os.getenv("OPENAI_MODEL", "gpt-5")

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
            )
        except Exception:
            # GPT-5 erişilemezse otomatik düş
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
            )

        return jsonify({
            "answer": response.choices[0].message.content
        })

    except Exception as e:
        return jsonify({
            "error": "INTERNAL_ERROR",
            "detail": str(e)
        }), 500


# -------------------------------------------------
# LOCAL ÇALIŞMA
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
