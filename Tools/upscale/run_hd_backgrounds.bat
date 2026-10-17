@echo off
rem HD backgrounds (recipe B): the ones you have seen in game first, then every other background.
rem Needs ComfyUI running. Safe to stop and restart: finished files are skipped.
cd /d "%~dp0"
set PY="%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe"
%PY% ..\art\bg_catalog.py
%PY% bg_batch.py
pause
