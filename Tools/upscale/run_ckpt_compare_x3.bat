@echo off
rem Checkpoint style comparison at 3x strength (denoise 0.90). Needs ComfyUI running.
cd /d "%~dp0"
"%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe" ckpt_compare.py --denoise 0.90 %*
pause
