# Cerberus

<details>

<summary>etymology</summary>

  

The guardian fetches things from the 'underworld' of the internet.

  

</details>

**Ein robustes CLI-Skript zum Herunterladen von Videos** aus Webseiten. Unterstützt:
- `yt_dlp` für bekannte Hosts und komplexe Streams (HLS, DASH, Playlists)
- Selenium-basiertes Netzwerk-Logging zur Extraktion direkter Video-URLs
- Nummerierung/Handling von mehreren Videos unter derselben URL (z. B. erome.com)
- Sortierung in Ordner nach Plattform / Künstler / Genre
- Konfigurierbare Einstellungen via `Settings.txt`

---

## Inhalt
- `downloader.py` — Hauptskript
- `Settings.txt` — zentrale Einstellungen (wird erzeugt, falls nicht vorhanden)
- Downloads gespeichert unter: `%APPDATA%/converter/Downloads` (Windows) bzw. `~/.converter/Downloads` (Linux/Mac) — konfigurierbar

---

## Voraussetzungen

- Python 3.8+
- Chrome (lokal installiert) oder anderer Chromium-Browser (Pfad in Settings setzen)
- `pip`-Pakete:
  ```bash
  pip install -r requirements.txt
  ```

Beispiel ´requirements.txt´
´´´bash
selenium
yt_dlp
requests
browser-cookie3
beautifulsoup4
tqdm
´´´
- FFmpeg (für Postprocessing / Konvertierung) empfohlen und im PATH

# Installation & erster Start
1. Klone das Repo:
´´´bash
git clone <repo-url>
cd <repo>
´´´

2. Installiere Abhängigkeiten:
´´´bash
pip install -r requirements.txt
´´´

3. Erzeuge / bearbeite die Settings.txt (wird beim ersten Start erzeugt) oder öffne sie mit:
´´´bash
python downloader.py --config
´´´

Minimum: ´browser_path=C:/Path/To/Browser.exe´

# CLI — Beispiele
- Single-Link herunterladen:
´´´bash
python downloader.py -l "https://erome.com/abcd" -p "/home/user/Downloads"
´´´

- Mehrere URLs (Comma-separated):
´´´bash
python downloader.py -u "https://site1.com/video1,https://site2.com/video2"
´´´

- Liste aus Datei:
´´´bash
python downloader.py -r urls.txt
´´´

- Erzwinge yt_dlp (ohne Selenium):
´´´bash
python downloader.py -l "https://example.com" -f
´´´

- Qualität:
´´´bash
python downloader.py -l "..." -q "720p"
´´´

# Verhalten bzgl. Duplikaten / Nummerierung

- ´overwrite_existing=true´ → vorhandene Dateien werden überschrieben.

- ´overwrite_existing=false´ → vorhandene Dateien werden übersprungen (Standard).

- **Ausnahme: Wenn eine einzelne URL mehrere Video-Ressourcen** enthält (z. B. mehrere ´<video>´-Tags auf einer Seite oder mehrere ´yt_dlp´-Entries), werden diese als eine Session behandelt und automatisch nummeriert:

    - ´TITLE.mp4´, ´TITLE(1).mp4´, ´TITLE(2).mp4´, ...
    - Dadurch werden mehrere Videos aus derselben Seite nicht übersprungen.

# Erweiterung & Entwicklung — Hinweise

**Neue Sites**: Für neue Seiten zuerst requests + BeautifulSoup Versuch einbauen (schnell), dann Selenium/yt_dlp fallback.

HLS: Wenn Seite m3u8 liefert, nutze ffmpeg oder yt_dlp für fragmentiertes Streaming.

Tests: Schreibe Unit-Tests für Namensauflösung und Integrationstests gegen statische HTML-Mocks.

Sicherheit: Prüfe Nutzungsbedingungen der Download-Quellen; implementiere optional eine Nutzungs-Hinweis/Confirm-Funktion.

FAQ / Troubleshooting

Browser-Pfad-Fehler

Stelle sicher, dass browser_path in Settings.txt korrekt ist und die exe vorhanden ist.

Selenium startet nicht (Headless/ChromeDriver)

Achte auf kompatible ChromeDriver-Version oder setze chromedriver im PATH. Empfohlen: Verwendung bundlerüber webdriver-manager oder matching driver.

yt_dlp Fehler

Prüfe Logs (converter.log im Konfig-Ordner). Setze ggf. use_browser_cookies=true und exportiere Cookies, falls Inhalte login-geschützt sind.

License & Legal

Dieses Tool ist ein technisches Werkzeug. Der Betreiber ist verantwortlich für die rechtmäßige Nutzung. Bitte beachte Urheberrechte und Nutzungsbedingungen der jeweiligen Seiten.

# Todo
- [ ] fix 'overwrite_existing=true' parameter
- [ ] test every parameter
- [x] centralize programfiles
- [x] add sorting via website/artist/genre
- [ ] optimise sorting
- [ ] optimize error_handling
- [x] organize code strucure
- [ ] fix youtube.com -downloads
- [x] add create download-list feature (links multiple downloads together, without external .txt-file)
- [x] download-quality-option-parameter (with standartsettings in external .txt-file)