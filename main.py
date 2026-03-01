"""
soul.py v1.0 Demo — RAG Memory Backend
Shows semantic retrieval: memory grows, only relevant chunks are injected.
Supports both qdrant (semantic) and bm25 (keyword) modes.
"""
import os, sys, time, uuid
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, Cookie
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Pull in soul.py v1.0 from the branch (bundled)
sys.path.insert(0, ".")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Mode: "qdrant" or "bm25"
MEMORY_MODE = os.environ.get("MEMORY_MODE", "qdrant")

_client = None
def get_client():
    global _client
    if _client is None:
        import anthropic
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key: raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = anthropic.Anthropic(api_key=key)
    return _client

sessions: dict = {}
SESSION_TTL = 1800

DEFAULT_SOUL = """You are a helpful, persistent AI assistant running on soul.py v1.0 with RAG memory.
Your memory is retrieved semantically — only the most relevant past exchanges are shown to you.
Be concise and direct. When a new session starts, acknowledge what you remember naturally."""

def make_rag_memory(tmp_path):
    from rag_memory import RAGMemory
    return RAGMemory(
        memory_path=str(tmp_path),
        mode=MEMORY_MODE,
        collection_name=f"soul_demo_{uuid.uuid4().hex[:8]}",  # unique per visitor
        qdrant_url=os.environ.get("QDRANT_URL",""),
        qdrant_api_key=os.environ.get("QDRANT_API_KEY",""),
        azure_embedding_endpoint=os.environ.get("AZURE_EMBEDDING_ENDPOINT",""),
        azure_embedding_key=os.environ.get("AZURE_EMBEDDING_KEY",""),
        k=4,
    )

def get_or_create_session(session_id):
    now = time.time()
    stale = [k for k,v in sessions.items() if now - v["last_active"] > SESSION_TTL]
    for k in stale:
        # cleanup qdrant collection
        try: sessions[k]["rag"].cleanup()
        except: pass
        del sessions[k]

    if session_id not in sessions:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".md", delete=False)
        tmp.write(b"# MEMORY.md\n")
        tmp.close()
        rag = make_rag_memory(tmp.name)
        sessions[session_id] = {
            "history": [], "rag": rag, "mem_path": tmp.name,
            "last_active": now, "message_count": 0, "session_count": 1,
        }
    sessions[session_id]["last_active"] = now
    return sessions[session_id]

def build_system(session, query):
    context = session["rag"].retrieve(query, k=4)
    return f"{DEFAULT_SOUL}\n\n---\n\n{context}"

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(open("index.html").read())

@app.post("/ask")
async def ask(request: Request, session_id: str = Cookie(default=None)):
    try:
        body = await request.json()
        question = body.get("question","").strip()
        if not question: return JSONResponse({"error":"empty"},status_code=400)
        if not session_id: session_id = str(uuid.uuid4())

        session = get_or_create_session(session_id)
        session["history"].append({"role":"user","content":question})

        client = get_client()
        resp = client.messages.create(
            model="claude-haiku-4-5", max_tokens=512,
            system=build_system(session, question),
            messages=session["history"],
        )
        answer = resp.content[0].text.strip()
        session["history"].append({"role":"assistant","content":answer})
        session["message_count"] += 1
        session["rag"].append(f"Q: {question}\nA: {answer}")

        memory_text = Path(session["mem_path"]).read_text()
        retrieved = session["rag"].retrieve(question, k=4)

        response = JSONResponse({
            "answer": answer,
            "memory": memory_text,
            "retrieved": retrieved,
            "message_count": session["message_count"],
            "session_count": session["session_count"],
            "total_memories": session["rag"].count(),
            "mode": MEMORY_MODE,
        })
        response.set_cookie("session_id", session_id, max_age=SESSION_TTL, samesite="lax")
        return response
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/new-session")
async def new_session(session_id: str = Cookie(default=None)):
    if session_id and session_id in sessions:
        sessions[session_id]["history"] = []
        sessions[session_id]["session_count"] += 1
        memory_text = Path(sessions[session_id]["mem_path"]).read_text()
        return JSONResponse({
            "ok": True,
            "memory": memory_text,
            "session_count": sessions[session_id]["session_count"],
            "total_memories": sessions[session_id]["rag"].count(),
        })
    return JSONResponse({"ok":False}, status_code=400)

@app.post("/reset")
async def reset(session_id: str = Cookie(default=None)):
    if session_id and session_id in sessions:
        try: os.unlink(sessions[session_id]["mem_path"])
        except: pass
        del sessions[session_id]
    return JSONResponse({"ok": True})

@app.get("/health")
async def health():
    return {"ok": True, "sessions": len(sessions),
            "key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "mode": MEMORY_MODE}
