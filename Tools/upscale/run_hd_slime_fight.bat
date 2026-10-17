@echo off
rem HD for everything in the slime fight (Celica: standing, hurt, casting, breast + crotch grabs; the slime).
rem Needs ComfyUI running. Installs into the game. Safe to stop and start again: finished files are skipped.
cd /d "%~dp0"
"%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe" hd_batch.py --set slime_fight %*
pause
