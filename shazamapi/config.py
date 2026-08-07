import os

PORT = int(os.environ.get("PORT", "10000"))

# Durée de l'extrait analysé (secondes)
SAMPLE_SECONDS = int(os.environ.get("SAMPLE_SECONDS", "12"))

# Timeout de la reconnaissance (secondes)
RECOGNIZE_TIMEOUT = int(os.environ.get("RECOGNIZE_TIMEOUT", "60"))

# Taille max d'un upload (Mo)
MAX_CONTENT_MB = int(os.environ.get("MAX_CONTENT_MB", "50"))

# Moteur de secours optionnel (https://audd.io)
AUDD_API_TOKEN = os.environ.get("AUDD_API_TOKEN", "").strip()
