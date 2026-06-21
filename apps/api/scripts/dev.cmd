@echo off
uv run python -m uvicorn app.api:app --reload --host 127.0.0.1 --port 8000
