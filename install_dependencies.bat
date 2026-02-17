@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM FakeTools Dependency Installer (Standalone Launcher)
REM
REM Searches for installed Maya versions (2023-2026) and launches
REM the dependency installer UI using the latest available mayapy.
REM ============================================================

set "MAYAPY="
set "SCRIPT_DIR=%~dp0"

REM Search for Maya versions from newest to oldest
for %%V in (2026 2025 2024 2023) do (
    set "CANDIDATE=C:\Program Files\Autodesk\Maya%%V\bin\mayapy.exe"
    if exist "!CANDIDATE!" (
        set "MAYAPY=!CANDIDATE!"
        echo Found Maya %%V
        goto :found
    )
)

echo ERROR: No Maya installation found (2023-2026).
echo Please install Autodesk Maya or run this tool from within Maya.
pause
exit /b 1

:found
echo Using: %MAYAPY%
echo.

REM Add scripts directory to PYTHONPATH so package imports work
set "PYTHONPATH=%SCRIPT_DIR%scripts;%PYTHONPATH%"

REM Launch the installer UI as a module via mayapy
"%MAYAPY%" -m faketools.tools.common.dependency_installer.ui

if errorlevel 1 (
    echo.
    echo An error occurred. Check the output above.
    pause
)
