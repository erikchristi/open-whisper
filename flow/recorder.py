"""Mikrofonaufnahme: dauerhaft offener Stream mit Pre-Roll-Ringpuffer.

Geräte werden mit ihrer nativen Abtastrate geöffnet (Resampling auf die Whisper-Rate
passiert in stop()), bevorzugt über WASAPI. Nach dem Öffnen prüft eine Liveness-Probe,
ob wirklich Daten fließen — auf manchen Systemen (z. B. MME bei erzwungenen 16 kHz)
bleibt ein Stream sonst „aktiv“, liefert aber nie einen Callback.
"""

import collections
import logging
import threading
import time

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

PROBE_TIMEOUT = 1.0  # s: Wartezeit auf den ersten Callback nach dem Öffnen
DEAD_AFTER = 1.5     # s: ohne Callback gilt ein "aktiver" Stream als tot


def list_input_devices():
    """Eindeutige Eingabegeräte-Namen, bevorzugt WASAPI — deckt sich mit den
    Windows-Soundeinstellungen und vermeidet die MME/DirectSound-Duplikate."""
    apis = sd.query_hostapis()
    wasapi, fallback = [], []
    for d in sd.query_devices():
        if d["max_input_channels"] <= 0:
            continue
        target = wasapi if "WASAPI" in apis[d["hostapi"]]["name"] else fallback
        if d["name"] not in target:
            target.append(d["name"])
    return wasapi or fallback


def resample(audio, src_rate, dst_rate):
    """Lineares Resampling — für Spracherkennung ausreichend."""
    if src_rate == dst_rate or len(audio) == 0:
        return audio.astype(np.float32, copy=False)
    n_dst = int(len(audio) * dst_rate / src_rate)
    x_src = np.linspace(0.0, 1.0, len(audio), endpoint=False)
    x_dst = np.linspace(0.0, 1.0, n_dst, endpoint=False)
    return np.interp(x_dst, x_src, audio).astype(np.float32)


