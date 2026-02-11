@echo off
set PYTHONPATH=C:\Data\projects\AskMe
set PYTHONPATH=%PYTHONPATH%;C:\Data\projects\AskMe\backend
cd C:\Data\projects\AskMe
venv\Scripts\uvicorn.exe backend.app.main:app --reload --port 8000