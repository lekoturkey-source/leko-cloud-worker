from flask import Flask, request, jsonify
import os
import time
import requests
from openai import OpenAI

app = Flask(__name__)

# -------------------------
# ENV / CLIENTS
# -------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID  = os.getenv("GOOGLE_CSE_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------------
# HEALTH
# -------------------------
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# -------------------------
# WEB SEARCH (Google CSE)
# -------------------------
def google_cse_search(query: str, num: int = 5) -> list[dict]:
    """
    Returns a list of {title, link, snippet}.
    If keys missing or request fails -> empty list.
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": max(1, min(num, 10)),
        "hl": "tr",
        "gl": "tr",
        "safe": "active",
    }

    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        items = data.get("items", []) or []
        out = []
        for it in items:
            out.append({
                "title": it.get("title", ""),
                "link": it.get("link", ""),
                "snippet": it.get("snippet", ""),
            })
        return out
    except Exception:
        return []

# -------------------------
# MODEL SELECTION (fallback)
# -------------------------
def chat_with_fallback(messages, max_tokens=400, temperature=0.2) -> str:
    """
    Try GPT-5 first; if unavailable/error, fallback to GPT-4o.
    """
    for model in ("gpt-5", "gpt-4o"):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return resp.choices[0].message.content or ""
        except Exception:
            continue
    return ""

# -------------------------
# DECIDE IF WEB NEEDED
# -------------------------
def decide_need_web(user_text: str) -> bool:
    """
    Let a small/cheap model decide if fresh/live info is needed.
    Returns True/False; safe default False.
    """
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Görevin: Kullanıcı sorusunun güncel/canlı bilgi gerektirip gerektirmediğine karar vermek.\n"
                        "Güncel/canlı bilgi örnekleri: maç sonucu, son dakika haber, döviz/altın fiyatı, deprem, seçim, "
                        "bugünkü hava, son durum, bugün/şu an değişen bilgiler.\n"
                        "Eğer web araması yapılması gerekiyorsa SADECE 'EVET' yaz.\n"
                        "Gerekli değilse SADECE 'HAYIR' yaz.\n"
                        "Başka hiçbir şey yazma."
                    )
                },
                {"role": "user", "content": user_text}
            ],
            max_tokens=3,
            temperature=0.0,
        )
        ans = (resp.choices[0].message.content or "").strip().lower()
        return ans.startswith("e")
    except Exception:
        return False

# -------------------------
# SUMMARIZE WEB RESULTS
# -------------------------
def build_web_context(results: list[dict]) -> str:
    """
    Compact context string for the model.
    """
    lines = []
    for i, it in enumerate(results[:5], start=1):
        title = (it.get("title") or "").strip()
        link = (it.get("link") or "").strip()
        snip = (it.get("snippet") or "").strip()
        if not (title or snip or link):
            continue
        # Keep it short; model gets enough to answer.
        lines.append(f"[{i}] {title}\n{snip}\nKaynak: {link}".strip())
    return "\n\n".join(lines).strip()

# -------------------------
# /ask
# -------------------------
@app.route("/ask", methods=["POST"])
def ask():
    t0 = time.time()
    try:
        data = request.json or {}
        user_text = (data.get("text") or "").strip()
        if not user_text:
            return jsonify({"answer": "Bir soru sorabilir misin?"})

        # 1) Decide if we need web
        need_web = decide_need_web(user_text)

        web_results = []
        web_context = ""
        if need_web:
            web_results = google_cse_search(user_text, num=5)
            web_context = build_web_context(web_results)

        # 2) Prepare final answer prompt
        if need_web and not web_context:
            # Web was needed but we couldn't fetch results
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Sen çocuklara da konuşabilen yardımsever bir asistansın. "
                        "Kısa, net ve uydurmadan cevap ver. "
                        "Güncel veri gerektiren sorularda web sonucu yoksa bunu açıkça söyle ve "
                        "kullanıcıdan netleştirici bilgi (tarih/rakip/şehir vb.) iste."
                    )
                },
                {"role": "user", "content": user_text}
            ]
            answer = chat_with_fallback(messages, max_tokens=220, temperature=0.2)
            if not answer:
                answer = "Şu an web araması yapamadım. Soru için biraz daha detay verir misin?"
            return jsonify({"answer": answer})

        if web_context:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Aşağıdaki web arama özetlerini KAYNAK olarak kullanarak yanıt ver. "
                        "Kesin emin olmadığın şeyi uydurma. "
                        "Yanıt kısa ve net olsun. Gerekiyorsa 1 cümleyle kaynaklara atıf yap."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Kullanıcı sorusu: {user_text}\n\n"
                        f"Web arama sonuçları:\n{web_context}\n\n"
                        "Yanıt:"
                    )
                }
            ]
        else:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Kısa, net ve doğru cevap ver. Uydurma bilgi verme."
                    )
                },
                {"role": "user", "content": user_text}
            ]

        answer = chat_with_fallback(messages, max_tokens=260, temperature=0.2)
        if not answer:
            answer = "Şu anda cevap veremiyorum, biraz sonra tekrar dener misin?"

        # Optional: small debug timing (not required by client)
        _elapsed = time.time() - t0
        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({"error": "INTERNAL_ERROR", "detail": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
