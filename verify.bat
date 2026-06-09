@echo off
chcp 65001 >nul
REM 제출물 구조/양식 즉시 검증 (윈도우 로컬, 무거운 모델 불필요)
REM 사용: verify.bat                          (현재 레포 검사)
REM       verify.bat dist\Termproject_장정원   (스테이징 폴더 검사)
REM       verify.bat dist\Termproject_장정원.zip (zip 직접 검사)
setlocal
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=."
echo === 제출물 구조/양식 검증 (모델 로딩 없이 즉시) ===
py scripts\verify_submission.py "%TARGET%"
echo.
pause
