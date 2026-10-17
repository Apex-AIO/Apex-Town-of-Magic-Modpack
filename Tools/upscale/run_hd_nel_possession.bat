@echo off
rem HD (recipe P) for Nel + all new Celica poses/expressions. Needs ComfyUI. Safe to stop and restart.
cd /d "%~dp0"
"%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe" hd_batch.py --set nel_possession %*
pause
