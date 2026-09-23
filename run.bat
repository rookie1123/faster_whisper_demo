@echo off
REM 统一入口: 固定使用 faster-whisper 环境 (Python 3.12), 避免误用系统 Python 3.6
REM 不切换 chcp, 让 Python 用系统默认编码输出, 中文才不会乱码
set "PY=D:\miniconda\envs\faster-whisper\python.exe"
if not exist "%PY%" (
    echo [ERROR] Python not found: %PY%
    echo Please create it first: conda create -n faster-whisper python=3.12 -y
    exit /b 1
)
if "%~1"=="" (
    echo Usage: run.bat ^<script^> [args...]
    echo   run.bat eval_zh.py samples\zh_tts_1.wav samples\zh_tts_1.txt
    echo   run.bat transcribe.py samples\zh_tts_1.wav --model faster-whisper-small --srt
    echo   run.bat demo.py
    exit /b 0
)
"%PY%" %*
