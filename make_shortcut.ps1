# Erzeugt eine Taskleisten-taugliche Verknuepfung "Open-Whisper.lnk" im Projektordner.
# Die Verknuepfung startet start_diktat.bat minimiert (kein aufpoppendes CMD-Fenster)
# und traegt das Mikrofon-Icon (open-whisper.ico) ein.
#
# Aufruf (im Projektordner):
#   powershell -ExecutionPolicy Bypass -File make_shortcut.ps1
#
# Danach die erzeugte Open-Whisper.lnk per Drag & Drop auf die Taskleiste ziehen.

$dir = $PSScriptRoot
$bat = Join-Path $dir "start_diktat.bat"
$ico = Join-Path $dir "open-whisper.ico"
$lnk = Join-Path $dir "Open-Whisper.lnk"

if (-not (Test-Path $bat)) { Write-Error "start_diktat.bat nicht gefunden neben diesem Skript."; exit 1 }

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = "$env:windir\System32\cmd.exe"
$sc.Arguments = '/c "' + $bat + '"'
$sc.WorkingDirectory = $dir
$sc.WindowStyle = 7          # 7 = minimiert
$sc.Description = "Open-Whisper starten"
if (Test-Path $ico) { $sc.IconLocation = "$ico,0" }
$sc.Save()

Write-Host "Verknuepfung erstellt: $lnk"
Write-Host "Zum Anheften per Drag & Drop auf die Taskleiste ziehen."
