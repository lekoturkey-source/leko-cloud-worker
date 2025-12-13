from flask import Flask, request, jsonify
import os
import time

app = Flask(__name__)

# ======================================================
# Basit bellek içi komut kuyruğu (Firestore ÖNCESİ TEST)
# ======================================================
COMMANDS = []

# ======================================================
# HEALTH CHECK
# ======================================================
@app.get("/health")
def health():
    return jsonify(
        service="leko-cloud-worker",
        status="ok",
        version=os.getenv("VERSION", "0.1")
    )

# ======================================================
# BASİT HEADER TABANLI GÜVENLİK
# ======================================================
def require_secret():
    expected = os.getenv("LEKO_SHARED_SECRET", "")
    received = request.headers.get("X-LEKO-SECRET", "")
    return expected != "" and received == expected

# ======================================================
# KOMUT EKLE (ROBOT -> CLOUD)
# ======================================================
@app.post("/command")
def add_command():
    if not require_secret():
        return jsonify(error="unauthorized"), 401

    data = request.get_json(silent=True) or {}

    # Zorunlu alanlar (kontrollü)
    command = {
        "robot_id": data.get("robot_id", "UNKNOWN"),
        "type": data.get("type", "say"),
        "text": data.get("text", ""),
        "ts": int(time.time())
    }

    COMMANDS.append(command)

    return jsonify(
        ok=True,
        queued=len(COMMANDS),
        last_command=command
    )

# ======================================================
# SIRADAKİ KOMUTU AL (ROBOT <- CLOUD)
# ======================================================
@app.get("/command/next")
def get_next_command():
    if not require_secret():
        return jsonify(error="unauthorized"), 401

    if not COMMANDS:
        return jsonify(ok=True, command=None)

    return jsonify(ok=True, command=COMMANDS.pop(0))

# ======================================================
# ROOT (DEBUG AMAÇLI)
# ======================================================
@app.get("/")
def root():
    return "leko ok root"

# ======================================================
# APP START (Cloud Run uyumlu)
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
