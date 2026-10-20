@echo off
rem Renders EVERYTHING that is queued and not rendered yet.  Starts ComfyUI by itself if it is not running.
rem   1. sets\redo.txt (if there is one): files the art catalog found were rendered with the wrong context/recipe
rem   2. the queued lists: forest monsters, town women, everything collected while playing (pending)
rem   3. the interface: main menu, world map, menus, icons, symbols, effects (ui_batch.py)
rem Safe to stop and restart: finished files are skipped (the redo list is only retired once it has run through).
cd /d "%~dp0"
set PY="%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe"
set tries=0

curl -s -m 3 http://127.0.0.1:8000/system_stats >nul 2>&1
if not errorlevel 1 goto comfyok
echo ComfyUI is not running - starting it ...
start "" "%LOCALAPPDATA%\Programs\ComfyUI\Comfy Desktop\Comfy Desktop.exe"

:waitcomfy
timeout /t 5 /nobreak >nul
curl -s -m 3 http://127.0.0.1:8000/system_stats >nul 2>&1
if not errorlevel 1 goto comfyok
set /a tries+=1
if %tries% LSS 60 goto waitcomfy
echo ComfyUI did not start within 5 minutes. Start it by hand and run this file again.
pause
exit /b 1

:comfyok
echo ComfyUI is ready.
if not exist sets\redo.txt goto noredo
%PY% hd_batch.py --set redo --force --no-open
if not errorlevel 1 move /y sets\redo.txt "..\debug\logs\redo_done.txt" >nul
:noredo
%PY% hd_batch.py --set monsters_forest2 --no-open
%PY% hd_batch.py --set town_women --no-open
%PY% hd_batch.py --set pending --no-open
rem 3. everything else: main menu art, world map, menus, icons, symbols, effects (upscale only, no ComfyUI needed)
%PY% ui_batch.py
pause
