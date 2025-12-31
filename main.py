# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import os
import re
import requests
from datetime import datetime, timezone

from openai import OpenAI

app = Flask(__name__)

# =========================
# CONFIG (ENV)
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# Google Custom Search (CSE)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GOOGLE_CSE_ID  = os.getenv("GOOGLE_CSE_ID", "").strip()

# Model: gpt-4 / gpt-5 vb. İstersen Cloud Run env'den değiştir.
# Örn: OPENAI_MODEL="gpt-4o-mini" veya "gpt-4.1-mini" gibi.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

# İsteğe bağlı: sonuç sayısı
GOOGLE_NUM_RESULTS = int(os.getenv("GOOGLE_NUM_RESULTS", "5"))

# İsteğe bağlı: kısa cevap hedefi (model yönlendirme)
MAX_SENTENCES = int(os.getenv("LEKO_MAX_SENTENCES", "2"))

# İsteğe bağlı: ağ zaman aşımı
HTTP_TIMEOUT = float(os.getenv("LEKO_HTTP_TIMEOUT", "8"))

# =========================
# HEALTH
# =========================
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# =========================
# HELPERS
# =========================
_MONTHS_TR = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "mayis": 5,
    "haziran": 6, "temmuz": 7, "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
    "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12
}

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _safe_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s[:600]

