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
        self._vu = tk.Canvas(self.win, width=64, height=16, bg=BG, highlightthickness=0)
        self._vu_display = 0.0
        self._hide_job = None
        self.win.withdraw()

    def show(self, text, kind="info"):
        if self._hide_job:
            self.win.after_cancel(self._hide_job)
            self._hide_job = None
        self._dot.configure(fg=COLORS.get(kind, COLORS["info"]))
        self._label.configure(text=text)
        if kind == "record":
            self._vu_display = 0.0
            self._draw_vu()
            self._vu.pack(side="left", padx=(0, 14), pady=6, before=self._label)
        else:
            self._vu.pack_forget()
        self.win.update_idletasks()
        w = self.win.winfo_reqwidth()
        h = self.win.winfo_reqheight()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{sh - h - 80}")
        self.win.deiconify()
        self.win.lift()

    def set_level(self, rms):
        """VU-Meter füttern (RMS 0..1); logarithmisch angehoben, mit Abklingen."""
        target = min(1.0, (rms * 12.0) ** 0.6) if rms > 0 else 0.0
        self._vu_display = max(target, self._vu_display * 0.75)
        self._draw_vu()

    def _draw_vu(self):
        c = self._vu
        c.delete("all")
        n = 10
        lit = round(self._vu_display * n)
        for i in range(n):
            if i >= lit:
                color = "#3a3a3a"
            elif i >= 8:
                color = "#e53935"
            elif i >= 6:
                color = "#fb8c00"
            else:
                color = "#43a047"
            x = 2 + i * 6
            c.create_rectangle(x, 4, x + 4, 12, fill=color, width=0)

    def flash(self, text, kind="ok", ms=1500):
        self.show(text, kind)
        self._hide_job = self.win.after(ms, self.hide)

    def hide(self):
        self._hide_job = None
        self.win.withdraw()
