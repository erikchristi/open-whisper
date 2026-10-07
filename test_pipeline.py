"""End-to-End-Smoke-Test ohne Mikrofon.

Erzeugt per Windows-TTS (SAPI) ein deutsches Test-WAV, lädt das Parakeet-Modell
über denselben Transcriber wie die App (inkl. CUDA→CPU-Fallback) und prüft,
ob die Kernwörter im Transkript auftauchen.
"""

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

from flow import hard_exit
from flow.config import load_config
from flow.recorder import resample
from flow.transcriber import Transcriber

SENTENCE = "Dies ist ein Test der lokalen Diktierfunktion. Der Text erscheint direkt am Cursor."
KEYWORDS = ("test", "lokal", "diktier", "cursor")


def make_tts_wav(path):
    ps = f'''
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$de = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like "de*" }} | Select-Object -First 1
if ($de) {{ $s.SelectVoice($de.VoiceInfo.Name) }}
$s.SetOutputToWaveFile("{path}")
$s.Speak("{SENTENCE}")
$s.Dispose()
'''
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        check=True, capture_output=True, text=True,
    )


def wav_to_float(path):
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1)
    return data.astype(np.float32) / 32768.0, rate


def finish(code):
    """Beendet den Prozess hart – siehe flow.hard_exit."""
    hard_exit(code)


def main():
    cfg = load_config()
    wav_path = Path(tempfile.gettempdir()) / "diktat_test.wav"

    print("1/3 Erzeuge Test-Audio per Windows-TTS …")
    make_tts_wav(wav_path)
    audio, rate = wav_to_float(wav_path)
    audio = resample(audio, rate, cfg["sample_rate"])
    print(f"    {len(audio) / cfg['sample_rate']:.1f} s Audio ({rate} Hz -> {cfg['sample_rate']} Hz)")

    print("2/3 Lade Parakeet-Modell (Erstlauf lädt das Modell von Hugging Face herunter) …")
    t = Transcriber(cfg, on_status=lambda s: print(f"    {s}"))
    t.load_async()
    t.ready.wait()
    if t.model is None:
        print(f"FEHLER: Modell konnte nicht geladen werden: {t.load_error}")
        finish(1)
    print(f"    Modell: {t.model_name} auf {t.device}")

    print("3/3 Transkribiere …")
    text = t.transcribe(audio)
    print(f"    Ergebnis: {text!r}")

    hits = [k for k in KEYWORDS if k in text.lower()]
    if len(hits) >= 2:
        print(f"OK – Pipeline funktioniert ({len(hits)}/{len(KEYWORDS)} Kernwörter erkannt).")
        finish(0)
    else:
        print(f"FEHLER: Kernwörter nicht wiedergefunden (nur {hits}).")
        finish(1)


if __name__ == "__main__":
    main()
