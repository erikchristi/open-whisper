"""Lokales Diktat – Wispr-Flow-artige Diktier-App, komplett offline.

F8 halten (Push-to-talk) oder F9 drücken (Toggle): Sprache aufnehmen, lokal mit
Whisper transkribieren, Text an der Cursorposition der aktiven App einfügen.
"""

import logging
import queue
import socket
import threading
import tkinter as tk
from pathlib import Path

from flow import hard_exit
from flow.config import load_config
from flow.hotkey import HotkeyManager
from flow.injector import paste_text
from flow.overlay import Overlay
from flow.recorder import Recorder
from flow.transcriber import Transcriber
from flow.tray import Tray

log = logging.getLogger(__name__)

LOG_PATH = Path(__file__).resolve().parent / "app.log"
MIN_SECONDS = 0.3
SINGLE_INSTANCE_PORT = 48653


class App:
    def __init__(self):
        self.cfg = load_config()
        self.root = tk.Tk()
        self.root.withdraw()
        self.ui_queue = queue.Queue()
        self.overlay = Overlay(self.root)

        self.state = "idle"  # idle | recording | transcribing
        self.record_source = None  # "ptt" | "toggle"
        self.status_text = "Modell lädt …"

        self.recorder = Recorder(
            sample_rate=self.cfg["sample_rate"],
            input_device=self.cfg["input_device"],
            max_seconds=self.cfg["max_seconds"],
            pre_roll_seconds=self.cfg["pre_roll_seconds"],
            on_limit=lambda: self.ui(self._stop_and_transcribe),
        )
        self.transcriber = Transcriber(
            self.cfg,
            on_status=lambda text: self.ui(lambda: self._set_model_status(text)),
        )
        self.hotkeys = HotkeyManager(
            self.cfg,
            on_ptt_down=lambda: self.ui(self._ptt_down),
            on_ptt_up=lambda: self.ui(self._ptt_up),
            on_toggle=lambda: self.ui(self._toggle),
        )
        self.tray = Tray(on_quit=lambda: self.ui(self.quit), get_status=lambda: self.status_text)

    # ---- Threading: alle Zustandsänderungen laufen über die Queue im Tk-Hauptthread ----

    def ui(self, fn):
        self.ui_queue.put(fn)

    def _poll_queue(self):
        try:
            while True:
                fn = self.ui_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    log.exception("Fehler im UI-Callback")
        except queue.Empty:
            pass
        self.root.after(30, self._poll_queue)

    # ---- Zustandsmaschine ----

    def _ptt_down(self):
        if self.state == "transcribing":
            self.overlay.flash("Noch beschäftigt – gleich nochmal drücken", "busy", 1200)
            return
        if self.state != "idle":
            return
        self.record_source = "ptt"
        self._start_recording()

    def _ptt_up(self):
        if self.state == "recording" and self.record_source == "ptt":
            self._stop_and_transcribe()

    def _toggle(self):
        if self.state == "recording":
            self._stop_and_transcribe()
        elif self.state == "transcribing":
            self.overlay.flash("Noch beschäftigt – gleich nochmal drücken", "busy", 1200)
        elif self.state == "idle":
            self.record_source = "toggle"
            self._start_recording()

    def _start_recording(self):
        try:
            self.recorder.start()
        except Exception as exc:
            log.exception("Mikrofon-Fehler")
            self.overlay.flash(f"Mikrofon-Fehler: {exc}", "error", 3500)
            return
        self.state = "recording"
        self.tray.set_state("recording")
        hint = "loslassen zum Stoppen" if self.record_source == "ptt" else f"{self.cfg['hotkey_toggle'].upper()} zum Stoppen"
        self.overlay.show(f"Aufnahme … ({hint})", "record")

    def _stop_and_transcribe(self):
        if self.state != "recording":
            return
        audio = self.recorder.stop()
        self.tray.set_state("idle")
        duration = len(audio) / self.cfg["sample_rate"]
        if duration < MIN_SECONDS:
            self.state = "idle"
            self.overlay.flash("Zu kurz – nichts aufgenommen", "info", 1200)
            return
        self.state = "transcribing"
        if self.transcriber.ready.is_set():
            self.overlay.show("Transkribiere …", "busy")
        else:
            self.overlay.show("Modell lädt noch – Transkription folgt …", "busy")
        threading.Thread(target=self._worker, args=(audio,), daemon=True).start()

    def _worker(self, audio):
        try:
            text = self.transcriber.transcribe(audio)
            if text:
                paste_text(text, self.cfg["paste_method"])
        except Exception as exc:
            log.exception("Transkription/Einfügen fehlgeschlagen")
            self.ui(lambda: self._finish(error=str(exc)))
            return
        self.ui(lambda: self._finish(text=text))

    def _finish(self, text=None, error=None):
        self.state = "idle"
        if error:
            self.overlay.flash(f"Fehler: {error}", "error", 3500)
        elif text:
            self.overlay.flash("✓ Eingefügt", "ok", 1000)
        else:
            self.overlay.flash("Nichts erkannt", "info", 1500)

    def _set_model_status(self, text):
        self.status_text = text
        if text.startswith("Bereit"):
            self.tray.set_state("idle")
            self.overlay.flash(
                f"{text} – {self.cfg['hotkey_ptt'].upper()} halten oder {self.cfg['hotkey_toggle'].upper()} drücken",
                "ok",
                3000,
            )
        elif text.startswith("Fehler"):
            self.tray.set_state("error")
            self.overlay.flash(f"{text} – Details in app.log", "error", 5000)
        else:
            self.tray.set_state("loading")

    # ---- Lebenszyklus ----

    def run(self):
        self.hotkeys.register()
        self.tray.start()
        self.transcriber.load_async()
        try:
            self.recorder.open()
            self.overlay.flash("Lokales Diktat startet – Modell lädt …", "info", 2500)
        except Exception as exc:
            log.exception("Mikrofon-Stream konnte nicht geöffnet werden")
            self.overlay.flash(f"Mikrofon-Fehler: {exc}", "error", 4000)
        self._poll_queue()
        self.root.mainloop()

    def quit(self):
        log.info("Beende App")
        try:
            self.recorder.close()
        except Exception:
            pass
        try:
            HotkeyManager.unregister_all()
        except Exception:
            pass
        try:
            self.tray.stop()
        except Exception:
            pass
        self.root.destroy()


def acquire_single_instance_lock():
    """Verhindert Doppelstart (zwei Instanzen würden doppelt einfügen)."""
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
    except OSError:
        return None
    return sock


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
    )


def main():
    setup_logging()
    lock = acquire_single_instance_lock()
    if lock is None:
        log.error("Lokales Diktat läuft bereits – zweite Instanz wird beendet.")
        return
    app = App()
    exit_code = 0
    try:
        app.run()
    except Exception:
        log.exception("Unerwarteter Fehler")
        exit_code = 1
    finally:
        lock.close()
    logging.shutdown()
    hard_exit(exit_code)


if __name__ == "__main__":
    main()
