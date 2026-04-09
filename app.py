"""
3D Model Generator — Flask backend

Accepts an uploaded image, submits it to the Meshy.ai image-to-3D API,
polls for completion, and serves the resulting GLB file for download.
"""

import os
import re
import uuid
import logging
import requests

from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB

# Regex for safe Meshy task IDs (alphanumeric + hyphens only)
_TASK_ID_RE = re.compile(r"^[a-zA-Z0-9\-]{1,128}$")

UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "outputs")
MESHY_API_KEY = os.getenv("MESHY_API_KEY", "")
MESHY_BASE_URL = "https://api.meshy.ai/openapi/v1"

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "change-me-in-production")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def meshy_headers() -> dict:
    return {"Authorization": f"Bearer {MESHY_API_KEY}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    """
    Accepts a multipart/form-data POST with an image file and optional
    art_style / negative_prompt fields.  Returns JSON with a task_id that
    the client can poll via /status/<task_id>.
    """
    if not MESHY_API_KEY:
        return jsonify({"error": "MESHY_API_KEY is not configured on the server."}), 500

    if "image" not in request.files:
        return jsonify({"error": "No image file provided."}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    # Save the upload locally so we can pass a URL or base64 to Meshy
    filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
    local_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(local_path)

    # Read image as base64 data-URL (Meshy supports image_url as a data-URL)
    import base64
    with open(local_path, "rb") as f:
        raw = f.read()
    ext = local_path.lower().rsplit(".", 1)[-1]
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    mime = mime_map.get(ext, "image/png")
    image_data_url = f"data:{mime};base64,{base64.b64encode(raw).decode()}"

    art_style = request.form.get("art_style", "realistic")
    negative_prompt = request.form.get("negative_prompt", "low quality, low resolution, low poly, ugly")

    payload = {
        "image_url": image_data_url,
        "enable_pbr": True,
        "ai_model": "meshy-4",
        "art_style": art_style,
        "negative_prompt": negative_prompt,
    }

    try:
        resp = requests.post(
            f"{MESHY_BASE_URL}/image-to-3d",
            json=payload,
            headers=meshy_headers(),
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Meshy API error: %s", exc)
        return jsonify({"error": "Failed to submit task to Meshy API. Check server logs."}), 502

    task_id = resp.json().get("result")
    if not task_id:
        return jsonify({"error": "Unexpected response from Meshy API.", "detail": resp.json()}), 502

    logger.info("Meshy task created: %s", task_id)
    return jsonify({"task_id": task_id})


@app.route("/status/<task_id>")
def status(task_id: str):
    """
    Proxy the Meshy task status so the frontend doesn't need the API key.
    Returns a subset of the Meshy response suitable for the UI.
    """
    if not MESHY_API_KEY:
        return jsonify({"error": "MESHY_API_KEY is not configured on the server."}), 500

    if not _TASK_ID_RE.match(task_id):
        return jsonify({"error": "Invalid task ID."}), 400

    try:
        resp = requests.get(
            f"{MESHY_BASE_URL}/image-to-3d/{task_id}",
            headers=meshy_headers(),
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Meshy status error: %s", exc)
        return jsonify({"error": "Failed to retrieve task status. Check server logs."}), 502

    data = resp.json()
    result = {
        "status": data.get("status"),
        "progress": data.get("progress", 0),
        "glb_url": None,
    }

    model_urls = data.get("model_urls", {})
    if model_urls.get("glb"):
        result["glb_url"] = f"/download/{task_id}"

    return jsonify(result)


@app.route("/download/<task_id>")
def download(task_id: str):
    """
    Stream the GLB file from Meshy and serve it to the browser as a download.
    Caches the file locally so repeated downloads don't re-fetch from Meshy.
    """
    if not MESHY_API_KEY:
        return jsonify({"error": "MESHY_API_KEY is not configured on the server."}), 500

    if not _TASK_ID_RE.match(task_id):
        return jsonify({"error": "Invalid task ID."}), 400

    cached = os.path.join(OUTPUT_FOLDER, f"{task_id}.glb")
    if not os.path.exists(cached):
        # Fetch task details to get the GLB URL
        try:
            resp = requests.get(
                f"{MESHY_BASE_URL}/image-to-3d/{task_id}",
                headers=meshy_headers(),
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Meshy download metadata error: %s", exc)
            return jsonify({"error": "Failed to retrieve model metadata. Check server logs."}), 502

        glb_url = resp.json().get("model_urls", {}).get("glb")
        if not glb_url:
            return jsonify({"error": "GLB file is not yet available for this task."}), 404

        # Download and cache
        try:
            glb_resp = requests.get(glb_url, timeout=120, stream=True)
            glb_resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("GLB fetch error: %s", exc)
            return jsonify({"error": "Failed to fetch GLB file. Check server logs."}), 502

        with open(cached, "wb") as f:
            for chunk in glb_resp.iter_content(chunk_size=8192):
                f.write(chunk)

    return send_file(
        cached,
        mimetype="model/gltf-binary",
        as_attachment=True,
        download_name="model.glb",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, port=5000)
