@echo off
rem Renders EVERYTHING that is queued and not rendered yet (pending + town_women + monsters_forest2).
rem Needs ComfyUI running. Safe to stop and restart: finished files are skipped.
cd /d "%~dp0"
set PY="%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe"
%PY% hd_batch.py --set monsters_forest2 --no-open
%PY% hd_batch.py --set town_women --no-open
%PY% hd_batch.py --set pending
pause
