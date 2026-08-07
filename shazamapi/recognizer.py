"""Extraction audio (ffmpeg) + reconnaissance musicale.

Moteur principal : Shazam (shazamio) — gratuit, aucune clé API.
Moteur de secours : AudD, utilisé uniquement si AUDD_API_TOKEN est défini.
"""

import asyncio
import base64
import logging
import os
import tempfile

import httpx

from . import config

logger = logging.getLogger(__name__)

AUDD_URL = "https://api.audd.io/"


class RecognizeError(Exception):
    pass


def _tmp(suffix: str) -> str:
    return os.path.join(
        tempfile.gettempdir(), f"shz_{os.getpid()}_{os.urandom(5).hex()}{suffix}"
    )


async def download_media(url: str) -> str:
    """Télécharge un média distant dans un fichier temporaire."""
    max_bytes = config.MAX_CONTENT_MB * 1024 * 1024
    path = _tmp(".media")
    try:
        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise RecognizeError(f"Téléchargement impossible (HTTP {response.status_code})")
                size = 0
                with open(path, "wb") as fh:
                    async for chunk in response.aiter_bytes(64 * 1024):
                        size += len(chunk)
                        if size > max_bytes:
                            raise RecognizeError(
                                f"Fichier trop volumineux (> {config.MAX_CONTENT_MB} Mo)"
                            )
                        fh.write(chunk)
    except httpx.HTTPError as exc:
        raise RecognizeError(f"Téléchargement échoué: {exc}")
    if not os.path.getsize(path):
        raise RecognizeError("Le média téléchargé est vide")
    return path


def save_base64(data: str) -> str:
    """Écrit un média base64 (avec ou sans préfixe data:) dans un fichier."""
    if "," in data and data.strip().startswith("data:"):
        data = data.split(",", 1)[1]
    try:
        raw = base64.b64decode(data, validate=False)
    except Exception:
        raise RecognizeError("Base64 invalide")
    if not raw:
        raise RecognizeError("Média vide")
    if len(raw) > config.MAX_CONTENT_MB * 1024 * 1024:
        raise RecognizeError(f"Fichier trop volumineux (> {config.MAX_CONTENT_MB} Mo)")
    path = _tmp(".media")
    with open(path, "wb") as fh:
        fh.write(raw)
    return path


async def extract_audio(source_path: str) -> str:
    """Extrait un extrait mp3 mono 44.1kHz depuis n'importe quel média (audio ou vidéo)."""
    out_path = _tmp(".mp3")
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", source_path,
        "-vn",
        "-t", str(config.SAMPLE_SECONDS),
        "-ac", "1",
        "-ar", "44100",
        "-b:a", "128k",
        out_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0 or not os.path.exists(out_path) or not os.path.getsize(out_path):
        raise RecognizeError(f'ffmpeg: {stderr.decode("utf-8", "ignore")[:300]}')
    return out_path


def _first(*values):
    for value in values:
        if value:
            return value
    return None


# ---------------------------------------------------------------- Shazam ----

def _shazam_meta(track: dict) -> dict:
    meta = {}
    for section in track.get("sections") or []:
        for item in section.get("metadata") or []:
            key = (item.get("title") or "").strip().lower()
            if key and item.get("text"):
                meta[key] = item["text"]
    return meta


def _parse_shazam(track: dict) -> dict:
    meta = _shazam_meta(track)
    images = track.get("images") or {}
    share = track.get("share") or {}
    hub = track.get("hub") or {}

    links = {}
    for provider in hub.get("providers") or []:
        name = (provider.get("type") or "").title()
        uri = None
        for action in provider.get("actions") or []:
            if (action.get("uri") or "").startswith("http"):
                uri = action["uri"]
                break
        if name and uri:
            links[name.lower()] = uri

    for option in hub.get("options") or []:
        for action in option.get("actions") or []:
            uri = action.get("uri") or ""
            if "music.apple.com" in uri:
                links.setdefault("apple_music", uri)

    shazam_url = _first(track.get("url"), share.get("href"))
    if shazam_url:
        links["shazam"] = shazam_url

    preview = None
    for action in hub.get("actions") or []:
        if action.get("type") == "uri" and (action.get("uri") or "").startswith("http"):
            preview = action["uri"]
            break

    genre = (track.get("genres") or {}).get("primary")

    return {
        "title": track.get("title") or None,
        "artist": track.get("subtitle") or None,
        "album": meta.get("album"),
        "release": meta.get("released"),
        "label": meta.get("label"),
        "genre": genre,
        "cover": _first(images.get("coverarthq"), images.get("coverart"), share.get("image")),
        "preview": preview,
        "links": links,
        "engine": "shazam",
    }


