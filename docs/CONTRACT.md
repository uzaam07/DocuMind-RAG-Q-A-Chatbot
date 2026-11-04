# DocuMind API contract (source of truth for backend, frontend, eval)

All routes live under `/api` except `GET /health`. JSON everywhere except uploads (multipart) and the SSE ask endpoint.
Timestamps: ISO-8601 UTC strings ending in `Z`. IDs: UUID strings.

## Errors
Every non-2xx JSON response: `{"error": {"code": "<snake_case>", "message": "<human sentence naming problem and fix>"}}`.
Codes used: `validation_error` (422), `unauthorized` (401), `forbidden` (403), `not_found` (404), `conflict` (409), `rate_limited` (429), `upstream_unavailable` (503), `internal_error` (500).

## Auth
Bearer token: `Authorization: Bearer <jwt>`.
- `POST /api/auth/register` body `{"email": str, "password": str(min 8)}` -> 201 `{"access_token": str, "token_type": "bearer", "user": User}`. Duplicate email -> 409 `conflict`.
- `POST /api/auth/login` body `{"email","password"}` -> 200 same shape as register. Bad credentials -> 401 `unauthorized`.
- `GET /api/auth/me` -> `User` = `{"id","email","created_at"}`.

## Documents
`Document` = `{id, filename, file_type: "pdf"|"docx"|"txt"|"md"|"xlsx"|"pptx"|"html"|"png"|"jpg"|"jpeg"|"webp"|"unknown", size_bytes, status: "processing"|"failed"|"ready", stage: "queued"|"parsing"|"chunking"|"embedding"|"indexing"|"done", progress_done: int, progress_total: int, chunk_count: int, error: str|null, created_at, updated_at}`
- `POST /api/documents` multipart, repeatable field name `files` -> 202 `Document[]`. Files rejected at intake (bad extension, oversize, empty, wrong signature) are still returned as `status:"failed"` documents with a readable `error`.
- `GET /api/documents` -> `Document[]` newest first.
- `GET /api/documents/{id}` -> `Document`.
- `DELETE /api/documents/{id}` -> 204.
- `POST /api/documents/{id}/reindex` -> 202 `Document`.
- `POST /api/documents/sample` -> 200 `Document[]` (bundled sample docs; idempotent, never duplicates).
- `progress_done/progress_total` are meaningful while `stage` is `embedding` (chunks embedded / total chunks).

## Sessions and messages
`Session` = `{id, title, created_at, updated_at}`. `Message` = `{id, role: "user"|"assistant", content, citations: Citation[], meta: DonePayload|null, feedback: "helpful"|"not_helpful"|null, created_at}`.
- `GET /api/sessions` -> `Session[]` most recently updated first.
- `GET /api/sessions/search?q=<term>&limit=25` -> matching sessions with `session_id`, `title`, `excerpt`, `matched_role`, and `updated_at`; searches titles and message bodies and is scoped to the authenticated user.
- `POST /api/sessions` body `{"title"?: str}` -> 201 `Session` (default title "New chat"; auto-renamed from the first question).
- `PATCH /api/sessions/{id}` body `{"title": str}` -> `Session`.
- `DELETE /api/sessions/{id}` -> 204.
- `GET /api/sessions/{id}/messages` -> `Message[]` oldest first, including the signed-in user's feedback signal.
- `GET /api/sessions/{id}/export` -> `{"markdown": str, "filename": str}`.
- `POST /api/messages/{id}/feedback` body `{"rating": "helpful"|"not_helpful", "reason"?: str}` -> saved feedback; message ownership is enforced.

## Citation
`Citation` = `{id: int (1-based, matches [n] markers), doc_id, filename, page_or_section: str ("Page 4" | "Section: Leave policy" | "Chunk 7"), snippet: str (full retrieved chunk text), highlight: str|null (substring of snippet: the best supporting sentence), score: float 0..1}`

## Asking
Request body (both endpoints): `{"question": str (1..2000), "doc_ids"?: str[]|null (null/omitted = all user docs), "mode"?: "vector"|"hybrid"|"hybrid_rerank"|null (null = server default)}`

