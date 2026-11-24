# LeadDesk — container image for any Docker host (Hugging Face Spaces, Render, Koyeb, Fly…).
# Runs keyless (offline rules) until GOOGLE_API_KEY is set as a secret, then uses Gemini.
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY . .

# Writable cache/leads dirs (filesystem may be ephemeral; that's fine for a demo).
# Precomputed document embeddings (embeddings/*.json), so startup makes no API calls and a
# rate-limited key can't crash a deploy. Changed documents are embedded on startup as before.
RUN mkdir -p .cache leads && for f in embeddings/*.json; do cp "$f" ".cache/embeddings-$(basename "$f")"; done

# Hugging Face Spaces expects 7860; Render/Koyeb set $PORT. Support both.
ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
