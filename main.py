"""
soul.py — Live Demo
FastAPI app: each visitor gets an isolated agent session.
Memory resets after 30 min of inactivity.
"""
import os, time, uuid
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request, Cookie
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import anthropic

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# In-memory session store: session_id -> {history, memory, soul, last_active}
sessions: dict = {}
SESSION_TTL = 1800  # 30 min

DEFAULT_SOUL = """You are a helpful, persistent AI assistant running on soul.py.
You have a memory — every exchange is logged and you read it at the start of each session.
You are concise, direct, and genuinely useful. You remember everything from this session."""

def get_or_create_session(session_id: str) -> dict:
    now = time.time()
    # Evict stale sessions
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
    body = await request.json()
    question = body.get("question", "").strip()
    if not question:
        return JSONResponse({"error": "empty question"}, status_code=400)

    if not session_id:
        session_id = str(uuid.uuid4())

    session = get_or_create_session(session_id)
    session["history"].append({"role": "user", "content": question})

    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=build_system(session),
        messages=session["history"],
    )
    answer = resp.content[0].text.strip()
    session["history"].append({"role": "assistant", "content": answer})
    session["message_count"] += 1

    # Append to memory
    ts = datetime.now().strftime("%H:%M")
    session["memory"] += f"\n## {ts}\nQ: {question}\nA: {answer}\n"

    response = JSONResponse({
        "answer": answer,
        "memory": session["memory"],
        "message_count": session["message_count"],
    })
    response.set_cookie("session_id", session_id, max_age=SESSION_TTL, samesite="lax")
    return response

@app.post("/reset")
async def reset(session_id: str = Cookie(default=None)):
    if session_id and session_id in sessions:
        del sessions[session_id]
    return JSONResponse({"ok": True})

@app.get("/health")
async def health():
    return {"ok": True, "sessions": len(sessions)}
