@echo off
rem Einrichtung: legt .venv an und installiert alle Abhaengigkeiten dort (nicht im System-Python).
rem Erkennt eine NVIDIA-GPU automatisch. "setup.bat cpu" erzwingt die CPU-Variante.
rem Erneut ausfuehren = Update/Reparatur der bestehenden .venv.
setlocal
cd /d "%~dp0"

rem --- Python finden ---------------------------------------------------------
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY (
    echo FEHLER: Python wurde nicht gefunden.
    echo Installiere Python 3.10 oder neuer von https://www.python.org/downloads/
    echo und setze dabei das Haekchen bei "Add Python to PATH".
    goto :fail
)
%PY% -c "import sys; sys.exit(sys.version_info < (3, 10))"
if errorlevel 1 (
    echo FEHLER: Python 3.10 oder neuer wird benoetigt.
    %PY% --version
    goto :fail
)

rem --- laeuft die App noch? Dann sind ihre DLLs gesperrt und pip scheitert ---
powershell -NoProfile -Command "if (Get-Process python,pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '%CD%\.venv\*' }) { exit 1 }"
if errorlevel 1 (
    echo FEHLER: Die App laeuft noch. Beende sie ueber das Tray-Icon ^(Beenden^)
    echo und starte setup.bat danach erneut.
    goto :fail
)

rem --- .venv anlegen (nur wenn noch keine existiert) -------------------------
set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo Lege virtuelle Umgebung .venv an ...
    %PY% -m venv .venv || goto :fail_msg
)

echo Installiere Abhaengigkeiten ...
"%VPY%" -m pip install --upgrade pip || goto :fail_msg
"%VPY%" -m pip install -r requirements.txt || goto :fail_msg

rem --- CPU oder GPU ----------------------------------------------------------
rem onnxruntime und onnxruntime-gpu teilen sich das Python-Modul "onnxruntime"; es darf
rem immer nur eine Variante installiert sein. Nach dem Deinstallieren der einen fehlen
rem gemeinsame Dateien, deshalb wird die andere mit --force-reinstall neu geschrieben.
if /i "%~1"=="cpu" goto :cpu
nvidia-smi -L >nul 2>&1 || goto :cpu

echo NVIDIA-GPU erkannt - installiere GPU-Variante (CUDA 13 + cuDNN 9, einige GB) ...
"%VPY%" -m pip uninstall -y onnxruntime >nul 2>&1
"%VPY%" -m pip install "onnxruntime-gpu[cuda,cudnn]" || goto :fail_msg
"%VPY%" -m pip install --force-reinstall --no-deps onnxruntime-gpu || goto :fail_msg
goto :done

:cpu
echo CPU-Modus - nutze onnxruntime ohne GPU.
"%VPY%" -m pip uninstall -y onnxruntime-gpu >nul 2>&1
"%VPY%" -m pip install --force-reinstall --no-deps onnxruntime || goto :fail_msg

:done
echo.
echo Fertig. Starte die App mit start_diktat.bat
echo (beim ersten Start wird das Sprachmodell heruntergeladen).
if not defined SETUP_NOPAUSE pause
exit /b 0

:fail_msg
echo.
echo FEHLER bei der Installation - siehe Meldungen oben.
:fail
if not defined SETUP_NOPAUSE pause
exit /b 1
