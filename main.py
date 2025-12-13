import os
from flask import Flask

print(">>> LEKO MAIN.PY LOADED <<<")

app = Flask(__name__)

@app.route("/")
def root():
    return "LEKO OK - ROOT"

@app.route("/health")
def health():
    return "LEKO OK - HEALTH"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
