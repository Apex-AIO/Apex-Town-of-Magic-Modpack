@echo off
rem REDO the whole slime fight with the shadow + flicker fixes (overwrites the existing HD files). Needs ComfyUI.
cd /d "%~dp0"
"%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe" hd_batch.py --set slime_fight --force %*
pause
