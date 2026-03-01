"""
soul.py — Live Demo
Shows the core soul.py promise: memory persists across sessions.
Session 1: chat, build up memory.
New Session: history clears, but MEMORY.md carries over — agent remembers.
"""
import os, time, uuid
from datetime import datetime
from fastapi import FastAPI, Request, Cookie
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_client = None
def get_client():
    global _client
    if _client is None:
        import anthropic
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = anthropic.Anthropic(api_key=key)
    return _client

sessions: dict = {}
SESSION_TTL = 1800

DEFAULT_SOUL = """You are a helpful, persistent AI assistant running on soul.py.
You have a memory — every exchange is logged and injected at the start of each session.
You are concise and direct. When a new session starts, acknowledge what you remember naturally — don't say 'based on our previous conversation', just speak as if you know the person."""

def get_or_create_session(session_id: str) -> dict:
    now = time.time()
    stale = [k for k, v in sessions.items() if now - v["last_active"] > SESSION_TTL]
    for k in stale:
        del sessions[k]
    if session_id not in sessions:
        sessions[session_id] = {
            "history": [],
            "memory": "# MEMORY.md\n(No memories yet — start chatting!)\n",
            "soul": DEFAULT_SOUL,
            "last_active": now,
            "message_count": 0,
            "session_count": 1,
        }
    sessions[session_id]["last_active"] = now
    return sessions[session_id]

def build_system(session: dict) -> str:
    return f"{session['soul']}\n\n---\n\n# Your Memory\n{session['memory']}"

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(open("index.html").read())

@app.post("/ask")
async def ask(request: Request, session_id: str = Cookie(default=None)):
    try:
        body = await request.json()
        question = body.get("question", "").strip()
        if not question:
            return JSONResponse({"error": "empty question"}, status_code=400)

        if not session_id:
            session_id = str(uuid.uuid4())

        session = get_or_create_session(session_id)
        session["history"].append({"role": "user", "content": question})

        client = get_client()
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            system=build_system(session),
            messages=session["history"],
        )
        answer = resp.content[0].text.strip()
        session["history"].append({"role": "assistant", "content": answer})
        session["message_count"] += 1

        ts = datetime.now().strftime("%H:%M")
        session["memory"] += f"\n## Session {session['session_count']} — {ts}\nQ: {question}\nA: {answer}\n"

        response = JSONResponse({
            "answer": answer,
            "memory": session["memory"],
            "message_count": session["message_count"],
            "session_count": session["session_count"],
        })
        response.set_cookie("session_id", session_id, max_age=SESSION_TTL, samesite="lax")
        return response

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/new-session")
async def new_session(session_id: str = Cookie(default=None)):
    """Start a new session — clears history but KEEPS memory. This is the demo moment."""
    if session_id and session_id in sessions:
        sessions[session_id]["history"] = []  # clear conversation history
        sessions[session_id]["session_count"] += 1  # increment session number
        # memory persists — this is the point
        return JSONResponse({
            "ok": True,
            "memory": sessions[session_id]["memory"],
            "session_count": sessions[session_id]["session_count"],
        })
    return JSONResponse({"ok": False, "error": "no session"}, status_code=400)

@app.post("/reset")
async def reset(session_id: str = Cookie(default=None)):
    """Full reset — clears everything including memory."""
    if session_id and session_id in sessions:
        del sessions[session_id]
    return JSONResponse({"ok": True})

@app.get("/health")
async def health():
    key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return {"ok": True, "sessions": len(sessions), "key_set": key_set}
