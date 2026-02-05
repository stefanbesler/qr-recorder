import os
import uuid
from flask import Flask, request, render_template, send_from_directory, url_for
from flask_basicauth import BasicAuth
import qrcode

USERNAME = '<your-username>'
PASSWORD = '<your-password>'
DOMAIN = 'record.besler.me'
PORT = '8808'

app = Flask(__name__)
app.config['BASIC_AUTH_USERNAME'] = USERNAME
app.config['BASIC_AUTH_PASSWORD'] = PASSWORD

basic_auth = BasicAuth(app)

UPLOAD_FOLDER = "uploads"
QR_FOLDER = "static/qr"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)

@app.route("/")
@basic_auth.required
def index():
    return render_template("record.html")

@app.route("/upload", methods=["POST"])
@basic_auth.required
def upload():
    file = request.files["audio"]
    uid = str(uuid.uuid4())
    filename = f"{uid}.webm"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    play_url = url_for("play", uid=uid, _external=True)

    qr = qrcode.make(play_url)
    qr_path = os.path.join(QR_FOLDER, f"{uid}.png")
    qr.save(qr_path)

    return {
        "play_url": play_url,
        "qr_url": f"/static/qr/{uid}.png"
    }

@app.route("/play/<uid>")
@basic_auth.required
def play(uid):
    return render_template("play.html", uid=uid)

@app.route("/audio/<uid>")
@basic_auth.required
def audio(uid):
    return send_from_directory(UPLOAD_FOLDER, f"{uid}.webm")

if __name__ == "__main__":
    app.run(debug=True)
