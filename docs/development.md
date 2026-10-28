# Development and Deployment

## Configuration

Copy `.env.example` to `.env` and edit it locally. Keep `DEEPSEEK_API_KEY` on the backend; do not place it in frontend variables. Recreate the API container after changing credentials:

```sh
docker compose up -d --force-recreate api
```

The example model is `deepseek-flash`; use the identifier available to your provider account. Configuration also covers model device, retrieval mode/depth, passage count, context budget, reranker threshold, cache size/TTL, and provider prices. A price of zero means cost is unavailable, not that requests are free.

## Local execution

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -e './backend[test,models]'
cp .env.example .env
(cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file ../.env)
```

In a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to the local backend. Backend defaults resolve `../data/demo` and `../data/index` when launched from `backend/`. Set `CORPUS_DIR` and `INDEX_DIR` if using different local locations. Do not copy provider keys into frontend `.env` files.

## Add local documents

Place permitted Markdown/TXT documents in `data/private/`, then add this setting to the root `.env`:

```dotenv
RAG_CORPUS_PATH=./data/private
```

Restart the API container to ingest the corpus. Its data mount is read-only, while model/index volumes persist across restarts. The repository ignores non-demo data by default. Never add private documents to `data/demo/`: that directory is intentionally shareable.

## Tests and live provider check

```sh
(cd backend && ../.venv/bin/python -m pytest -q)
(cd frontend && npm ci && npm test && npm run build)
```

To verify the deployed provider integration after configuring your own key:

```sh
.venv/bin/python scripts/verify_deepseek.py --question "How do I reset my password?"
```

This command makes a real provider request and can incur usage charges. It records answer text, citations, token usage, token-frame count, and arrival timings under the Git-ignored `evaluation/results/` directory. It does not print the key. Use a question that your selected corpus can answer.

## Docker

```sh
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose down
```

The image installs the official PyTorch CPU wheel. The health endpoint confirms API/corpus readiness, not provider authentication or model warm-up. Initial builds and model downloads need network access. Compose binds only to localhost and is intended for local demonstration.

## Prepare a source archive

```sh
python3 scripts/package_source.py --output release/source.zip
```

The script packages an explicit source allowlist and excludes Git internals, credentials, local datasets, generated results, dependencies, and model caches. The `release/` directory is ignored by Git. Review new files before committing; `.gitignore` alone cannot remove a secret already committed to history.
