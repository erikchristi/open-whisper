# Lokales Diktat

Eine lokale Alternative zu [Wispr Flow](https://wisprflow.ai) für Windows. Du drückst einen
Hotkey, sprichst, und der Text erscheint an der Cursorposition, egal in welcher Anwendung
(Editor, Browser, Mail, Chat und so weiter). Die Spracherkennung läuft **komplett offline** mit
NVIDIAs [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) über
[onnx-asr](https://github.com/istupakov/onnx-asr). Das Modell versteht 25 europäische Sprachen
(darunter Deutsch und Englisch) und erkennt die Sprache automatisch. Keine Cloud, keine laufenden Kosten,
keine Daten verlassen deinen Rechner.

## Systemanforderungen

| Bereich | Anforderung |
|---|---|
| Betriebssystem | Windows 10 oder Windows 11 (64 Bit) |
| Python | Version 3.10 oder neuer ([python.org](https://www.python.org/downloads/)) |
| Arbeitsspeicher | mindestens 8 GB RAM |
| Festplatte | ca. 1 GB frei für den CPU-Betrieb, ca. 6 GB mit GPU-Unterstützung (Sprachmodell plus CUDA-Bibliotheken) |
| Mikrofon | ein beliebiges Eingabegerät (eingebautes Notebook-Mikrofon reicht) |
| Grafikkarte | optional, aber empfohlen: NVIDIA-GPU mit CUDA-Unterstützung. Ohne GPU läuft die App auf der CPU, dann etwas langsamer |
| Internet | nur einmalig beim ersten Start nötig, um das Sprachmodell zu laden. Danach ist alles offline |

Getestet wurde die App unter Windows 11 mit Python 3.14 und einer NVIDIA RTX 2060. Andere
Konfigurationen funktionieren ebenfalls, sofern die obigen Punkte erfüllt sind.

## Schnellstart in vier Schritten

Wenn du wenig Erfahrung mit Python hast, folge einfach dieser Reihenfolge. Alle Pakete landen in
einer eigenen virtuellen Umgebung (`.venv` im Projektordner), dein System-Python bleibt unberührt.

**1. Python installieren.** Lade Python von [python.org](https://www.python.org/downloads/) und
setze bei der Installation das Häkchen bei **"Add Python to PATH"**. Prüfe danach in der
Eingabeaufforderung (PowerShell), ob es funktioniert:

```
python --version
```

**2. Projekt herunterladen.** Lade dieses Repository als ZIP herunter und entpacke es, oder klone
es mit Git:

```
git clone https://github.com/erikchristi/open-whisper.git
cd open-whisper
```

Lege den Ordner möglichst an einen kurzen Pfad (zum Beispiel `C:\Tools\open-whisper`). Sehr lange
Pfade stoßen an die 260-Zeichen-Grenze von Windows und lassen die Installation scheitern.

**3. Einrichten.** Doppelklick auf `setup.bat`. Das Skript legt die `.venv` an und installiert alle
Abhängigkeiten. Findet es eine NVIDIA-Grafikkarte (ab RTX 20xx / Turing, aktueller Treiber nötig),
installiert es automatisch die GPU-Variante samt CUDA 13 und cuDNN 9 (einige GB, kein
CUDA-Toolkit nötig). Ohne NVIDIA-Karte läuft alles auf der CPU.

- `setup.bat cpu` erzwingt die CPU-Variante, auch wenn eine GPU vorhanden ist.
- `setup.bat` erneut ausführen aktualisiert oder repariert die Installation. Beende die App vorher
  über das Tray-Icon, sonst sind ihre Dateien gesperrt.

**4. App starten.** Doppelklick auf `start_diktat.bat` (startet ohne Konsolenfenster) oder mit
sichtbarer Konsole in PowerShell:

```
.venv\Scripts\python.exe app.py
```

Beim allerersten Start lädt die App das Sprachmodell herunter (Parakeet in voller Genauigkeit
mit ca. 2,4 GB bei GPU, int8-quantisiert mit ca. 0,65 GB bei CPU). Das dauert einen Moment und passiert nur einmal.
Danach ist alles lokal gecacht und funktioniert offline.

## Bedienung

| Taste | Funktion |
|---|---|
| **F8 halten** | Push to talk: solange gedrückt wird aufgenommen, beim Loslassen wird transkribiert und eingefügt |
| **F9** | Umschalten: einmal drücken startet die Aufnahme, erneut drücken stoppt sie (für längere Diktate) |

Ein kleines Overlay unten in der Bildschirmmitte zeigt den Status
(Aufnahme, Transkribiere, Eingefügt). Während der Aufnahme läuft dort ein **VU-Meter** mit. Wenn
die Balken beim Sprechen ausschlagen, kommt dein Mikrofon nachweislich in der App an. Im
System-Tray sitzt ein Mikrofon-Icon mit Statusanzeige und dem Menüpunkt "Beenden".

**Hinweis zum Mikrofon:** Der Mikrofon-Stream bleibt dauerhaft offen, solange die App läuft
(der Windows-Mikrofon-Indikator leuchtet also durchgehend). Das ist Absicht, denn nur so startet
die Aufnahme ohne Verzögerung. Ein Ringpuffer von 0,4 Sekunden sorgt außerdem dafür, dass auch
Wörter erfasst werden, die minimal vor dem Tastendruck beginnen. Außerhalb einer Aufnahme wird
nichts gespeichert. Der Puffer wird laufend überschrieben und verlässt nie den Arbeitsspeicher.

## Konfiguration (`config.json`)

Die App liest ihre Einstellungen aus `config.json`. Alle Werte haben sinnvolle Voreinstellungen,
du musst nichts ändern, um loszulegen.

| Option | Voreinstellung | Bedeutung |
|---|---|---|
| `hotkey_ptt` | `"f8"` | Push-to-talk-Taste (halten); leerer Wert `""` deaktiviert sie |
| `hotkey_toggle` | `"f9"` | Umschalt-Taste; leerer Wert `""` deaktiviert sie |
| `device` | `"auto"` | `auto` (nutzt GPU, sonst CPU), `cuda` oder `cpu` |
| `model` | `"nemo-parakeet-tdt-0.6b-v3"` | Modellname für onnx-asr (die Sprache wird automatisch erkannt) |
| `quantization_gpu` / `quantization_cpu` | `null` / `"int8"` | Quantisierung je nach Gerät (`null` steht für volle Genauigkeit) |
| `input_device` | `null` | Mikrofon-Index (`null` steht für Standardmikrofon; Liste anzeigen mit `.venv\Scripts\python.exe -m sounddevice`) |
| `paste_method` | `"clipboard"` | `clipboard` (Strg+V, Zwischenablage wird danach wiederhergestellt) oder `type` (zeichenweise tippen) |
| `max_seconds` | `120` | Maximale Aufnahmedauer in Sekunden, danach wird automatisch transkribiert |
| `pre_roll_seconds` | `0.4` | Vorlauf aus dem Ringpuffer, der jeder Aufnahme vorangestellt wird |

## Tests ohne Mikrofon

```
.venv\Scripts\python.exe test_pipeline.py     (TTS-Audio erzeugen, transkribieren, Ergebnis prüfen)
.venv\Scripts\python.exe test_recorder.py     (Pre-Roll, Ringpuffer und Zeitlimit des Recorders)
```

## Fehlersuche

- **Logs**: Die Datei `app.log` im Projektordner enthält alle Meldungen.
- **Kein Text erscheint**: Manche Apps, die mit Administratorrechten laufen, empfangen keine
  Eingaben von normalen Prozessen. Starte die App in dem Fall ebenfalls über "Als Administrator
  ausführen".
- **Falsches Mikrofon**: Mit `.venv\Scripts\python.exe -m sounddevice` bekommst du alle Geräte aufgelistet. Trage
  den passenden Index in `config.json` unter `input_device` ein. Ohne Angabe wählt die App
  automatisch den WASAPI-Standardeingang mit nativer Abtastrate und prüft, ob wirklich Daten
  fließen (in `app.log` erscheint dann "Mikrofon-Stream aktiv"). Schlägt das VU-Meter bei der
  Aufnahme nicht aus, greift die App auf das falsche Gerät zu.
- **GPU wird nicht genutzt**: Prüfe `app.log` auf die Zeile "Modell bereit". Steht dort `cpu`,
  zeigt die Zeile "Modell-Load auf cuda fehlgeschlagen" den Grund. Häufigste Ursachen: die
  CPU-Variante `onnxruntime` ist installiert, CUDA 13 oder cuDNN fehlen, oder der Grafiktreiber
  ist zu alt. Abhilfe: Treiber aktualisieren, App beenden und `setup.bat` erneut ausführen.
- **Installation bricht mit "No such file or directory" oder "Long Path" ab**: Der Projektpfad ist
  zu lang. Verschiebe den Ordner an einen kürzeren Pfad, lösche `.venv` und starte `setup.bat` neu.

## Grenzen dieser Version

- Keine Nachbearbeitung durch ein Sprachmodell (Füllwörter bleiben so, wie du sie sprichst).
- Kein automatischer Start mit Windows. Bei Bedarf legst du eine Verknüpfung zu
  `start_diktat.bat` in den Autostart-Ordner (`shell:startup`).

## Lizenz

Lizenziert unter der [Apache-Lizenz 2.0](LICENSE).
