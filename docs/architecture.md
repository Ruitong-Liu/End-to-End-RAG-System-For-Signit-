# Architecture and Streaming

## Ingestion and retrieval

`app/ingest.py` reads Markdown/TXT documents, normalizes text, splits at headings, and creates chunks within a 512-token `cl100k_base` budget. Headings consume part of the budget; up to 64 tokens overlap, shortened where necessary for valid Unicode. Content hashes support deduplication; duplicate source paths are retained as aliases.

`app/retrieval.py` supports `bm25`, `dense`, `hybrid`, and `hybrid_rerank`. The full pipeline retrieves BM25 and dense candidates, combines ranks using RRF (`k=60`), reranks the fused candidate pool with BGE, and returns up to five passages. Source titles and headings participate in retrieval. Normalized embedding vectors are cached using corpus/model fingerprints, and retrieval results use a bounded TTL cache.

Defaults are BGE-small-zh-v1.5 and BGE-reranker-base on CPU. Documents and queries are embedded locally. Model token limits differ from the ingestion tokenizer and can truncate model input. The initial reranker threshold is not a calibrated confidence guarantee.

## Orchestration

`app/service.py` handles greetings, requests for clarification, human-support guidance, and document questions. LangChain prompts rewrite follow-up questions and translate English search queries when the corpus is Chinese. Original source documents are preserved; generation is requested in English.

Selected evidence is constrained by a token budget. Low evidence scores trigger a fallback; eligible evidence is passed to DeepSeek for grounded generation. Questions and selected evidence are sent to that provider when a key is configured. The server does not persist conversation history.

## Real-time delivery

Provider text deltas are forwarded immediately through FastAPI and Nginx to the React SSE reader. There is no post-generation slicing or artificial delay. Status events indicate queueing, rewriting, retrieval, generation, and validation. Heartbeat comments keep inactive phases connected, while proxy buffering, caching, and compression are disabled on the streaming route.

Live output is provisional. At completion, citation-number validation either confirms the answer or emits `replace` with a fallback. Provider failures replace incomplete drafts with an explicit error. A stream ending without `done` is incomplete.

Stop aborts the browser request. Disconnect handling cancels in-flight provider reads, closes the upstream iterator, and releases the request slot. Stopped drafts are excluded from future conversation history. CPU work already executing in a Python worker thread may finish, and provider tokens already generated may be billed.

## Source map

| Module | Responsibility |
| --- | --- |
| `backend/app/config.py` | Environment-based settings |
| `backend/app/ingest.py` | Normalization, chunking, deduplication and metadata |
| `backend/app/retrieval.py` | BM25, embeddings, RRF, reranking and caches |
| `backend/app/service.py` | Routing, LangChain prompts, generation and citation checks |
| `backend/app/main.py` | Validation, API endpoints, SSE and disconnect cleanup |
| `backend/app/evaluate.py` | Retrieval metrics and measured output |
| `frontend/src/main.tsx` | Chat interface, sources and cancellation |
| `frontend/src/stream.ts` | Incremental SSE decoding and replacement events |
