@echo off
rem Celica extra-detail test (tile ControlNet + detail LoRAs + feet pass). Needs ComfyUI running.
cd /d "%~dp0"
"%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe" detail_test.py %*
pause
