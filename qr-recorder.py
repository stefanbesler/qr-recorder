import os
import uuid
import subprocess
from flask import Flask, request, render_template, send_from_directory, url_for, jsonify
from flask_basicauth import BasicAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import qrcode
from datetime import datetime
import math

USERNAME = ''
PASSWORD = ''
PAGE_SIZE = 10

app = Flask(__name__)
app.config['BASIC_AUTH_USERNAME'] = USERNAME
app.config['BASIC_AUTH_PASSWORD'] = PASSWORD

basic_auth = BasicAuth(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    headers_enabled=True
)

UPLOAD_FOLDER = "uploads"
QR_FOLDER = "static/qr"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)

def get_recordings():
    """Return all recordings as list of dicts with uid, datetime, paths"""
    recordings = []
    for f in os.listdir(UPLOAD_FOLDER):
        if f.endswith(".m4a"):  # your ffmpeg output
            uid = f.split(".")[0]
            path = os.path.join(UPLOAD_FOLDER, f)
            date = datetime.fromtimestamp(os.path.getmtime(path))
            qr_path = f"/static/qr/{uid}.png"
            qr_url = url_for("static", filename=f"qr/{uid}.png", _external=True)
            play_url = url_for("audio", uid=uid, _external=True)
            audio_url = url_for("audio", uid=uid, _external=True)
            recordings.append({
                "uid": uid,
                "date": date.strftime("%Y-%m-%d %H:%M:%S"),
                "qr_url": qr_url,
                "play_url": play_url,
                "audio_url": audio_url
            })
    # sort newest first
    recordings.sort(key=lambda x: x["date"], reverse=True)
    return recordings

@app.route("/")
@basic_auth.required
@limiter.limit("10 per minute")
def index():
    return render_template("index.html")

@app.route("/record")
@basic_auth.required
@limiter.limit("10 per minute")
def record():
    return render_template("record.html")
    
@app.route("/recordings")
@basic_auth.required
@limiter.limit("10 per minute")
def recordings_api():
    page = int(request.args.get("page", 1))
    all_rec = get_recordings()
    total = len(all_rec)
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    data = all_rec[start:end]
    return jsonify({
        "recordings": data,
        "page": page,
        "total_pages": math.ceil(total / PAGE_SIZE)
    })

@app.route("/upload", methods=["POST"])
@basic_auth.required
@limiter.limit("10 per minute")
def upload():

    file = request.files["audio"]
    uid = str(uuid.uuid4())

    # original temp file
    tmp_path = os.path.join(UPLOAD_FOLDER, f"{uid}_raw")

    file.save(tmp_path)

    final_filename = f"{uid}.m4a"
    final_path = os.path.join(UPLOAD_FOLDER, final_filename)

    # convert with ffmpeg
    subprocess.run([
        "ffmpeg",
        "-y",
        "-fflags", "+genpts",      # regenerate timestamps (fixes jitter/stutter)
        "-i", tmp_path,
        "-vn",                     # no video
        "-ac", "1",                # mono (speech recordings = safer & smaller)
        "-ar", "22050",            # stable sample rate for mobile playback
        "-af", "aresample=async=1:first_pts=0",
        "-c:a", "aac",
        "-profile:a", "aac_low",   # best compatibility (especially iOS)
        "-b:a", "64k",             # 64k mono speech is more than enough
        "-movflags", "+faststart", # playback starts immediately
        final_path
    ], check=True)

    os.remove(tmp_path)

    play_url = url_for("play", uid=uid, _external=True)

    qr = qrcode.make(play_url)
    qr_path = os.path.join(QR_FOLDER, f"{uid}.png")
    qr.save(qr_path)

    return {
        "play_url": play_url,
        "qr_url": f"/static/qr/{uid}.png"
    }

@app.route("/play/<uid>")
@limiter.limit("60 per minute")
def play(uid):
    return render_template("play.html", uid=uid)

def ip_uid_key():
    uid = request.view_args.get("uid", "")
    return f"{request.remote_addr}:{uid}"

@app.route("/audio/<uid>")
@limiter.limit("120 per minute")
@limiter.limit("20 per minute", key_func=ip_uid_key)
def audio(uid):
    return send_from_directory(
        UPLOAD_FOLDER,
        f"{uid}.m4a",
        mimetype="audio/mp4"
    )

if __name__ == "__main__":
    app.run(debug=True)
