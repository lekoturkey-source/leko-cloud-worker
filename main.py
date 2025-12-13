import os
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def root():
    return "LEKO OK - ROOT", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "leko-cloud-worker",
        "version": "0.1"
    }), 200

@app.route("/vision", methods=["POST"])
def vision():
    """
    JPEG dosyası bekler:
    - form-data field: image  (dosya)
    - optional: robot_id (text)
    - optional: question (text)
    """
    if "image" not in request.files:
        return jsonify({"ok": False, "error": "Missing file field 'image'"}), 400

    f = request.files["image"]
    robot_id = request.form.get("robot_id", "")
    question = request.form.get("question", "")

    # dosyayı belleğe al (şimdilik sadece test)
    data = f.read()
    size_bytes = len(data)

    return jsonify({
        "ok": True,
        "robot_id": robot_id,
        "question": question,
        "filename": f.filename,
        "content_type": f.content_type,
        "size_bytes": size_bytes,
        "note": "Vision test OK (OpenAI yok, sadece dosyayı aldım)."
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
