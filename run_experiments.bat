@echo off
setlocal
cd /d "%~dp0"
REM Evaluation suite: 3 models x 2 samples x 3 prompt variants.
REM Writes eval_report.md (latest) + one timestamped file per run in reports\.

echo ################################################################
echo #  faster-whisper evaluation suite
echo #  tiny / small / medium   x   no-prompt / zh / tech
echo ################################################################

echo.
echo [1/6] baseline  zh_tts_1   (no prompt)
call run.bat eval_zh.py samples\zh_tts_1.wav samples\zh_tts_1.txt --models faster-whisper-tiny faster-whisper-small faster-whisper-medium

echo.
echo [2/6] baseline  zh_tts_2   (no prompt)
call run.bat eval_zh.py samples\zh_tts_2.wav samples\zh_tts_2.txt --models faster-whisper-tiny faster-whisper-small faster-whisper-medium

echo.
echo [3/6] zh guide  zh_tts_1   (--prompt-name zh)
call run.bat eval_zh.py samples\zh_tts_1.wav samples\zh_tts_1.txt --prompt-name zh --models faster-whisper-tiny faster-whisper-small faster-whisper-medium

echo.
echo [4/6] zh guide  zh_tts_2   (--prompt-name zh)
call run.bat eval_zh.py samples\zh_tts_2.wav samples\zh_tts_2.txt --prompt-name zh --models faster-whisper-tiny faster-whisper-small faster-whisper-medium

echo.
echo [5/6] tech vocab zh_tts_1  (--prompt-name tech)
call run.bat eval_zh.py samples\zh_tts_1.wav samples\zh_tts_1.txt --prompt-name tech --models faster-whisper-tiny faster-whisper-small faster-whisper-medium

echo.
echo [6/6] tech vocab zh_tts_2  (--prompt-name tech)
call run.bat eval_zh.py samples\zh_tts_2.wav samples\zh_tts_2.txt --prompt-name tech --models faster-whisper-tiny faster-whisper-small faster-whisper-medium

echo.
echo ================================================================
echo  Done. See eval_report.md and the reports folder.
echo ================================================================
endlocal
