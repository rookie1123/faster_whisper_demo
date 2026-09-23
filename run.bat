@echo off
REM Wrapper that prefers the project-local .venv, so the script never picks up
REM another Python from PATH.
REM
REM Keep this file ASCII-only. cmd.exe reads .bat files using the OEM codepage
REM (GBK on Chinese Windows); non-ASCII comments break parsing on some machines.

setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo Usage: run.bat ^<script^> [args...]
    echo   run.bat demo.py
    echo   run.bat eval_zh.py samples\speaker\speaker_fujian.mp3 samples\reading_script.txt
    echo   run.bat transcribe.py samples\speaker\speaker_fujian.mp3 --model faster-whisper-small --srt
    exit /b 0
)

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    echo [WARN] .venv not found, falling back to "python" from PATH.
    echo        If you get "No module named 'av'", the wrong interpreter was used.
    echo        Create the environment first:
    echo          uv venv .venv --python 3.12 --seed
    echo          .venv\Scripts\python.exe -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
    set "PY=python"
)

"%PY%" %*
endlocal
