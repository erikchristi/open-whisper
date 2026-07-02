"""Kleiner rahmenloser Always-on-top-Statusindikator, unten mittig am Bildschirm."""

import tkinter as tk

COLORS = {
    "record": "#e53935",
    "busy": "#fb8c00",
    "ok": "#43a047",
    "error": "#e53935",
    "info": "#90a4ae",
}

BG = "#1e1e1e"
FG = "#f5f5f5"


class Overlay:
    """Muss aus dem Tk-Hauptthread bedient werden (der Controller stellt das sicher)."""

    def __init__(self, root):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.92)
        self.win.configure(bg=BG)
        self._dot = tk.Label(self.win, text="●", bg=BG, fg=COLORS["info"], font=("Segoe UI", 12))
        self._dot.pack(side="left", padx=(14, 6), pady=6)
        self._label = tk.Label(self.win, text="", bg=BG, fg=FG, font=("Segoe UI", 11))
        self._label.pack(side="left", padx=(0, 14), pady=6)
        self._hide_job = None
        self.win.withdraw()

    def show(self, text, kind="info"):
        if self._hide_job:
            self.win.after_cancel(self._hide_job)
            self._hide_job = None
        self._dot.configure(fg=COLORS.get(kind, COLORS["info"]))
        self._label.configure(text=text)
        self.win.update_idletasks()
        w = self.win.winfo_reqwidth()
        h = self.win.winfo_reqheight()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{sh - h - 80}")
        self.win.deiconify()
        self.win.lift()

    def flash(self, text, kind="ok", ms=1500):
        self.show(text, kind)
        self._hide_job = self.win.after(ms, self.hide)

    def hide(self):
        self._hide_job = None
        self.win.withdraw()
