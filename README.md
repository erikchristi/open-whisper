# Lokales Diktat

Eine lokale Alternative zu [Wispr Flow](https://wisprflow.ai) für Windows: Hotkey drücken,
sprechen, und der Text erscheint an der Cursorposition — in jeder Anwendung (Editor,
Browser, Mail, Chat …). Die Spracherkennung läuft **komplett offline** mit
[faster-whisper](https://github.com/SYSTRAN/faster-whisper). Keine Cloud, keine Kosten,
keine Daten verlassen den Rechner.

## Bedienung

| Taste | Funktion |
|---|---|
| **F8 halten** | Push-to-talk: solange gedrückt wird aufgenommen, beim Loslassen wird transkribiert und eingefügt |
| **F9** | Toggle: einmal drücken startet die Aufnahme, erneut drücken stoppt sie (für längere Diktate) |

Ein kleines Overlay unten in der Bildschirmmitte zeigt den Status
(● Aufnahme / Transkribiere / ✓ Eingefügt). Während der Aufnahme läuft dort ein
**VU-Meter** mit — schlagen die Balken beim Sprechen aus, kommt dein Mikrofon
nachweislich in der App an. Im System-Tray sitzt ein Mikrofon-Icon mit Status
und „Beenden“.

**Hinweis:** Der Mikrofon-Stream bleibt dauerhaft offen (der Windows-Mikrofon-Indikator
leuchtet, solange die App läuft). Das ist Absicht: nur so startet die Aufnahme ohne
Verzögerung, und ein Ringpuffer von 0,4 s sorgt dafür, dass auch Wörter erfasst werden,
die minimal vor dem Tastendruck beginnen. Außerhalb einer Aufnahme wird nichts
gespeichert — der Puffer wird laufend überschrieben und verlässt nie den Arbeitsspeicher.

## Start

```
start_diktat.bat        (Doppelklick, ohne Konsolenfenster; Logs in app.log)
```
oder mit sichtbarer Konsole:
```
python app.py
```

## Installation

```
pip install -r requirements.txt
```

**GPU (empfohlen, NVIDIA):** Für CUDA-Betrieb werden cuBLAS und cuDNN 9 benötigt:
```
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```
Die App bindet die DLLs automatisch ein und nutzt dann das Modell `large-v3-turbo`
(beste Qualität, auf einer RTX 2060 deutlich schneller als Echtzeit). Schlägt die
CUDA-Initialisierung fehl, fällt die App automatisch auf CPU mit dem Modell `small` zurück.

Beim ersten Start wird das Whisper-Modell von Hugging Face heruntergeladen
(`large-v3-turbo` ≈ 1,6 GB bzw. `small` ≈ 0,5 GB) und lokal gecacht — danach ist
alles offline.

## Konfiguration (`config.json`)

| Option | Default | Bedeutung |
|---|---|---|
| `hotkey_ptt` | `"f8"` | Push-to-talk-Taste (halten); `""` deaktiviert |
| `hotkey_toggle` | `"f9"` | Toggle-Taste; `""` deaktiviert |
| `language` | `"de"` | Diktatsprache (fest, kein Auto-Detect) |
| `device` | `"auto"` | `auto` (CUDA, sonst CPU), `cuda` oder `cpu` |
| `model_gpu` / `model_cpu` | `large-v3-turbo` / `small` | Whisper-Modell je Gerät |
| `input_device` | `null` | Mikrofon: `null` = automatisch, Gerätename (Text) oder Index. Am einfachsten per Rechtsklick aufs Tray-Icon → „Mikrofon“ wählen — die Wahl wird hier gespeichert |
| `paste_method` | `"clipboard"` | `clipboard` (Strg+V, Zwischenablage wird wiederhergestellt) oder `type` (zeichenweise tippen) |
| `max_seconds` | `120` | Maximale Aufnahmedauer, danach wird automatisch transkribiert |
| `pre_roll_seconds` | `0.4` | Vorlauf aus dem Ringpuffer, der jeder Aufnahme vorangestellt wird |
| `initial_prompt` | `""` | Optionaler Kontext-Prompt (z. B. Fachbegriffe, Namen) |

## Tests ohne Mikrofon

```
python test_pipeline.py     (TTS-Audio erzeugen → transkribieren → Ergebnis prüfen)
python test_recorder.py     (Pre-Roll, Ringpuffer und Zeitlimit des Recorders)
```

## Fehlersuche

- **Logs**: `app.log` im Projektordner.
- **Kein Text erscheint**: Manche Apps mit Admin-Rechten empfangen keine Eingaben von
  normalen Prozessen — die App dann ebenfalls „Als Administrator ausführen“.
- **Falsches Mikrofon**: `python -m sounddevice` listet alle Geräte; Index in
  `config.json` unter `input_device` eintragen. Ohne Angabe wählt die App automatisch
  den WASAPI-Standardeingang mit nativer Abtastrate und prüft per Liveness-Probe, dass
  wirklich Daten fließen (`app.log`: „Mikrofon-Stream aktiv: …“). Schlägt das VU-Meter
  bei Aufnahme nicht aus, greift die App auf das falsche Gerät zu.
- **GPU wird nicht genutzt**: `app.log` prüfen („Modell bereit: … auf cuda/cpu“).
  Häufigste Ursache: cuDNN fehlt → `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`.

## Grenzen von v1

- Keine LLM-Nachbearbeitung (Füllwörter bleiben, wie gesprochen)
- Kein Autostart mit Windows (bei Bedarf: Verknüpfung zu `start_diktat.bat` in
  `shell:startup` legen)
