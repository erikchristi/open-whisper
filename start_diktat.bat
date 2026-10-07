@echo off
rem Startet das lokale Diktat ohne Konsolenfenster (Logs in app.log)
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
    rem Verknuepfungen starten diese Datei minimiert - deshalb ein sichtbares Meldungsfenster
    powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [void][System.Windows.MessageBox]::Show('Die App ist noch nicht eingerichtet. Bitte zuerst setup.bat im Projektordner ausfuehren.', 'Open-Whisper')"
    exit /b 1
)
start "Lokales Diktat" "%~dp0.venv\Scripts\pythonw.exe" app.py
