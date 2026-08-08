@echo off
chcp 65001 >nul
REM Submission structure/format verifier (Windows local, no heavy model needed)
REM Usage:
REM   verify.bat                               check current repo
REM   verify.bat dist\Termproject_name         check staging folder
REM   verify.bat dist\Termproject_name.zip     check zip directly
setlocal
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=."
echo === Submission structure / format check (no model load) ===
py scripts\verify_submission.py "%TARGET%"
echo.
pause
