@echo off
chcp 65001 >nul
title backup to GitHub
cd /d "%~dp0"

git remote get-url origin >nul 2>nul
if errorlevel 1 goto noremote

echo   Committing changes...
git add -A
git commit -m "backup %date% %time%"

echo.
echo   Pushing to GitHub...
git push
if errorlevel 1 goto pushfailed

echo.
echo   Backup finished.
pause
exit /b 0

:pushfailed
echo.
echo   Push failed. Check your network, or sign in when the GitHub
echo   window appears, then run this file again.
pause
exit /b 1

:noremote
echo.
echo   No GitHub remote is configured for this folder yet.
echo   Create the repository on github.com first, then run the
echo   "git remote add origin ..." command once.
pause
exit /b 1
