@echo off
rem Style comparison: every checkpoint in ComfyUI on Celica (standing) and the slime. Needs ComfyUI running.
rem Default strength 0.30. Example for stronger: run_ckpt_compare.bat --denoise 0.45
cd /d "%~dp0"
"%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe" ckpt_compare.py %*
pause
