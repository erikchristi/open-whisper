"""Desktop-/Startmenü-Verknüpfungen erzeugen (PowerShell/WScript.Shell).

Vorbild ist make_shortcut.ps1: die Verknüpfung startet start_diktat.bat minimiert
(kein aufpoppendes CMD-Fenster) und trägt das Mikrofon-Icon ein. Das Anheften an die
Taskleiste bleibt ein manueller Windows-Schritt (Microsoft sperrt die Automatisierung).
"""

import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent
BAT = PROJECT_DIR / "start_diktat.bat"
ICO = PROJECT_DIR / "open-whisper.ico"
LNK_NAME = "Open-Whisper.lnk"

CREATE_NO_WINDOW = 0x08000000  # kein Konsolenfenster für den PowerShell-Aufruf


def _create_lnk(dest_dir: Path) -> Path:
    """Legt Open-Whisper.lnk in dest_dir an und gibt den Pfad zurück."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    lnk = dest_dir / LNK_NAME
    icon_line = f'$sc.IconLocation = "{ICO},0";' if ICO.exists() else ""
    ps = (
        "$ws = New-Object -ComObject WScript.Shell;"
        f'$sc = $ws.CreateShortcut("{lnk}");'
        f'$sc.TargetPath = "$env:windir\\System32\\cmd.exe";'
        f'$sc.Arguments = \'/c "{BAT}"\';'
        f'$sc.WorkingDirectory = "{PROJECT_DIR}";'
        "$sc.WindowStyle = 7;"
        '$sc.Description = "Open-Whisper starten";'
        f"{icon_line}"
        "$sc.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        check=True,
        capture_output=True,
        creationflags=CREATE_NO_WINDOW,
    )
    return lnk


def create_desktop_shortcut() -> bool:
    """Verknüpfung auf dem Desktop anlegen. True bei Erfolg."""
    try:
        dest = Path(os.environ["USERPROFILE"]) / "Desktop"
        lnk = _create_lnk(dest)
        log.info("Desktop-Verknüpfung erstellt: %s", lnk)
        return True
    except Exception:
        log.exception("Desktop-Verknüpfung fehlgeschlagen")
        return False


def create_startmenu_shortcut() -> bool:
    """Verknüpfung im Startmenü (Programme) anlegen. True bei Erfolg."""
    try:
        dest = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        lnk = _create_lnk(dest)
        log.info("Startmenü-Verknüpfung erstellt: %s", lnk)
        return True
    except Exception:
        log.exception("Startmenü-Verknüpfung fehlgeschlagen")
        return False
