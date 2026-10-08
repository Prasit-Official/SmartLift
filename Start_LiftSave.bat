@echo off
setlocal
cd /d "%~dp0"
if defined LIFTSAVE_PYTHON goto custom
if defined VIRTUAL_ENV if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
  "%VIRTUAL_ENV%\Scripts\python.exe" launcher.py
  goto done
)
for %%E in (.venv .venv312 .venv_cpu .venv311 venv) do (
  if exist "%%E\Scripts\python.exe" (
    "%%E\Scripts\python.exe" launcher.py
    goto done
  )
)
echo No project Python environment found.
echo Put this file beside app.py in the project that already runs.
echo Or set LIFTSAVE_PYTHON to your working python.exe path.
pause
exit /b 1
:custom
"%LIFTSAVE_PYTHON%" launcher.py
:done
if errorlevel 1 pause
endlocal