class Recorder:
    """Hält den Input-Stream dauerhaft offen; start()/stop() kippen nur ein Sammel-Flag.

    Der Callback läuft permanent, füttert einen Ringpuffer von pre_roll_seconds Länge
    und misst den aktuellen Pegel (self.level, RMS) für das VU-Meter. on_limit wird
    (einmalig, aus dem Audio-Thread) gerufen, wenn max_seconds erreicht ist.
    """

    def __init__(self, sample_rate=16000, input_device=None, max_seconds=120,
                 pre_roll_seconds=0.4, on_limit=None):
        self.sample_rate = sample_rate          # Zielrate (Whisper: 16 kHz)
        self.capture_rate = sample_rate         # tatsächliche Geräterate, in open() gesetzt
        self.input_device = input_device
        self.max_seconds = max_seconds
        self.pre_roll_seconds = pre_roll_seconds
        self.on_limit = on_limit
        self.level = 0.0                        # RMS des letzten Callbacks (VU-Meter)
        self.device_label = "kein Gerät"
        self._configure_frames()
        self._stream = None
        self._pre_roll = collections.deque()
        self._pre_roll_held = 0
        self._chunks = []
        self._frames = 0
        self._collecting = False
        self._limit_fired = False
        self._last_data = 0.0                   # time.monotonic() des letzten Callbacks
        self._lock = threading.Lock()

    def _configure_frames(self):
        self.pre_roll_frames = int(self.pre_roll_seconds * self.capture_rate)
        self.max_frames = int(self.max_seconds * self.capture_rate)

    @property
    def is_recording(self):
        return self._collecting

    # ---- Stream-Verwaltung ----

    def _candidates(self):
        """Aufnahme-Konfigurationen in Prioritätsreihenfolge: (device, rate, channels, label).

        Immer native Rate und native Kanalzahl (max. 2) — WASAPI-Shared-Mode liefert
        z. B. oft nur Daten, wenn die Kanalzahl dem Mix-Format entspricht.
        """

        def native(device):
            info = sd.query_devices(device)
            return int(info["default_samplerate"]), min(2, info["max_input_channels"])

        cands = []
        if self.input_device is not None:
            try:
                idx = self._resolve_device(self.input_device)
                rate, ch = native(idx)
                cands.append((idx, rate, ch, "konfiguriertes Gerät"))
            except Exception as exc:
                log.warning("Konfiguriertes Mikrofon nicht nutzbar (%s) – nutze Automatik", exc)
        # WASAPI-Standardeingang zuerst — zuverlässigste Host-API auf modernem Windows
        for api in sd.query_hostapis():
            if "WASAPI" in api["name"] and api["default_input_device"] >= 0:
                idx = api["default_input_device"]
                rate, ch = native(idx)
                cands.append((idx, rate, ch, "WASAPI-Standard"))
        # Fallbacks: PortAudio-Default (meist MME) mit nativer, dann mit Zielrate
        default_in = sd.default.device[0]
        if isinstance(default_in, int) and default_in >= 0:
            rate, ch = native(default_in)
            cands.append((default_in, rate, ch, "System-Standard"))
            cands.append((default_in, self.sample_rate, ch, "System-Standard (Zielrate)"))
        return cands

    @staticmethod
    def _resolve_device(wanted):
        """Löst einen Gerätenamen zum Index auf, bevorzugt WASAPI; Indizes/None
        werden unverändert durchgereicht."""
        if not isinstance(wanted, str):
            return wanted
        apis = sd.query_hostapis()
        matches = [d for d in sd.query_devices()
                   if d["max_input_channels"] > 0 and wanted.lower() in d["name"].lower()]
        if not matches:
            raise ValueError(f"Mikrofon '{wanted}' nicht gefunden")
        for d in matches:
            if "WASAPI" in apis[d["hostapi"]]["name"]:
                return d["index"]
        return matches[0]["index"]

    def set_device(self, device):
        """Wechselt das Aufnahmegerät (None = automatisch) und öffnet den Stream neu."""
        self.input_device = device
        self.close()
        self.open()

    def open(self):
        """Öffnet den dauerhaften Input-Stream; probiert Kandidaten durch, bis einer
        nachweislich Daten liefert."""
        if self._stream is not None:
            return
        errors = []
        for device, rate, channels, label in self._candidates():
            with self._lock:
                self._pre_roll.clear()
                self._pre_roll_held = 0
                self.capture_rate = rate
                self._configure_frames()
            self._last_data = 0.0
            try:
                stream = sd.InputStream(
                    samplerate=rate, channels=channels, dtype="float32",
                    device=device, callback=self._callback,
                )
                stream.start()
            except Exception as exc:
                errors.append(f"{label}: {exc}")
                log.warning("Kandidat %s nicht nutzbar: %s", label, exc)
                continue
            # Liveness-Probe: fließen wirklich Daten?
            deadline = time.monotonic() + PROBE_TIMEOUT
            while time.monotonic() < deadline and self._last_data == 0.0:
                time.sleep(0.05)
            if self._last_data == 0.0:
                errors.append(f"{label}: Stream liefert keine Daten")
                log.warning("Kandidat %s: Stream aktiv, aber keine Daten – verworfen", label)
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
                continue
            self._stream = stream
            name = sd.query_devices(device)["name"]
            self.device_label = f"{name} @ {rate} Hz/{channels}ch ({label})"
            log.info("Mikrofon-Stream aktiv: %s", self.device_label)
            return
        raise RuntimeError("Kein Mikrofon liefert Daten – " + "; ".join(errors))

    def close(self):
        with self._lock:
            self._collecting = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
            self.level = 0.0
            log.info("Mikrofon-Stream geschlossen")

    def _ensure_stream(self):
        """Öffnet den Stream neu, falls er fehlt oder keine Daten mehr liefert
        (z. B. nach Gerätewechsel — Windows lässt tote Streams „aktiv“ erscheinen)."""
        if self._stream is not None:
            silent_for = time.monotonic() - self._last_data
            if self._stream.active and silent_for < DEAD_AFTER:
                return
            log.warning("Mikrofon-Stream tot (letzte Daten vor %.1f s) – öffne neu", silent_for)
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.open()

    # ---- Aufnahme ----

    def start(self):
        self._ensure_stream()
        self._begin_collect()

    def _begin_collect(self):
        with self._lock:
            if self._collecting:
                return
            self._chunks = list(self._pre_roll)
            self._frames = sum(len(c) for c in self._chunks)
            self._limit_fired = False
            self._collecting = True
        log.info("Aufnahme gestartet (Pre-Roll: %.2f s)", self._frames / self.capture_rate)

    def stop(self):
        """Beendet das Sammeln und liefert das Audio (auf sample_rate resampelt);
        der Stream bleibt offen."""
        with self._lock:
            self._collecting = False
            chunks, self._chunks = self._chunks, []
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        audio = resample(audio, self.capture_rate, self.sample_rate)
        log.info("Aufnahme beendet: %.1f s", len(audio) / self.sample_rate)
        return audio

    def _callback(self, indata, frames, time_info, status):
        if status:
            log.warning("Audio-Status: %s", status)
        self._last_data = time.monotonic()
        chunk = indata.mean(axis=1) if indata.shape[1] > 1 else indata[:, 0].copy()
        self.level = float(np.sqrt(np.mean(chunk * chunk)))
        fire_limit = False
        with self._lock:
            self._pre_roll.append(chunk)
            self._pre_roll_held += len(chunk)
            # trimmen, solange der Puffer auch ohne den ältesten Block lang genug bleibt
            while self._pre_roll and self._pre_roll_held - len(self._pre_roll[0]) >= self.pre_roll_frames:
                self._pre_roll_held -= len(self._pre_roll.popleft())
            if self._collecting:
                if self._frames >= self.max_frames:
                    if not self._limit_fired:
                        self._limit_fired = True
                        fire_limit = True
                else:
                    self._chunks.append(chunk)
                    self._frames += len(chunk)
        if fire_limit:
            log.info("Zeitlimit erreicht (%d s)", self.max_frames // self.capture_rate)
            if self.on_limit:
                self.on_limit()
