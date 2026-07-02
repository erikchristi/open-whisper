"""System-Tray-Icon (Mikrofon-Symbol) mit Statusanzeige und Beenden-Menü."""

import pystray
from PIL import Image, ImageDraw

STATE_COLORS = {
    "loading": "#fb8c00",
    "idle": "#43a047",
    "recording": "#e53935",
    "error": "#757575",
}


def _make_image(color):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # stilisiertes Mikrofon: Kapsel, Bügel, Fuß
    d.rounded_rectangle([24, 6, 40, 36], radius=8, fill=color)
    d.arc([16, 18, 48, 48], start=0, end=180, fill=color, width=5)
    d.line([32, 48, 32, 56], fill=color, width=5)
    d.line([22, 58, 42, 58], fill=color, width=5)
    return img


class Tray:
    def __init__(self, on_quit, get_status, list_mics, get_mic, set_mic):
        self._on_quit = on_quit
        self._get_status = get_status
        self._list_mics = list_mics
        self._get_mic = get_mic
        self._set_mic = set_mic
        self.icon = pystray.Icon(
            "lokal_diktat",
            icon=_make_image(STATE_COLORS["loading"]),
            title="Lokales Diktat",
            menu=pystray.Menu(
                pystray.MenuItem(lambda item: self._get_status(), None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Mikrofon", pystray.Menu(self._mic_items)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Beenden", self._quit),
            ),
        )

    def _mic_items(self):
        """Untermenü-Einträge; wird von pystray bei jedem Öffnen neu abgefragt."""
        yield pystray.MenuItem(
            "Automatisch (empfohlen)",
            lambda icon, item: self._set_mic(None),
            checked=lambda item: self._get_mic() is None,
            radio=True,
        )
        for name in self._list_mics():
            yield pystray.MenuItem(
                name,
                (lambda n: lambda icon, item: self._set_mic(n))(name),
                checked=(lambda n: lambda item: self._get_mic() == n)(name),
                radio=True,
            )

    def start(self):
        self.icon.run_detached()

    def set_state(self, state):
        self.icon.icon = _make_image(STATE_COLORS.get(state, STATE_COLORS["idle"]))
        self.icon.title = f"Lokales Diktat – {self._get_status()}"

    def stop(self):
        self.icon.stop()

    def _quit(self, icon, item):
        self._on_quit()