async def _recognize_shazam(sample_path: str) -> dict | None:
    try:
        from shazamio import Shazam
    except ImportError as exc:  # pragma: no cover
        raise RecognizeError(f"shazamio indisponible: {exc}")

    try:
        payload = await asyncio.wait_for(
            Shazam().recognize(sample_path), timeout=config.RECOGNIZE_TIMEOUT
        )
    except asyncio.TimeoutError:
        raise RecognizeError("Shazam: délai dépassé")
    except Exception as exc:
        raise RecognizeError(f"Shazam: {exc}")

    track = (payload or {}).get("track")
    if not track:
        return None
    return _parse_shazam(track)


# ------------------------------------------------------------------ AudD ----

def _parse_audd(result: dict) -> dict:
    spotify = result.get("spotify") or {}
    deezer = result.get("deezer") or {}
    apple = result.get("apple_music") or {}
    album = spotify.get("album") or {}
    images = album.get("images") or []
    artwork = (apple.get("artwork") or {}).get("url", "")

    return {
        "title": _first(result.get("title"), apple.get("name"), deezer.get("title")),
        "artist": _first(result.get("artist"), apple.get("artistName")),
        "album": _first(result.get("album"), album.get("name"), (deezer.get("album") or {}).get("title")),
        "release": _first(result.get("release_date"), album.get("release_date")),
        "label": _first(result.get("label"), apple.get("recordLabel")),
        "genre": (apple.get("genreNames") or [None])[0],
        "cover": _first(
            images[0].get("url") if images else None,
            (deezer.get("album") or {}).get("cover_big"),
            artwork.replace("{w}", "600").replace("{h}", "600") or None,
        ),
        "preview": _first(deezer.get("preview"), spotify.get("preview_url")),
        "links": {
            key: value
            for key, value in {
                "spotify": (spotify.get("external_urls") or {}).get("spotify"),
                "apple_music": apple.get("url"),
                "deezer": deezer.get("link"),
            }.items()
            if value
        },
        "engine": "audd",
    }


async def _recognize_audd(sample_path: str) -> dict | None:
    with open(sample_path, "rb") as fh:
        files = {"file": ("sample.mp3", fh, "audio/mpeg")}
        data = {
            "api_token": config.AUDD_API_TOKEN,
            "return": "apple_music,spotify,deezer",
        }
        async with httpx.AsyncClient(timeout=config.RECOGNIZE_TIMEOUT) as client:
            response = await client.post(AUDD_URL, data=data, files=files)

    if response.status_code != 200:
        raise RecognizeError(f"AudD HTTP {response.status_code}")

    payload = response.json()
    if payload.get("status") != "success":
        error = (payload.get("error") or {}).get("error_message", "erreur inconnue")
        raise RecognizeError(f"AudD: {error}")

    result = payload.get("result")
    if not result:
        return None
    return _parse_audd(result)


# ----------------------------------------------------------------- public ---

async def recognize_file(media_path: str) -> dict | None:
    """Renvoie les infos du son, ou None si rien n'est reconnu."""
    sample_path = await extract_audio(media_path)
    try:
        try:
            info = await _recognize_shazam(sample_path)
        except RecognizeError as exc:
            logger.warning("Shazam indisponible (%s)", exc)
            info = None
            if not config.AUDD_API_TOKEN:
                raise

        if info:
            return info
        if config.AUDD_API_TOKEN:
            return await _recognize_audd(sample_path)
        return None
    finally:
        for path in (sample_path,):
            try:
                os.remove(path)
            except OSError:
                pass


def recognize_sync(media_path: str, cleanup: bool = True) -> dict | None:
    """Wrapper synchrone pour Flask."""
    try:
        return asyncio.run(recognize_file(media_path))
    finally:
        if cleanup:
            try:
                os.remove(media_path)
            except OSError:
                pass


def prepare_sync(url: str) -> str:
    return asyncio.run(download_media(url))