### `POST /api/sessions/{id}/ask` -> `text/event-stream`
Frames are `event: <name>\ndata: <single-line JSON>\n\n`. Exact order:
1. one or more `stage`: `{"stage": "searching"|"reranking"|"writing"}` (`reranking` only in `hybrid_rerank` mode and not on cache hit)
2. exactly one `citations`: `{"citations": Citation[]}` (empty array when not found)
3. zero or more `token`: `{"text": str}`
4. exactly one `done` (or `error` instead, at any point): 
   `{"message_id", "answer": str, "cached": bool, "mode": str, "not_found": bool, "rewritten_question": str|null, "counts": {"retrieved","fused","reranked","used"}, "timings": {"embed_ms","retrieve_ms","rerank_ms","generate_ms","total_ms"}}` (all ints)
5. `error`: `{"code": str, "message": str}`
Cache hit: same events replayed fast with `cached: true`.
Not found: `citations` empty, one `token` with the not-found message, `done.not_found = true`.
`counts`: retrieved = distinct candidates from vector+BM25 (vector mode: vector candidates); fused = candidates kept after fusion (max 10); reranked = kept after rerank/selection (max top_k); used = citations returned.

### `POST /api/ask` -> 200 JSON (stateless, no session)
`{"answer", "citations", "not_found", "cached", "mode", "rewritten_question": null, "counts", "timings", "retrieved": [{"rank": int, "doc_id", "filename", "page_or_section", "score"}]}` where `retrieved` is the final top_k list before the score threshold is applied.

## Stats and eval
- `GET /api/stats` -> `{"answer_cache": {"hits","misses","hit_rate","entries"}, "embedding_cache": {"hits","misses","hit_rate","entries"}, "usage": {"documents","sessions","messages"}}` (`hit_rate` float 0..1, current user for usage and caches' entries; hits/misses are process-wide counters since start).
- `GET /api/eval/latest` -> `{"available": false}` or `{"available": true, ...results}` where results =
```json
{"generated_at": "...Z", "mock": true, "k": 5, "dataset_size": 32,
 "modes": {"vector": {"hit_at_k": 0.0, "mrr": 0.0, "answer_accuracy": 0.0, "citation_correctness": 0.0, "fallback_accuracy": 0.0, "latency_p50_ms": 0, "latency_p95_ms": 0},
           "hybrid": {...}, "hybrid_rerank": {...}},
 "cache": {"cold_ms": 0, "warm_ms": 0, "speedup": 0.0}}
```
All metric fractions are 0..1.
- `GET /health` -> `{"status": "ok", "db": "ok", "chroma": "ok"}`.

## Chunk labelling (affects eval and UI)
- PDF: chunks never cross pages; `page_or_section` = `"Page N"` (1-based).
- MD: heading text of nearest preceding `#` heading -> `"Section: <heading>"`.
- DOCX: nearest preceding paragraph whose style name starts with `Heading` -> `"Section: <heading>"`.
- TXT: nearest preceding heading line, defined as a line of 3..80 chars that is entirely uppercase (letters, digits, spaces, punctuation) -> `"Section: <Heading in original case>"`.
- No heading found -> `"Chunk N"` (1-based chunk index).

## Environment variables
`GEMINI_API_KEY`, `GEMINI_CHAT_MODEL` (gemini-3.5-flash-lite), `LOCAL_EMBEDDING_MODEL` (sentence-transformers/all-MiniLM-L6-v2), `MOCK_LLM` (true/false), `JWT_SECRET`, `JWT_EXPIRE_MINUTES` (60), `CHUNK_SIZE` (800), `CHUNK_OVERLAP` (150), `TOP_K` (5), `RETRIEVAL_MODE` (hybrid_rerank), `SCORE_THRESHOLD`, `MAX_UPLOAD_MB` (20), `CACHE_TTL_SECONDS` (86400), `CORS_ORIGINS` (comma list), `DATA_DIR` (./data), `DATABASE_URL` (optional SQLAlchemy URL; SQLite default), `REDIS_URL` (optional Redis/RQ queue; Docker Compose enables it), `EVAL_RESULTS_PATH` (../eval/results/results.json), `SAMPLE_DOCS_DIR` (../eval/sample_docs).

## Ports
Backend 8000. Vite dev server 5173 proxies `/api` and `/health` to `http://localhost:8000`. Docker frontend (nginx) listens on 8080 inside, published as 3000, proxies `/api` and `/health` to `http://backend:8000`.
