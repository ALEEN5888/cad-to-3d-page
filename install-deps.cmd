@echo off
chcp 65001 >nul
title Install dependencies for CAD -> 3D web page
setlocal
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

set "PYEXE="
set "PYOPT="

echo.
echo   Step 1/2 : Python packages (cascadio, trimesh)
echo.

rem If some Python already has them, upgrade that one.
for /f "delims=" %%P in ('where python 2^>nul') do (
  if not defined PYEXE (
    "%%P" -c "import cascadio,trimesh" >nul 2>nul
    if not errorlevel 1 set "PYEXE=%%P"
  )
)

if defined PYEXE (
  echo   Found an existing install, upgrading:
  echo     "%PYEXE%"
  echo.
  "%PYEXE%" -m pip install --upgrade cascadio trimesh
  if errorlevel 1 goto pipfail
  goto gltfpack
)

rem Otherwise install into the newest 3.x the py launcher knows about.
for %%V in (3.12 3.13 3.11 3.10 3.9) do (
  if not defined PYEXE (
    py -%%V -c "print(1)" >nul 2>nul
    if not errorlevel 1 (
      set "PYEXE=py"
      set "PYOPT=-%%V"
    )
  )
)

if not defined PYEXE (
  where python >nul 2>nul
  if not errorlevel 1 set "PYEXE=python"
)

if not defined PYEXE goto nopython

echo   Installing into: "%PYEXE%" %PYOPT%
echo.
"%PYEXE%" %PYOPT% -m pip install --upgrade cascadio trimesh
if errorlevel 1 goto pipfail

:gltfpack
echo.
echo   Step 2/2 : gltfpack (optional, makes the output about 2x smaller)
echo.
where gltfpack >nul 2>nul
if not errorlevel 1 (
  echo   gltfpack already installed.
  goto done
)
where npm >nul 2>nul
if errorlevel 1 (
  echo   npm not found - skipping. That is fine, output is just larger.
  goto done
)
echo   Installing gltfpack via npm ...
call npm install -g gltfpack

:done
echo.
echo   All set. Now drag a CAD file onto the converter cmd icon.
echo.
pause
exit /b 0

:pipfail
echo.
echo   [ERROR] pip failed. Check the network, or run this by hand:
echo     "%PYEXE%" %PYOPT% -m pip install cascadio trimesh
echo.
pause
exit /b 1

:nopython
echo.
echo   [ERROR] No Python found at all. Install Python 3.9+ first
echo           (from python.org), then run this file again.
echo.
pause
exit /b 1
