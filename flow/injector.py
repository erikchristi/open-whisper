"""Text an der Cursorposition der aktiven Anwendung einfügen."""

import logging
import time

import keyboard
import pyperclip

log = logging.getLogger(__name__)


def paste_text(text, method="clipboard"):
    """Fügt Text in die aktive App ein.

    "clipboard": Zwischenablage sichern → Text kopieren → Strg+V → Zwischenablage
    wiederherstellen. Schnell und robust auch bei langen Texten.
    "type": Zeichenweise tippen – langsamer, aber lässt die Zwischenablage unberührt.
    """
    if not text:
        return
    if method == "type":
        keyboard.write(text, delay=0.005)
        log.info("Text getippt (%d Zeichen)", len(text))
        return

    old_clip = None
    try:
        old_clip = pyperclip.paste()
    except Exception:
        pass
    try:
        pyperclip.copy(text)
        time.sleep(0.05)
        keyboard.send("ctrl+v")
        # Ziel-App braucht einen Moment zum Einfügen, bevor das Clipboard zurückgesetzt wird
        time.sleep(0.3)
    finally:
        if old_clip:
            try:
                pyperclip.copy(old_clip)
            except Exception:
                pass
    log.info("Text eingefügt (%d Zeichen)", len(text))
