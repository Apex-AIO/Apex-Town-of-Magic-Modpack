@echo off
rem Redo the slime fight with recipe P (overwrites), then Nel + possession. Needs ComfyUI. Long: run overnight.
cd /d "%~dp0"
"%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe" hd_batch.py --set slime_fight --force --no-open %*
"%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe" hd_batch.py --set nel_possession %*
pause
