"""Shazam API — Flask app déployable sur Render (Docker).

Endpoints
  GET  /            → health check + liste des endpoints
  GET  /health      → statut simple
  POST /recognize   → JSON {url|audio|video|media} ou multipart file → métadonnées du son
  GET  /recognize   → ?url=... (idem, pratique pour un test navigateur)
  POST /shazam      → alias de /recognize
  POST /lyrics-free → texte formaté prêt à envoyer dans un chat (?text=1 équivalent)
"""

import logging
import os
import traceback

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from shazamapi import config
from shazamapi.recognizer import (
    RecognizeError,
    prepare_sync,
    recognize_sync,
    save_base64,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", level=logging.INFO
)
logger = logging.getLogger("shazam-api")

app = Flask(__name__, static_folder="shazamapi/static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_MB * 1024 * 1024
CORS(app)

MEDIA_FIELDS = ("media", "audio", "video", "file", "data")
URL_FIELDS = ("url", "media_url", "audio_url", "video_url", "attachment")


def _ok(info: dict, as_text: bool):
    if as_text:
        lines = [
            f"🎵 Titre : {info.get('title') or '—'}",
            f"🎤 Artiste : {info.get('artist') or '—'}",
        ]
        if info.get("album"):
            lines.append(f"💿 Album : {info['album']}")
        if info.get("release"):
            lines.append(f"📅 Sortie : {info['release']}")
        if info.get("genre"):
            lines.append(f"🏷️ Genre : {info['genre']}")
        for name, url in (info.get("links") or {}).items():
            lines.append(f"🔗 {name.replace('_', ' ').title()} : {url}")
        return jsonify({"success": True, "text": "\n".join(lines), "result": info})
    return jsonify({"success": True, "result": info})


def _resolve_media() -> str:
    """Renvoie le chemin local du média envoyé (upload, base64 ou URL)."""
    for field in MEDIA_FIELDS:
        uploaded = request.files.get(field)
        if uploaded and uploaded.filename:
            path = os.path.join(
                "/tmp", f"upload_{os.getpid()}_{os.urandom(5).hex()}"
            )
            uploaded.save(path)
            if not os.path.getsize(path):
                raise RecognizeError("Fichier envoyé vide")
            return path

    payload = request.get_json(silent=True) or {}
    form = request.form

    for field in URL_FIELDS:
        url = payload.get(field) or form.get(field) or request.args.get(field)
        if url:
            if not str(url).startswith("http"):
                raise RecognizeError("URL invalide (http/https requis)")
            return prepare_sync(str(url))

    for field in MEDIA_FIELDS:
        b64 = payload.get(field) or form.get(field)
        if b64 and isinstance(b64, str):
            return save_base64(b64)

    raise RecognizeError(
        "Aucun média fourni. Envoie un fichier (multipart 'file'), une URL ('url') ou du base64 ('audio')."
    )


@app.route("/", methods=["GET"])
def index():
    return jsonify(
        {
            "status": "active",
            "service": "Shazam API",
            "message": "Reconnaissance musicale depuis un audio ou une vidéo",
            "engine": "shazam" + (" + audd" if config.AUDD_API_TOKEN else ""),
            "sample_seconds": config.SAMPLE_SECONDS,
            "max_upload_mb": config.MAX_CONTENT_MB,
            "endpoints": {
                "recognize": "/recognize (POST json|multipart, GET ?url=)",
                "shazam": "/shazam (POST, alias)",
                "health": "/health (GET)",
                "docs": "/docs",
            },
            "accepts": {
                "file": "multipart/form-data champ 'file'",
                "url": "JSON {\"url\": \"https://...mp4|mp3\"}",
                "base64": "JSON {\"audio\": \"<base64>\"}",
                "text_output": "?text=1 pour un message déjà formaté",
            },
        }
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/docs", methods=["GET"])
def docs():
    path = os.path.join(app.root_path, "shazamapi", "static", "docs.html")
    if os.path.exists(path):
        return send_from_directory(os.path.dirname(path), "docs.html")
    return index()


@app.route("/recognize", methods=["POST", "GET"])
@app.route("/shazam", methods=["POST", "GET"])
def recognize_route():
    as_text = str(request.args.get("text", "")).lower() in ("1", "true", "yes")
    media_path = None
    try:
        media_path = _resolve_media()
        info = recognize_sync(media_path)
        media_path = None
        if not info:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Aucune correspondance trouvée pour cet extrait",
                    }
                ),
                404,
            )
        return _ok(info, as_text)
    except RecognizeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error("recognize: %s", traceback.format_exc())
        return jsonify({"success": False, "error": f"Erreur interne: {exc}"}), 500
    finally:
        if media_path:
            try:
                os.remove(media_path)
            except OSError:
                pass


@app.errorhandler(413)
def too_large(_e):
    return (
        jsonify(
            {
                "success": False,
                "error": f"Fichier trop volumineux (max {config.MAX_CONTENT_MB} Mo)",
            }
        ),
        413,
    )


@app.errorhandler(404)
def not_found(_e):
    return jsonify({"success": False, "error": "Endpoint inconnu"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT)
