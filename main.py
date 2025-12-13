import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def health():
    return "Leko Cloud Worker is running 🚀"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
