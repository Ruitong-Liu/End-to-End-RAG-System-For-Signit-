# Verification Notes

The development version passed 20 backend tests and four frontend SSE tests, TypeScript checking, the production frontend build, and Docker image builds. A live DeepSeek integration request returned a cited English answer, and a separate real streaming check observed 227 text frames with answer text arriving before the completion event.

Coverage includes ingestion/deduplication, title-aware retrieval, RRF, caches, API input validation, query rewriting, evidence fallback, citation numbering, partial-response replacement, fragmented UTF-8/SSE parsing, cancellation, upstream iterator closure, and ASGI disconnect cleanup.

These are local engineering checks. They do not establish production answer accuracy, calibrated refusal behavior, production p95 latency, or cost improvements. Tests use explicit local fake models where appropriate; those runs are not provider evaluations. GitHub Actions has not yet been executed for this repository.

The public repository contains synthetic smoke data only. Company documents, internal evaluation materials, provider credentials, and local transcripts are not included. Run the checks against the public source using the commands in the README. The macOS package snapshot in `backend/requirements-tested.txt` is a historical development snapshot; Linux packages and dependency resolution can differ.

## Public source preparation checks

The clean public source was rechecked: 20 backend tests, four frontend SSE tests, TypeScript/production build, and Compose configuration validation passed. The included password-reset and report-export starter questions also retrieved the synthetic guide with BGE reranker scores above the default threshold. These are smoke checks, not a quality benchmark. The uncalibrated threshold may reject other answerable questions and should be calibrated for a deployed corpus. No private corpus or configured provider key was required for these checks.
