@echo off
chcp 65001 >nul
title CAD -> single-file 3D web page (flip 180)
setlocal enabledelayedexpansion
set "HERE=%~dp0"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

rem Use the first Python that really has cascadio + trimesh.
set "PYEXE="
set "PYOPT="
for /f "delims=" %%P in ('where python 2^>nul') do (
  if not defined PYEXE (
    "%%P" -c "import cascadio,trimesh" >nul 2>nul
    if not errorlevel 1 set "PYEXE=%%P"
  )
)
if not defined PYEXE (
  for %%V in (3.12 3.11 3.10 3.9) do (
    if not defined PYEXE (
      py -%%V -c "import cascadio,trimesh" >nul 2>nul
      if not errorlevel 1 (
        set "PYEXE=py"
        set "PYOPT=-%%V"
      )
    )
  )
)
if not defined PYEXE goto nodeps
echo   Python: "%PYEXE%" %PYOPT%

if "%~1"=="" goto pick

:loop
if "%~1"=="" goto done
"%PYEXE%" %PYOPT% "%HERE%make_viewer.py" "%~1" --flip-axis x --open
shift
goto loop

:pick
echo.
echo   Choose one or more CAD files in the dialog that opens...
echo.
set "PICKED=0"
for /f "usebackq delims=" %%F in (`"%PYEXE%" %PYOPT% "%HERE%pick_files.py"`) do (
  set "PICKED=1"
  "%PYEXE%" %PYOPT% "%HERE%make_viewer.py" "%%F" --flip-axis x --open
)
if "%PICKED%"=="0" goto usage

:done
echo.
pause
exit /b 0

:usage
echo.
echo   No file selected.
echo.
echo   Use this one when the converted model comes out upside down.
echo   Double-click this file and pick a model, or drag a model onto its icon.
echo.
pause
exit /b 0

:nodeps
echo.
echo   [ERROR] No Python with the required packages (cascadio, trimesh) was found.
echo.
echo   Fix it in one step: run install-deps.cmd in this folder.
echo.
pause
exit /b 1
