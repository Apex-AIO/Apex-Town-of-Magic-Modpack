@echo off
rem Renders EVERYTHING that is queued and not rendered yet.
rem   1. sets\redo.txt (if there is one): files the art catalog found were rendered with the wrong context/recipe
rem   2. the queued lists: forest monsters, town women, everything collected while playing (pending)
rem Needs ComfyUI running. Safe to stop and restart: finished files are skipped (the redo list is only retired
rem once it has run through completely).
cd /d "%~dp0"
set PY="%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe"
if exist sets\redo.txt (
    %PY% hd_batch.py --set redo --force --no-open
    if not errorlevel 1 move /y sets\redo.txt "..\debug\logs\redo_done.txt" >nul
)
%PY% hd_batch.py --set monsters_forest2 --no-open
%PY% hd_batch.py --set town_women --no-open
%PY% hd_batch.py --set pending
pause
