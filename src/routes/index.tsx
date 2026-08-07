import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Shazam API — Identifier un son depuis un audio ou une vidéo" },
      {
        name: "description",
        content:
          "API de reconnaissance musicale : envoie un audio, une vidéo ou une URL et récupère le titre et l'artiste. Déployable sur Render avec Docker.",
      },
      { property: "og:title", content: "Shazam API — reconnaissance musicale" },
      {
        property: "og:description",
        content:
          "Envoie un audio ou une vidéo, l'API renvoie le titre, l'artiste, l'album et les liens d'écoute.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

type TrackResult = {
  title?: string | null;
  artist?: string | null;
  album?: string | null;
  release?: string | null;
  genre?: string | null;
  cover?: string | null;
  preview?: string | null;
  links?: Record<string, string>;
  engine?: string;
};

const DEFAULT_BASE = "https://shazam-api.onrender.com";

const ENDPOINTS = [
  {
    method: "GET",
    path: "/",
    desc: "Health check : statut du service et liste des endpoints.",
  },
  {
    method: "POST",
    path: "/recognize",
    desc: "Reconnaît un son. Accepte un fichier (multipart « file »), une URL JSON { url } ou du base64 JSON { audio }.",
  },
  {
    method: "GET",
    path: "/recognize?url=…&text=1",
    desc: "Même reconnaissance via query string. text=1 renvoie un message déjà formaté.",
  },
  {
    method: "POST",
    path: "/shazam",
    desc: "Alias de /recognize, même contrat d'entrée et de sortie.",
  },
];

function Index() {
  const [base, setBase] = useState(DEFAULT_BASE);
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TrackResult | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const stored = localStorage.getItem("shazam-api-base");
    if (stored) setBase(stored);
  }, []);

  const persistBase = (value: string) => {
    setBase(value);
    localStorage.setItem("shazam-api-base", value);
  };

  const identify = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    const endpoint = `${base.replace(/\/+$/, "")}/recognize`;
    try {
      let response: Response;
      if (file) {
        const body = new FormData();
        body.append("file", file);
        response = await fetch(endpoint, { method: "POST", body });
      } else if (url.trim()) {
        response = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: url.trim() }),
        });
      } else {
        setError("Choisis un fichier audio/vidéo ou colle une URL.");
        setLoading(false);
        return;
      }
      const data = await response.json();
      if (!response.ok || !data.success) {
        setError(data.error ?? `Erreur HTTP ${response.status}`);
      } else {
        setResult(data.result as TrackResult);
      }
    } catch (exception) {
      setError(
        exception instanceof Error
          ? `Requête impossible : ${exception.message}`
          : "Requête impossible",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="pointer-events-none fixed inset-x-0 top-0 h-[420px] bg-glow" aria-hidden />

      <section className="relative mx-auto max-w-5xl px-5 pt-16 pb-10 sm:pt-24">
        <span className="badge">Reconnaissance musicale · Docker · Render</span>
        <h1 className="mt-6 font-display text-4xl leading-tight tracking-tight sm:text-6xl">
          Shazam API
        </h1>
        <p className="mt-4 max-w-2xl text-base text-muted-foreground sm:text-lg">
          Envoie un <strong className="text-foreground">audio</strong> ou une{" "}
          <strong className="text-foreground">vidéo</strong> — l'API extrait l'extrait sonore et
          renvoie le titre, l'artiste, l'album et les liens d'écoute. Zéro clé API requise.
        </p>
      </section>

      <section className="relative mx-auto max-w-5xl px-5 pb-10">
        <div className="panel p-5 sm:p-7">
          <h2 className="font-display text-xl">Tester l'API</h2>
          <label className="mt-5 block text-xs uppercase tracking-widest text-muted-foreground">
            URL de base de l'API
          </label>
          <input
            className="field mt-2"
            value={base}
            onChange={(event) => persistBase(event.target.value)}
            placeholder={DEFAULT_BASE}
            spellCheck={false}
          />

          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            <div>
              <label className="block text-xs uppercase tracking-widest text-muted-foreground">
                Fichier audio / vidéo
              </label>
              <input
                ref={fileInput}
                type="file"
                accept="audio/*,video/*"
                className="field mt-2 file:mr-3 file:rounded-full file:border-0 file:bg-primary file:px-3 file:py-1 file:text-primary-foreground"
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null);
                  setUrl("");
                }}
              />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-widest text-muted-foreground">
                …ou une URL de média
              </label>
              <input
                className="field mt-2"
                value={url}
                onChange={(event) => {
                  setUrl(event.target.value);
                  if (event.target.value && fileInput.current) {
                    fileInput.current.value = "";
                    setFile(null);
                  }
                }}
                placeholder="https://exemple.com/clip.mp4"
                spellCheck={false}
              />
            </div>
          </div>

          <button className="btn-primary mt-6" onClick={identify} disabled={loading}>
            {loading ? "Analyse en cours…" : "Identifier le son"}
          </button>

          {error ? (
            <p className="mt-5 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {error}
            </p>
          ) : null}

          {result ? (
            <div className="mt-6 flex flex-col gap-5 rounded-2xl border border-border bg-card p-5 sm:flex-row">
              {result.cover ? (
                <img
                  src={result.cover}
                  alt={`Pochette de ${result.title ?? "l'album"}`}
                  loading="lazy"
                  className="h-32 w-32 shrink-0 rounded-xl object-cover shadow-lg"
                />
              ) : null}
              <div className="min-w-0">
                <p className="font-display text-2xl">{result.title ?? "—"}</p>
                <p className="text-accent">{result.artist ?? "—"}</p>
                <dl className="mt-3 space-y-1 text-sm text-muted-foreground">
                  {result.album ? <div>Album · {result.album}</div> : null}
                  {result.release ? <div>Sortie · {result.release}</div> : null}
                  {result.genre ? <div>Genre · {result.genre}</div> : null}
                </dl>
                {result.links ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {Object.entries(result.links).map(([name, link]) => (
                      <a key={name} href={link} target="_blank" rel="noreferrer" className="chip">
                        {name.replace(/_/g, " ")}
                      </a>
                    ))}
                  </div>
                ) : null}
                {result.preview ? (
                  <audio src={result.preview} controls className="mt-4 w-full max-w-sm" />
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className="relative mx-auto max-w-5xl px-5 pb-10">
        <h2 className="font-display text-2xl">Endpoints</h2>
        <div className="mt-4 grid gap-3">
          {ENDPOINTS.map((endpoint) => (
            <div key={endpoint.path} className="panel flex flex-col gap-1 p-4">
              <div className="flex items-center gap-3">
                <span className="method">{endpoint.method}</span>
                <code className="text-sm text-foreground">{endpoint.path}</code>
              </div>
              <p className="text-sm text-muted-foreground">{endpoint.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="relative mx-auto max-w-5xl px-5 pb-10">
        <h2 className="font-display text-2xl">Exemples</h2>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <pre className="code">{`curl -X POST "${DEFAULT_BASE}/recognize" \\
  -H "Content-Type: application/json" \\
  -d '{"url":"https://exemple.com/clip.mp4"}'`}</pre>
          <pre className="code">{`curl -X POST "${DEFAULT_BASE}/recognize?text=1" \\
  -F "file=@song.mp3"`}</pre>
          <pre className="code">{`{
  "success": true,
  "result": {
    "title": "Blinding Lights",
    "artist": "The Weeknd",
    "album": "After Hours",
    "cover": "https://...jpg",
    "links": { "spotify": "https://...", "shazam": "https://..." },
    "engine": "shazam"
  }
}`}</pre>
          <pre className="code">{`// commande bot (cmds/shazam.js)
const res = await axios.post(
  "${DEFAULT_BASE}/recognize?text=1",
  { url: event.messageReply.attachments[0].url }
);
message.reply(res.data.text);`}</pre>
        </div>
      </section>

      <section className="relative mx-auto max-w-5xl px-5 pb-20">
        <h2 className="font-display text-2xl">Déploiement sur Render</h2>
        <ol className="mt-4 grid gap-3">
          {[
            "Pousse ce dépôt sur GitHub (le Dockerfile est à la racine, pas dans un sous-dossier).",
            "Sur Render : New → Web Service → Docker, sélectionne le dépôt.",
            "Health check path : /  — le port est lu depuis la variable PORT.",
            "Optionnel : ajoute AUDD_API_TOKEN pour activer le moteur de secours AudD.",
          ].map((step, index) => (
            <li key={step} className="panel flex gap-3 p-4 text-sm text-muted-foreground">
              <span className="step">{index + 1}</span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