def google_search(query: str) -> dict:
    """
    Google Custom Search API çağrısı.
    Bu fonksiyon "web'e çıkma" işidir. Her soruda çağrılacak.
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        # Konfig yoksa bile "bulamadım" demek yasak;
        # bu durumda da OpenAI ile genel cevap üretmeye devam edeceğiz.
        return {"items": []}

    # Query paramında Türkçe karakterler için requests params güvenli
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": max(1, min(GOOGLE_NUM_RESULTS, 10)),
        # "hl": "tr",
        # "gl": "tr",
    }
    try:
        r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"items": []}

def extract_date_from_text(text: str):
    """
    Arama sonucu snippet/title içinde tarih yakalamaya çalışır.
    Yakalanırsa timezone-aware datetime döner (UTC varsayıyoruz).
    """
    if not text:
        return None
    t = text.lower()

    # 1) ISO / numerik: 2025-12-31, 31.12.2025, 31/12/2025
    m = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", t)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(y, mo, d, tzinfo=timezone.utc)
    m = re.search(r"(\d{1,2})[-./](\d{1,2})[-./](\d{4})", t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(y, mo, d, tzinfo=timezone.utc)

    # 2) Türkçe yazıyla: 31 Aralık 2025 / 1 Ocak 2026
    m = re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)\s+(\d{4})", t)
    if m:
        d = int(m.group(1))
        mon_name = m.group(2)
        y = int(m.group(3))
        mo = _MONTHS_TR.get(mon_name)
        if mo:
            return datetime(y, mo, d, tzinfo=timezone.utc)

    return None

def pick_best_item(items: list) -> dict:
    """
    Tarihi bulunanlar arasından EN YENİ olanı seç.
    Tarih bulunamazsa ilk item.
    """
    if not items:
        return {}

    scored = []
    for it in items:
        title = it.get("title", "") or ""
        snippet = it.get("snippet", "") or ""
        text = f"{title} {snippet}"
        dt = extract_date_from_text(text)

        # Bazı siteler "Dec 31, 2025" gibi İngilizce yazabilir; basit yakalama:
        if dt is None:
            m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2}),\s*(\d{4})", text.lower())
            if m:
                mm = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
                mo = mm.get(m.group(1))
                d = int(m.group(2))
                y = int(m.group(3))
                dt = datetime(y, mo, d, tzinfo=timezone.utc)

        # Tarih yoksa çok eski gibi davranmasın diye None'u en alta iteriz
        score_dt = dt if dt is not None else datetime(1970, 1, 1, tzinfo=timezone.utc)

        scored.append((score_dt, it))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else items[0]

def build_context_from_items(items: list) -> str:
    """
    Model için web özet bağlamı. Kullanıcıya kaynak göstermiyoruz,
    ama model daha doğru cevap versin diye metinleri bağlama koyuyoruz.
    """
    if not items:
        return ""

    chunks = []
    for it in items[:5]:
        title = _safe_text(it.get("title", ""))
        snippet = _safe_text(it.get("snippet", ""))
        link = _safe_text(it.get("link", ""))
        # link'i kullanıcıya göstermeyeceğiz; model bağlamında tutabiliriz.
        chunks.append(f"- TITLE: {title}\n  SNIPPET: {snippet}\n  LINK: {link}")
    return "\n".join(chunks)

def looks_like_time_sensitive(user_text: str) -> bool:
    """
    Spesifik kelime listesine bağlı kalmadan,
    'güncel' olma ihtimali yüksek soruları sezmek için kaba bir sınıflandırma.
    Not: Biz zaten HER SORUDA web'e çıkıyoruz; bu sadece model yönlendirmesi için.
    """
    t = (user_text or "").lower()
    # para, hava, deprem, maç, seçim, sonuç, bugün/yarın/dün, kimdir (bakan vb. değişebilir), son/sonuç
    patterns = [
        r"\bbugün\b", r"\byarın\b", r"\bdün\b", r"\bşu an\b", r"\bson\b", r"\bgüncel\b",
        r"\bkaç\b", r"\bkuru\b", r"\bdolar\b", r"\beuro\b", r"\baltın\b",
        r"\bhava\b", r"\bdeprem\b", r"\bmaç\b", r"\bsonuç\b", r"\bseçim\b",
        r"\bbakan\b", r"\bkimdir\b"
    ]
    return any(re.search(p, t) for p in patterns)

def openai_answer(user_text: str, web_context: str) -> str:
    """
    Cevap üretimi: kısa, çocuk dostu, kaynak belirtmeden.
    """
    if not OPENAI_API_KEY:
        # Key yoksa bile 'bulamadım' demiyoruz; kısa genel cevap döndür.
        return "Bunu şimdi birlikte araştıralım. Bana biraz daha açık söyler misin?"

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Sistem yönergesi: çocuk dostu, kısa, kesinlik iddiası abartma, kaynak gösterme
    sys = (
        "Sen Leko adında 7 yaşındaki bir çocuğa konuşan yardımcı robotsun.\n"
        "Cevapların kısa olsun (en fazla "
        f"{MAX_SENTENCES} cümle).\n"
        "Kaynak, link, site adı, 'internetten baktım' gibi ifadeler ASLA kullanma.\n"
        "‘Bilmiyorum’, ‘bulamadım’, ‘emin değilim’, ‘internet yok’ gibi cümleler KULLANMA.\n"
        "Web bağlamı varsa onu kullanarak net ve basit bir cevap ver.\n"
        "Eğer soru belirsizse (hangi maç gibi), en olası yorumu seç ve yine kısa cevap ver.\n"
    )

    # Web bağlamı: modele ver, kullanıcıya değil
    ctx = ""
    if web_context:
        ctx = (
            "Aşağıda web aramasından gelen kısa özetler var. "
            "Bunları sadece doğru cevap üretmek için kullan:\n"
            f"{web_context}\n"
        )

    # Parametre uyumluluğu: temperature bazen desteklenmeyebiliyor (gpt-5 bazı modlarda).
    # Bu yüzden temperature vb. göndermiyoruz.
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": f"{ctx}\nSORU: {user_text}".strip()}
        ],
    )

    ans = resp.choices[0].message.content or ""
    ans = _safe_text(ans)

    # Son güvenlik filtresi: kaynak/link sızıntısı olmasın
    ans = re.sub(r"https?://\S+", "", ans).strip()
    ans = re.sub(r"\b(www\.)\S+", "", ans).strip()
    ans = re.sub(r"\s+", " ", ans).strip()

    # Eğer model yine de çok kısa/boş döndüyse fallback (yine yasak cümle yok)
    if len(ans) < 2:
        return "Bunu hemen anlatayım: Biraz daha detay söyler misin?"
    return ans


# =========================
# MAIN ENDPOINT
# =========================
@app.route("/ask", methods=["POST"])
def ask():
    data = request.json or {}
    user_text = _safe_text(data.get("text", ""))

    # Her soruda web'e çık: Google CSE (zorunlu)
    search_q = user_text

    # Eğer “en son / son durum” gibi ise aramayı güçlendirmek için küçük ek:
    # (spesifik maç promptu değil; genel)
    if looks_like_time_sensitive(user_text):
        # tazelik sinyali
        search_q = f"{user_text} son durum"

    g = google_search(search_q)
    items = g.get("items", []) or []

    # En iyi item’ı seç (en yeni tarih / yoksa ilk)
    best = pick_best_item(items)

    # Model için bağlam: best + ilk birkaç sonuç
    # best'i öne al
    ordered = []
    if best:
        ordered.append(best)
        for it in items:
            if it is best:
                continue
            ordered.append(it)
    else:
        ordered = items

    web_context = build_context_from_items(ordered)

    # Cevabı üret
    answer = openai_answer(user_text, web_context)

    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
