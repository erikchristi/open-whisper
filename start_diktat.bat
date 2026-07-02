@echo off
rem Startet das lokale Diktat ohne Konsolenfenster (Logs in app.log)
cd /d "%~dp0"
start "Lokales Diktat" pythonw app.py
