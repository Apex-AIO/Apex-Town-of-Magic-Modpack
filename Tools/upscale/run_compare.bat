@echo off
rem Builds upscale comparisons into "Claude Workspace\Upscale\compare"
cd /d "%~dp0"
"%USERPROFILE%\Documents\ComfyUI\.venv\Scripts\python.exe" compare_upscalers.py %*
pause
