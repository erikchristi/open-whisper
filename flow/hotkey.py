"""Globale Hotkeys: Push-to-talk (Taste halten) und Toggle (Ein/Aus)."""

import logging

import keyboard

log = logging.getLogger(__name__)


class HotkeyManager:
    """Meldet Hotkey-Ereignisse an den Controller; den Zustand hält der Controller.

    Die Callbacks laufen im Thread der keyboard-Bibliothek – der Controller
    reicht sie per Queue in den Tk-Hauptthread weiter.
    """

    def __init__(self, cfg, on_ptt_down, on_ptt_up, on_toggle):
        self.cfg = cfg
        self.on_ptt_down = on_ptt_down
        self.on_ptt_up = on_ptt_up
        self.on_toggle = on_toggle
        self._ptt_held = False

    def register(self):
        ptt = self.cfg["hotkey_ptt"]
        toggle = self.cfg["hotkey_toggle"]
        if ptt:
            keyboard.on_press_key(ptt, self._ptt_press, suppress=True)
            keyboard.on_release_key(ptt, self._ptt_release, suppress=True)
            log.info("Push-to-talk: '%s' halten", ptt)
        if toggle:
            keyboard.add_hotkey(toggle, self.on_toggle, suppress=True)
            log.info("Toggle: '%s'", toggle)

    def _ptt_press(self, _event):
        if self._ptt_held:  # Auto-Repeat beim Halten ignorieren
            return
        self._ptt_held = True
        self.on_ptt_down()

    def _ptt_release(self, _event):
        self._ptt_held = False
        self.on_ptt_up()

    @staticmethod
    def unregister_all():
        keyboard.unhook_all()
