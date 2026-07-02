"""Wispr-Flow-artiges Overlay: abgerundete dunkle Pille unten mittig mit
Live-Waveform (Aufnahme), Punkte-Animation (Transkription) und sanftem Fade.

Die abgerundete Form entsteht über einen Transparenz-Farb-Key: das Fenster ist
rechteckig, aber alles in TRANSPARENT_KEY wird von Windows durchsichtig gerendert.
"""

import collections
import time
import tkinter as tk
import tkinter.font as tkfont

TRANSPARENT_KEY = "#010203"
PILL_BG = "#141517"
PILL_OUTLINE = "#2c2d31"
TEXT_FG = "#f2f2f4"
MUTED_FG = "#9a9ba0"
WAVE_FG = "#e9e9ec"
DOT_RECORD = "#ff4d4f"
DOT_RECORD_DIM = "#8a3235"
COLORS = {"ok": "#4cc38a", "error": "#ff6369", "info": "#9a9ba0", "busy": "#f5a623"}

HEIGHT = 44
RADIUS = 21
MARGIN_BOTTOM = 70
N_BARS = 24
BAR_W = 3
BAR_GAP = 2
MAX_ALPHA = 0.97


class Overlay:
    """Muss aus dem Tk-Hauptthread bedient werden (der Controller stellt das sicher)."""

    def __init__(self, root):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.0)
        self.win.configure(bg=TRANSPARENT_KEY)
        try:
            self.win.attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass  # ohne Farb-Key wird die Pille eckig, bleibt aber nutzbar
        self.canvas = tk.Canvas(self.win, width=200, height=HEIGHT,
                                bg=TRANSPARENT_KEY, highlightthickness=0)
        self.canvas.pack()
        self.font = tkfont.Font(family="Segoe UI", size=10)
        self.font_small = tkfont.Font(family="Segoe UI", size=9)
        self._levels = collections.deque([0.0] * N_BARS, maxlen=N_BARS)
        self._mode = None  # "record" | "busy" | "message"
        self._visible = False
        self._cur_w = None
        self._alpha_job = None
        self._anim_job = None
        self._hide_job = None
        self._rec_started = 0.0
        self._busy_text = ""
        self._dots = 0
        self.win.withdraw()

    # ---- öffentliche API ----

    def show_recording(self):
        self._switch_mode("record")
        self._levels.extend([0.0] * N_BARS)
        self._rec_started = time.monotonic()
        self._draw_record()
        self._fade_to(MAX_ALPHA)

    def set_level(self, rms):
        """Waveform füttern (RMS 0..1); logarithmisch angehoben, mit Abklingen."""
        if self._mode != "record":
            return
        target = min(1.0, (rms * 12.0) ** 0.6) if rms > 0 else 0.0
        self._levels.append(max(target, self._levels[-1] * 0.6))
        self._draw_record()

    def show_busy(self, text="Transkribiere"):
        self._switch_mode("busy")
        self._busy_text = text.rstrip(" .…")
        self._dots = 0
        self._draw_busy()
        self._fade_to(MAX_ALPHA)
        self._animate_busy()

    def show(self, text, kind="info"):
        """Dauerhafte Textmeldung (bis hide/flash)."""
        self._switch_mode("message")
        self._draw_message(text, kind)
        self._fade_to(MAX_ALPHA)

    def flash(self, text, kind="ok", ms=1500):
        self.show(text, kind)
        self._hide_job = self.win.after(ms, self.hide)

    def hide(self):
        self._hide_job = None
        self._mode = None
        self._cancel_anim()
        self._fade_to(0.0, then_withdraw=True)

    # ---- Zeichnen ----

    def _switch_mode(self, mode):
        if self._hide_job:
            self.win.after_cancel(self._hide_job)
            self._hide_job = None
        self._cancel_anim()
        self._mode = mode

    def _resize(self, w):
        w = int(w)
        if self._cur_w != w:
            self._cur_w = w
            self.canvas.config(width=w, height=HEIGHT)
            sw = self.win.winfo_screenwidth()
            sh = self.win.winfo_screenheight()
            self.win.geometry(f"{w}x{HEIGHT}+{(sw - w) // 2}+{sh - HEIGHT - MARGIN_BOTTOM}")

    def _pill(self, w):
        r = RADIUS
        x1, y1, x2, y2 = 1, 1, w - 1, HEIGHT - 1
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.canvas.create_polygon(pts, smooth=True, fill=PILL_BG, outline=PILL_OUTLINE)

    def _draw_record(self):
        elapsed = time.monotonic() - self._rec_started
        timer = f"{int(elapsed) // 60}:{int(elapsed) % 60:02d}"
        wave_w = N_BARS * (BAR_W + BAR_GAP) - BAR_GAP
        timer_w = self.font_small.measure("0:00")
        w = 20 + 8 + 14 + wave_w + 14 + timer_w + 20
        self._resize(w)
        c = self.canvas
        c.delete("all")
        self._pill(w)
        mid = HEIGHT / 2
        # pulsierender Aufnahme-Punkt
        dot = DOT_RECORD if int(elapsed * 2) % 2 == 0 else DOT_RECORD_DIM
        c.create_oval(20, mid - 4, 28, mid + 4, fill=dot, width=0)
        x = 20 + 8 + 14
        for lv in self._levels:
            h = max(3.0, lv * 26.0)
            c.create_rectangle(x, mid - h / 2, x + BAR_W, mid + h / 2, fill=WAVE_FG, width=0)
            x += BAR_W + BAR_GAP
        c.create_text(w - 20, mid, text=timer, anchor="e", fill=MUTED_FG, font=self.font_small)

    def _draw_busy(self):
        text = self._busy_text
        w = 20 + 10 + 10 + self.font.measure(text) + 4 + self.font.measure("···") + 20
        self._resize(w)
        c = self.canvas
        c.delete("all")
        self._pill(w)
        mid = HEIGHT / 2
        c.create_oval(20, mid - 4, 28, mid + 4, fill=COLORS["busy"], width=0)
        c.create_text(20 + 10 + 10, mid, text=text, anchor="w", fill=TEXT_FG, font=self.font)
        dots = "·" * self._dots
        x_dots = 20 + 10 + 10 + self.font.measure(text) + 4
        c.create_text(x_dots, mid, text=dots, anchor="w", fill=MUTED_FG, font=self.font)

    def _animate_busy(self):
        if self._mode != "busy":
            return
        self._dots = (self._dots + 1) % 4
        self._draw_busy()
        self._anim_job = self.win.after(280, self._animate_busy)

    def _draw_message(self, text, kind):
        glyph = "✓" if kind == "ok" else "●"
        glyph_w = self.font.measure(glyph)
        w = 20 + glyph_w + 10 + self.font.measure(text) + 20
        self._resize(w)
        c = self.canvas
        c.delete("all")
        self._pill(w)
        mid = HEIGHT / 2
        c.create_text(20, mid, text=glyph, anchor="w",
                      fill=COLORS.get(kind, COLORS["info"]), font=self.font)
        c.create_text(20 + glyph_w + 10, mid, text=text, anchor="w", fill=TEXT_FG, font=self.font)

    # ---- Animation ----

    def _cancel_anim(self):
        if self._anim_job:
            self.win.after_cancel(self._anim_job)
            self._anim_job = None

    def _fade_to(self, target, then_withdraw=False):
        if self._alpha_job:
            self.win.after_cancel(self._alpha_job)
            self._alpha_job = None
        if target > 0 and not self._visible:
            self.win.deiconify()
            self.win.lift()
            self._visible = True

        def step():
            self._alpha_job = None
            cur = float(self.win.attributes("-alpha"))
            delta = target - cur
            if abs(delta) < 0.13:
                self.win.attributes("-alpha", target)
                if then_withdraw and target == 0.0:
                    self.win.withdraw()
                    self._visible = False
                return
            self.win.attributes("-alpha", cur + (0.13 if delta > 0 else -0.13))
            self._alpha_job = self.win.after(16, step)

        step()
