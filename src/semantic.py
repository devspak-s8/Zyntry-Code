"""Semantic repo search: chunk -> embed -> index -> nearest neighbors.

Backend-side capability: the agent's ``fs.search_semantic`` tool resolves here
(inline, no runner round-trip) and the REST API exposes index/search directly.

Embeddings come from OpenAI (``text-embedding-3-small`` when a key is
configured) or Cloudflare Workers AI (``@cf/baai/bge-base-en-v1.5`` via the AI
binding). The index lives in D1 (vectors stored as JSON) so the same code runs
locally and on Cloudflare; swapping the store for Vectorize later does not
change the tool contract.

Semantic search is for *discovery*; pair it with ``fs.search`` (regex) for
exact refactoring targets — never replace regex with embeddings.
"""

import asyncio
import json
import math

import httpx

from runtime import Runtime
import store

CHUNK_SIZE = 400
CHUNK_OVERLAP = 60
EMBED_MODEL_OPENAI = "text-embedding-3-small"
EMBED_MODEL_WORKERS_AI = "@cf/baai/bge-base-en-v1.5"
MAX_INPUT_CHARS = 2048  # embedding models cap input length


def chunk_file(path: str, language: str | None, content: str) -> list[dict]:
    """Split a file into overlapping line chunks."""
    lines = content.splitlines(keepends=True)
    chunks: list[dict] = []
    start = 0
    while start < len(lines):
        end = min(start + CHUNK_SIZE, len(lines))
        text = "".join(lines[start:end])
        if text.strip():
            chunks.append({"path": path, "language": language,
                           "start_line": start + 1, "end_line": end,
                           "content": text})
        if end >= len(lines):
            break
        start = max(start + CHUNK_SIZE - CHUNK_OVERLAP, start + 1)
    return chunks


def chunk_files(repo_files: list[dict]) -> list[dict]:
    out: list[dict] = []
    for f in repo_files:
        content = f.get("content")
        if not content:
            continue
        out.extend(chunk_file(f.get("path", "?"), f.get("language"), content))
    return out


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


async def embed(runtime: Runtime, texts: list[str]) -> list[list[float]]:
    """Embed texts via OpenAI (key) or Workers AI bge (binding), with retries."""
    texts = [t[:MAX_INPUT_CHARS] for t in texts]
    key = runtime.get("OPENAI_API_KEY")
    if key:
        base = str(runtime.get("OPENAI_BASE_URL", "https://api.openai.com/v1") or "").rstrip("/")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        for attempt in range(3):
            try:
                with httpx.Client(timeout=120.0) as client:
                    resp = client.post(f"{base}/embeddings",
                                       json={"model": EMBED_MODEL_OPENAI, "input": texts},
                                       headers=headers)
                if resp.status_code >= 400:
                    raise RuntimeError(f"embeddings provider returned {resp.status_code}: {resp.text[:300]}")
                rows = sorted(resp.json().get("data", []), key=lambda d: d.get("index", 0))
                return [r["embedding"] for r in rows]
            except httpx.HTTPError as exc:
                if attempt == 2:
                    raise RuntimeError(f"embeddings http error: {exc}") from exc
                await asyncio.sleep(0.5 * (2 ** attempt))

    ai = runtime.workers_ai
    if ai is not None:
        result = await ai.run(EMBED_MODEL_WORKERS_AI, {"texts": texts})
        data = result.get("data") if isinstance(result, dict) else None
        if data:
            return [list(row) for row in data]

    raise RuntimeError(
        "no embedding provider available — configure OPENAI_API_KEY or a Workers AI binding")


async def index_workspace(runtime: Runtime, workspace_id: str) -> dict:
    """Chunk + embed + index the workspace's ingested repo files."""
    db = runtime.db
    ws = await store.get_workspace(db, workspace_id)
    if ws is None:
        raise ValueError("workspace not found")
    if not ws.get("task_id"):
        raise ValueError("workspace has no task — nothing to index")

    repo_files = await store.get_repo_files(db, ws["task_id"])
    if not repo_files:
        raise ValueError("workspace has no ingested repo files — POST /tasks/{id}/repo first")

    chunks = chunk_files(repo_files)
    if not chunks:
        raise ValueError("no indexable file contents found in the repo snapshot")

    vectors = await embed(runtime, [c["content"] for c in chunks])
    records = [dict(c, embedding=json.dumps(v)) for c, v in zip(chunks, vectors)]
    await store.replace_semantic_chunks(db, workspace_id, records)
    return {"workspace_id": workspace_id, "files": len(repo_files), "chunks": len(records)}


async def search_query(runtime: Runtime, workspace_id: str, query: str, top_k: int = 5) -> list[dict]:
    """Embed the query and return the nearest chunks."""
    db = runtime.db
    chunks = await store.get_semantic_chunks(db, workspace_id)
    if not chunks:
        raise ValueError("semantic index is empty — POST /workspaces/{id}/semantic/index first")

    query_vec = (await embed(runtime, [query]))[0]
    scored = []
    for c in chunks:
        try:
            vec = json.loads(c["embedding"])
        except (json.JSONDecodeError, TypeError):
            continue
        scored.append((cosine(query_vec, vec), c))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {"path": c["path"], "start_line": c["start_line"], "end_line": c["end_line"],
         "content": c["content"][:600], "score": round(score, 4)}
        for score, c in scored[:top_k]
    ]