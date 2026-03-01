# soul.py v1.0 — RAG Demo

Live demo for [soul.py v1.0-rag branch](https://github.com/menonpg/soul.py/tree/v1.0-rag).

Shows semantic RAG retrieval — only relevant memory chunks are injected per query.
Watch the "Retrieved Context" panel to see what the agent actually sees vs full MEMORY.md.

**v0.1 demo:** https://soul.themenonlab.com
**v1.0 demo:** this app

## Deploy to Railway

1. Fork this repo
2. Railway → New Project → Deploy from GitHub
3. Add env vars:
   - `ANTHROPIC_API_KEY`
   - `QDRANT_URL`
   - `QDRANT_API_KEY`
   - `AZURE_EMBEDDING_ENDPOINT`
   - `AZURE_EMBEDDING_KEY`
   - `MEMORY_MODE=qdrant` (or `bm25` for keyword mode)
4. Deploy
