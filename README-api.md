# Shazam API

API de reconnaissance musicale : envoie un **audio** ou une **vidéo**, elle renvoie le
titre, l'artiste, l'album, la pochette et les liens d'écoute.
Moteur principal : Shazam (`shazamio`, gratuit, sans clé). Secours optionnel : AudD.

## Structure

```
Dockerfile          <- à la racine (pas dans un sous-dossier)
render.yaml
requirements.txt
gunicorn.conf.py
app.py              <- serveur Flask (endpoints)
shazamapi/
  config.py         <- variables d'environnement
  recognizer.py     <- ffmpeg + Shazam + AudD
cmds/shazam.js      <- commande bot (style gem.js)
src/                <- site de documentation / testeur
```

## Endpoints

| Méthode | Route | Description |
| --- | --- | --- |
| GET | `/` | Health check + liste des endpoints |
| GET | `/health` | `{"status":"ok"}` |
| POST | `/recognize` | Reconnaissance (multipart `file`, JSON `url` ou `audio` base64) |
| GET | `/recognize?url=…` | Reconnaissance via query string |
| POST | `/shazam` | Alias de `/recognize` |

Ajoute `?text=1` pour recevoir en plus un champ `text` déjà formaté pour un chat.

### Exemples

```bash
curl -X POST "$API/recognize" -H "Content-Type: application/json" \
  -d '{"url":"https://exemple.com/clip.mp4"}'

curl -X POST "$API/recognize?text=1" -F "file=@song.mp3"

curl -X POST "$API/recognize" -H "Content-Type: application/json" \
  -d '{"audio":"<base64>"}'
```

### Réponse

```json
{
  "success": true,
  "result": {
    "title": "Blinding Lights",
    "artist": "The Weeknd",
    "album": "After Hours",
    "release": "2020",
    "genre": "Pop",
    "cover": "https://…jpg",
    "preview": "https://…m4a",
    "links": { "spotify": "https://…", "shazam": "https://…" },
    "engine": "shazam"
  }
}
```

Erreurs : `400` (entrée invalide), `404` (aucune correspondance), `413` (fichier trop
gros), `500` (erreur interne) — toujours au format `{"success": false, "error": "…"}`.

## Déploiement Render (Docker)

1. Pousse le dépôt sur GitHub.
2. Render → New → Web Service → Docker (ou "Blueprint" avec `render.yaml`).
3. Health check path : `/`. Le port vient de `PORT` (géré automatiquement).
4. Variables optionnelles : `SAMPLE_SECONDS` (12), `RECOGNIZE_TIMEOUT` (60),
   `MAX_CONTENT_MB` (50), `AUDD_API_TOKEN` (moteur de secours).

Local :

```bash
docker build -t shazam-api . && docker run -p 10000:10000 shazam-api
```

## Commande bot

`cmds/shazam.js` : réponds à un audio/vidéo avec `shazam`. Change `API_URL` par
l'URL de ton service Render.
