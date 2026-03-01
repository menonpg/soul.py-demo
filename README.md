# soul.py — Live Demo

Interactive demo for [soul.py](https://github.com/menonpg/soul.py).

Chat with an agent and watch MEMORY.md grow in real time. Each visitor gets an isolated session. Memory resets after 30 min of inactivity.

## Deploy to Railway

1. Fork this repo
2. New project on Railway → Deploy from GitHub
3. Add env var: `ANTHROPIC_API_KEY=sk-ant-...`
4. Deploy

## Run locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --reload
```
