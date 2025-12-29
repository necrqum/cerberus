# Converter/CerberusFetch.py

import os
import re
import platform
import subprocess
import time
import json
import signal
import threading
import argparse
import requests
import logging
import shutil
from tqdm import tqdm
from urllib.parse import urlparse, unquote

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import NoSuchElementException, NoSuchWindowException, WebDriverException

import yt_dlp

# Global event to signal download termination
stop_download = threading.Event()

# ================================
# Central Configuration Management
# ================================

def get_config_dir():
    """
    Returns the path to the centralized configuration directory.
    On Windows, uses %APPDATA%\\.Cerberus.
    On other systems, uses ~/.Cerberus.
    """
    if platform.system() == "Windows":
        config_dir = os.path.join(os.environ.get("APPDATA"), ".Cerberus")
    else:
        config_dir = os.path.join(os.path.expanduser("~"), ".Cerberus")
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    return config_dir

CONFIG_DIR = get_config_dir()
SETTINGS_PATH = os.path.join(CONFIG_DIR, "Settings.txt")
LOG_PATH = os.path.join(CONFIG_DIR, "Cerberus.log")
DEFAULT_DOWNLOAD_DIR = os.path.join(CONFIG_DIR, "Downloads")

# Ensure default download folder exists
if not os.path.exists(DEFAULT_DOWNLOAD_DIR):
    os.makedirs(DEFAULT_DOWNLOAD_DIR)

# ================================
# Logging Setup
# ================================
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def log_info(message):
    logger.info(message)

def log_error(message):
    logger.error(message)

def print_if_not_ignored(message, settings):
    """
    Prints message to console only if 'ignoreerrors' is not set to true.
    """
    if settings.get('ignoreerrors', 'false').lower() != 'true':
        print(message)

# ================================
# Utility Functions
# ================================

def open_file(file_path):
    """Opens the given file in the system's default editor."""
    try:
        if platform.system() == "Windows":
            os.startfile(file_path)
        elif platform.system() == "Darwin":
            subprocess.call(["open", file_path])
        else:
            subprocess.call(["xdg-open", file_path])
    except Exception as e:
        log_error(f"Error opening file {file_path}: {e}")

def build_settings(file_path=SETTINGS_PATH):
    """Creates the Settings.txt file if it does not exist."""
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            f.write("browser_path=C:/PATH/TO/BROWSER/Browser.exe\n")
            f.write("# use --list-config to see the current/standart -config-settings\n")
            f.write("# use --example-config to view all available config-settings\n")
        log_info(f"Settings file created at {file_path}")

def load_settings(file_path=SETTINGS_PATH):
    """Loads settings from the Settings.txt file."""
    settings = {}
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip() and '=' in line and not line.strip().startswith('#'):
                    key, value = line.split('=', 1)
                    settings[key.strip()] = value.strip()
    except FileNotFoundError:
        log_error(f"Settings file {file_path} not found.")
        build_settings(file_path)
    # Ensure defaults
    if 'overwrite_existing' not in settings:
        settings['overwrite_existing'] = 'false'
    if 'sort_by' not in settings:
        settings['sort_by'] = 'none'
    if 'default_quality' not in settings:
        settings['default_quality'] = 'best'
    if 'use_cwd_as_default' not in settings:
        settings['use_cwd_as_default'] = 'false'
    return settings

def is_output_hidden(settings, args):
    """Checks whether console output should be hidden."""
    return settings.get('output_always_hidden', 'false').lower() == 'true' or args.hidden

def custom_print(*args, hidden=False, **kwargs):
    """Prints to console only if hidden is False."""
    if not hidden:
        print(*args, **kwargs)

# ================================
# Configuration Command Handlers
# ================================

def handle_config(args):
    """
    Handles configuration commands:
      - --list-config: displays the current settings.
      - --example-config: creates an example configuration file.
      - --config (alone): opens the Settings.txt file in the default editor.
    """
    if not os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, 'w') as f:
            f.write("browser_path=C:/PATH/TO/BROWSER/Browser.exe\n")
            f.write("# use --list-config to see the current/standart -config-settings\n")
            f.write("# use --example-config to view all available config-settings\n")
        log_info(f"Created new settings file at {SETTINGS_PATH}")

    if args.list_config:
        settings = load_settings(SETTINGS_PATH)
        custom_print("Current Settings:")
        for key in sorted(settings.keys()):
            custom_print(f"{key} = {settings[key]}")
    elif args.example_config:
        example_path = os.path.join(CONFIG_DIR, "example_settings.txt")
        with open(example_path, 'w') as f:
            f.write(
                """browser_path=C:/PATH/TO/BROWSER/Browser.exe
minimized=false
overwrite_existing=false
output_always_hidden=false
ignoreerrors=false
yt_verbose=false # set true for detailed ytdlp-output
custom_hosts=youtu.be,pornhub.org,erome.com # e.g.
use_browser_cookies=false # needed for yt-downloads
ng_username=your_newgrounds_username # for newgrounds
ng_password=your_newgrounds_password
sort_by=none   # options: none, artist, platform, genre
default_quality=best   # e.g. best, worst, 720p
use_cwd_as_default=false   # if true, default save path is current directory
"""
            )
        print(f"Example configuration created at {example_path}")
    else:
        print(f"Opening settings file at {SETTINGS_PATH}...")
        open_file(SETTINGS_PATH)

# ================================
# Sorting Helper
# ================================

from bs4 import BeautifulSoup

def sort_downloaded_file(file_path, original_url, settings):
    """
    Moves downloaded file into a subfolder based on 'sort_by' setting.
    Possible values: 'none', 'artist', 'platform', 'genre'.

    - 'platform': detect site name via Open Graph 'og:site_name' or fallback to domain.
    - 'artist'/'genre': extract from meta tags <meta name="author"> or <meta name="genre">.

    Returns the new path (or original if not moved).
    """
    sort_by = settings.get('sort_by', 'none').lower()
    if sort_by == 'none':
        return file_path

    # Determine base download directory
    if settings.get('use_cwd_as_default', 'false').lower() == 'true':
        base_dir = os.getcwd()
    else:
        base_dir = DEFAULT_DOWNLOAD_DIR

    platform_folder = None
    artist_folder = None
    genre_folder = None

    # Fetch and parse page once if artist/genre or OG site_name needed
    soup = None
    need_soup = sort_by in ("platform", "artist", "genre")
    if need_soup:
        try:
            resp = requests.get(original_url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            log_error(f"Error fetching page for sorting: {e}")
            soup = None

    # 1) PLATFORM
    if sort_by == "platform":
        if soup:
            og_site = soup.find("meta", property="og:site_name")
            if og_site and og_site.get("content"):
                platform_folder = og_site["content"].strip().lower().replace(" ", "_")
        if not platform_folder:
            # Fallback to domain
            domain = urlparse(original_url).netloc
            platform_folder = domain.replace("www.", "").split(".")[0].lower()
        dest_dir = os.path.join(base_dir, platform_folder)

    # 2) ARTIST
    elif sort_by == "artist":
        if soup:
            author_meta = soup.find("meta", attrs={"name": "author"})
            if author_meta and author_meta.get("content"):
                artist_folder = author_meta["content"].strip().lower().replace(" ", "_")
        if not artist_folder:
            artist_folder = "unknown_artist"
        dest_dir = os.path.join(base_dir, artist_folder)

    # 3) GENRE
    elif sort_by == "genre":
        if soup:
            genre_meta = soup.find("meta", attrs={"name": "genre"})
            if genre_meta and genre_meta.get("content"):
                genre_folder = genre_meta["content"].strip().lower().replace(" ", "_")
        if not genre_folder:
            genre_folder = "unknown_genre"
        dest_dir = os.path.join(base_dir, genre_folder)

    else:
        # Should not reach here, but fallback to base
        dest_dir = base_dir

    # Ensure destination directory exists
    try:
        os.makedirs(dest_dir, exist_ok=True)
        new_path = os.path.join(dest_dir, os.path.basename(file_path))
        shutil.move(file_path, new_path)
        return new_path
    except Exception as e:
        log_error(f"Error moving file to sorted folder: {e}")
        return file_path

# ================================
# Download Functions
# ================================

def download_with_youtube_dl(video_url, save_folder, custom_name=None, quality=None, session_key=None, overwrite_existing=None):
    """
    Robust yt_dlp handler:
     - extracts info once
     - deduplicates entries (stable key)
     - determines real media URLs (prefer entry fields first)
     - downloads each distinct media resource exactly once
     - uses resolve_available_filename for session-local numbering (NAME, NAME(1), ...)
     - falls back to yt_dlp.download per-entry only if direct media URL cannot be determined
    Returns last downloaded path or None.
    """
    settings = load_settings(SETTINGS_PATH)
    yt_verbose = settings.get('yt_verbose', 'false').lower() == 'true'
    # Wenn yt_verbose True => show internal yt_dlp logs (quiet=False)
# Wenn False => suppress internal logs and rely on progress hook (quiet=True)
    if quality is None:
        quality = settings.get('default_quality', 'best')
    if overwrite_existing is None:
        overwrite_existing = settings.get('overwrite_existing', 'false').lower() == 'true'

    # Try to extract info once
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({'quiet': True, 'format': quality}) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except Exception as e:
        log_error(f"yt_dlp extract_info error: {e}")
        info = None

    # Determine base title
    base_title = None
    if custom_name:
        base_title = custom_name[:-4] if custom_name.lower().endswith(".mp4") else custom_name
    else:
        if info:
            base_title = info.get('title') or info.get('fulltitle') or info.get('id')
    if not base_title:
        base_title = "video"

    # Playlist / multiple entries handling
    if info and info.get('entries'):
        raw_entries = [e for e in info.get('entries') if e]
        # stable dedupe by key
        seen_keys = set()
        unique_entries = []
        for e in raw_entries:
            key = e.get('id') or e.get('webpage_url') or e.get('url')
            if not key:
                title = (e.get('title') or '').strip()
                dur = str(e.get('duration') or '')
                fs = str(e.get('filesize') or e.get('filesize_approx') or '')
                key = f"{title}|{dur}|{fs}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_entries.append(e)

        # Reusable ydl instance for targeted re-extraction if needed
        import yt_dlp
        ydl_for_info = yt_dlp.YoutubeDL({'quiet': True, 'format': quality})

        media_seen = set()
        final_paths = []

        for idx, entry in enumerate(unique_entries):
            entry_url = entry.get('webpage_url') or entry.get('url') or video_url

            # Try to get media_url from entry, prefer non-extractive access
            media_url, meta = get_direct_media_url(entry, entry_url, quality=quality, ydl_instance=ydl_for_info)

            # If still no media_url, mark for controlled yt_dlp fallback (we will still dedupe by entry key)
            used_fallback_ydl_download = False
            if not media_url:
                # we will use yt_dlp to download this entry directly (outtmpl below)
                used_fallback_ydl_download = True

            # Deduplicate by media_url (if available), else by entry key
            dedupe_key = media_url if media_url else (entry.get('id') or entry.get('webpage_url') or entry.get('url'))
            if dedupe_key in media_seen:
                continue
            media_seen.add(dedupe_key)

            # Resolve target path using session_key (so same-page multiple videos get numbered)
            entry_title = (entry.get('title') or base_title).strip()
            candidate_base = sanitize_filename(entry_title)
            ext = (meta.get('ext') or 'mp4').lstrip('.')
            target_path = resolve_available_filename(save_folder, candidate_base, ext='.' + ext,
                                                     overwrite_existing=overwrite_existing,
                                                     session_key=session_key or video_url)
            if target_path is None:
                print_if_not_ignored(f"Skipping existing file: {os.path.join(save_folder, candidate_base + '.' + ext)}", settings)
                continue

            saved_path = None
            if not used_fallback_ydl_download:
                ok = download_media_url(media_url, target_path, settings, original_page_url=entry_url)
                if not ok:
                    log_error(f"Failed to download media_url for entry: {media_url}")
                    print_if_not_ignored(f"Failed to download media_url for entry: {media_url}", settings)
                    # try fallback to yt_dlp once for this entry
                    used_fallback_ydl_download = True
                else:
                    saved_path = target_path

            if used_fallback_ydl_download:
                # Controlled yt_dlp download for this entry (prevents playlist-appended suffixes)
                ydl_opts_entry = {
                    'outtmpl': target_path,
                    'format': quality,
                    'noplaylist': True,
                    'quiet': not yt_verbose,
                    'no_warnings': True,
                    'progress_hooks': [ytdlp_progress_hook],
                    'useragent': settings.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'),
                    'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
                    'socket_timeout': int(settings.get('socket_timeout', 60)),
                    'retries': int(settings.get('retries', 10)),
                }
                if settings.get('cookies_file'):
                    ydl_opts_entry['cookiefile'] = settings['cookies_file']
                if settings.get('proxy'):
                    ydl_opts_entry['proxy'] = settings['proxy']
                if settings.get('ignoreerrors', 'false').lower() == 'true':
                    ydl_opts_entry['ignoreerrors'] = True
                try:
                    with yt_dlp.YoutubeDL(ydl_opts_entry) as ydl_single:
                        ydl_single.download([entry_url])
                    saved_path = target_path
                except Exception as e:
                    log_error(f"Fallback yt_dlp download failed for entry {entry_url}: {e}")
                    print_if_not_ignored(f"Fallback yt_dlp download failed for entry {entry_url}: {e}", settings)
                    continue

            # Postprocess / sort
            try:
                moved = sort_downloaded_file(saved_path, entry_url, settings)
                if moved and moved != saved_path:
                    final_paths.append(moved)
                else:
                    final_paths.append(saved_path)
            except Exception:
                final_paths.append(saved_path)

        try:
            ydl_for_info.close()
        except Exception:
            pass

        return final_paths[-1] if final_paths else None

    # Single item fallback (not playlist)
    target_path = resolve_available_filename(save_folder, base_title, ext=".mp4", overwrite_existing=overwrite_existing, session_key=session_key or video_url)
    if target_path is None:
        print_if_not_ignored(f"Skipping existing file: {os.path.join(save_folder, base_title + '.mp4')}", settings)
        return None

    ydl_opts = {
        'outtmpl': target_path,
        'format': quality,
        'noplaylist': True,
        'quiet': not yt_verbose,
        'no_warnings': True,
        'progress_hooks': [ytdlp_progress_hook],
        'useragent': settings.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'),
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
        'socket_timeout': int(settings.get('socket_timeout', 60)),
        'retries': int(settings.get('retries', 10)),
    }
    if settings.get('cookies_file'):
        ydl_opts['cookiefile'] = settings['cookies_file']
    if settings.get('proxy'):
        ydl_opts['proxy'] = settings['proxy']
    if settings.get('ignoreerrors', 'false').lower() == 'true':
        ydl_opts['ignoreerrors'] = True

    try:
        import yt_dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        try:
            final_path = sort_downloaded_file(target_path, video_url, settings)
            if final_path and final_path != target_path:
                return final_path
            return target_path
        except Exception:
            return target_path
    except Exception as e:
        log_error(f"Error downloading video with yt_dlp: {e}")
        print_if_not_ignored(f"Error downloading video with yt_dlp: {e}", settings)
        return None

def download_video(video_url, save_path):
    """Downloads a video from a URL using HTTP."""
    settings = load_settings(SETTINGS_PATH)
    try:
        response = requests.get(video_url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        progress = tqdm(total=total_size, unit='iB', unit_scale=True, unit_divisor=1024, desc=os.path.basename(save_path))

        with open(save_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=block_size):
                if stop_download.is_set():
                    print("\nDownload aborted.")
                    return None
                file.write(chunk)
                progress.update(len(chunk))

        progress.close()
        if total_size != 0 and progress.n != total_size:
            print(f"Warning: Download may be incomplete. ({progress.n}/{total_size})")
        log_info(f"Video successfully downloaded: {save_path}")
        print(f"\nVideo successfully downloaded: {save_path}")
        final_path = sort_downloaded_file(save_path, video_url, settings)
        if final_path != save_path:
            print(f"Moved to sorted folder: {final_path}")
        return final_path
    except Exception as e:
        log_error(f"Error downloading video: {e}")
        print_if_not_ignored(f"Error downloading video: {e}", settings)
        return None

INVALID_WIN_CHARS = r'<>:"/\\|?*\x00-\x1f'
INVALID_RE = re.compile(f'[{re.escape("<>:\"/\\\\|?*")}\x00-\x1f]')

def sanitize_filename(name, max_length=200):
    """
    Entfernt/ersetzt ungültige Dateiname-Zeichen für Windows/Linux.
    - ersetzt ungültige Zeichen durch '_' und kürzt Länge
    - entfernt führende/trailing Whitespace und Punkt
    """
    if not name:
        return "video"
    # normalize whitespace
    s = str(name).strip()
    # replace invalid chars
    s = INVALID_RE.sub("_", s)
    # remove control chars explicitly
    s = ''.join(ch for ch in s if ord(ch) >= 32)
    # Trim trailing dots/spaces (Windows problem)
    s = s.rstrip(". ")
    # Limit length (keep extension space later)
    if len(s) > max_length:
        s = s[:max_length].rstrip()
    # fallback
    if not s:
        return "video"
    return s

def extract_video_name(driver):
    """Extracts the title of the video from the page."""
    try:
        title_element = driver.find_element(By.TAG_NAME, 'title')
        video_title = title_element.get_attribute('innerText')
        safe_title = ''.join(c for c in video_title if c.isalnum() or c in (' ', '_')).rstrip()
        return safe_title
    except NoSuchWindowException:
        print("The browser window closed unexpectedly.")
        raise
    except Exception as e:
        log_error(f"Error extracting video title: {e}")
        return "video"

def extract_main_video_url(driver):
    """Searches for and extracts the main video URL from the page."""
    try:
        video_element = driver.find_element(By.TAG_NAME, 'video')
        video_url = video_element.get_attribute('src')
        if video_url and (".mp4" in video_url or ".wav" in video_url):
            return video_url
        else:
            print("No valid video tag or URL found.")
            return None
    except NoSuchElementException:
        print("No video tag found on the page.")
        return None
    except Exception as e:
        log_error(f"Error extracting main video URL: {e}")
        return None

def check_file_exists(save_path, overwrite_existing):
    """
    Checks if the file exists.
    If overwrite_existing is True, the file is not skipped but overwritten.
    """
    settings = load_settings(SETTINGS_PATH)
    if isinstance(overwrite_existing, str):
        overwrite_existing = overwrite_existing.lower() == 'true'
    if os.path.exists(save_path):
        if overwrite_existing:
            print_if_not_ignored(
                f"The file {save_path} already exists but will be overwritten since overwrite_existing=true.",
                settings
            )
            return False
        else:
            print_if_not_ignored(
                f"Skipping download because the file already exists: {save_path}",
                settings
            )
            return True
    return False

def download_video_from_page(url, browser_path, save_folder, video_index, total_videos,
                             minimize_browser, overwrite_existing, custom_name=None, force=False, quality=None):
    """
    Attempts to download a video from a webpage.
    Workflow:
      - If the --force flag is set, or the URL matches known hosts (fixed: 'youtube.com' and 'pornhub.com', plus custom hosts from settings),
        the video is downloaded immediately using yt_dlp.
      - Otherwise, up to 3 attempts are made:
          * Attempts 1 and 2 use Selenium.
          * On the 3rd attempt, yt_dlp is used as fallback.
      - Newgrounds-specific: if URL contains 'newgrounds.com/portal/view', handle login.
    Returns the final saved path (or None).
    """
    settings = load_settings(SETTINGS_PATH)
    print_if_not_ignored(f"\nStarting download of video {video_index + 1}/{total_videos}: {url}", settings)
    
    # ensure a separate session counter exists for this top-level URL
    with session_lock:
        session_filename_counters.setdefault(url, {})

    # Determine known hosts including custom
    default_hosts = ["youtube.com", "pornhub.com"]
    custom_hosts_str = settings.get('custom_hosts', "")
    additional_hosts = [host.strip() for host in custom_hosts_str.split(",") if host.strip()] if custom_hosts_str else []
    known_hosts = default_hosts + additional_hosts

    # Handle Newgrounds login if needed
    is_ng = "newgrounds.com/portal/view" in url
    ng_cookies = None
    if is_ng:
        if settings.get('use_browser_cookies','false').lower() == 'true':
            try:
                import browser_cookie3
                ng_cookies = browser_cookie3.load(domain_name='newgrounds.com')
            except Exception as e:
                log_error(f"Error loading browser cookies: {e}")
                ng_cookies = None
        if ng_cookies is None:
            ng_user = settings.get('ng_username','')
            ng_pass = settings.get('ng_password','')
            if ng_user and ng_pass:
                session = requests.Session()
                login_payload = {'username': ng_user, 'password': ng_pass}
                try:
                    session.post("https://www.newgrounds.com/login", data=login_payload)
                    ng_cookies = session.cookies
                except Exception as e:
                    log_error(f"Error performing Newgrounds login: {e}")
                    ng_cookies = None

    # If force or known host, use yt_dlp directly
    if force or any(host in url for host in known_hosts):
        return download_with_youtube_dl(url, save_folder, custom_name, quality)

    for attempt in range(3):
        if attempt < 2:
            print_if_not_ignored(f"\nSelenium attempt {attempt+1} of 2...", settings)
        else:
            print_if_not_ignored("\nSelenium attempts failed - falling back to yt_dlp (attempt 3)...", settings)

        if attempt < 2:
            driver = None
            try:
                options = Options()
                options.binary_location = browser_path
                options.add_argument("--incognito")
                capabilities = DesiredCapabilities.CHROME.copy()
                capabilities['goog:loggingPrefs'] = {'performance': 'ALL'}
                options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
                if minimize_browser:
                    options.add_argument("--window-position=0,3000")
                    options.add_argument("--headless=new")

                driver = webdriver.Chrome(service=ChromeService(), options=options)
                driver.get("about:blank")
                # Inject Newgrounds cookies if needed
                if is_ng and ng_cookies:
                    for c in ng_cookies:
                        try:
                            driver.add_cookie({'name': c.name, 'value': c.value, 'domain': '.newgrounds.com'})
                        except:
                            pass
                driver.get(url)
                time.sleep(5)

                if not custom_name:
                    # sanitize title extracted from page
                    raw_name = extract_video_name(driver)
                    video_name = sanitize_filename(raw_name)
                    current_save_path = os.path.join(save_folder, f"{video_name}.mp4")
                else:
                    # sanitize provided custom name as well (strip .mp4 if present)
                    base_raw = custom_name[:-4] if custom_name.lower().endswith(".mp4") else custom_name
                    base = sanitize_filename(base_raw)
                    current_save_path = os.path.join(save_folder, f"{base}.mp4")


                logs = driver.get_log('performance')
                video_links = []
                for log in logs:
                    log_message = json.loads(log['message'])
                    message = log_message.get('message', {})
                    if message.get('method') == 'Network.responseReceived':
                        response = message.get('params', {}).get('response', {})
                        if 'video' in response.get('mimeType', '') or '.mp4' in response.get('url', '') or '.m3u8' in response.get('url', '') or '.wav' in response.get('url', ''):
                            video_links.append(response.get('url'))

                    if video_links:
                        # dedupe identical resource URLs logged multiple times
                        unique_video_links = []
                        for v in video_links:
                            if v and v not in unique_video_links:
                                unique_video_links.append(v)

                        # determine base name if not provided
                        if not custom_name:
                            video_name = sanitize_filename(extract_video_name(driver))

                        downloaded_any = False
                        final_path = None

                        for idx, video_url_found in enumerate(unique_video_links):
                            # if custom name provided, create numbered variant directly
                            if custom_name:
                                base_raw = custom_name[:-4] if custom_name.lower().endswith(".mp4") else custom_name
                                base = sanitize_filename(base_raw)
                                if len(unique_video_links) > 1:
                                    candidate = os.path.join(save_folder, f"{base}({idx+1}).mp4")
                                else:
                                    candidate = os.path.join(save_folder, f"{base}.mp4")
                                if os.path.exists(candidate) and not overwrite_existing:
                                    print_if_not_ignored(f"Skipping existing file: {candidate}", settings)
                                    continue
                                current_save_path = candidate
                                # Download via direct stream or yt_dlp fallback - prefer direct download
                                ok = download_media_url(video_url_found, current_save_path, settings, original_page_url=url)
                                
                                if not ok:
                                    # fallback to yt_dlp single-download
                                    current_save_path = download_with_youtube_dl(video_url_found, save_folder, custom_name=base, quality=quality, session_key=url, overwrite_existing=overwrite_existing)
                                if current_save_path:
                                    downloaded_any = True
                                    final_path = current_save_path
                            else:
                                # no custom name => resolve filename using session_key=url so multiple items on same page get numbered
                                resolved = resolve_available_filename(save_folder, video_name, ext=".mp4", overwrite_existing=overwrite_existing, session_key=url)
                                if resolved is None:
                                    print_if_not_ignored(f"Skipping existing file: {os.path.join(save_folder, video_name + '.mp4')}", settings)
                                    continue
                                # prefer direct download
                                ok = download_media_url(video_url_found, resolved, settings, original_page_url=url)
                                if not ok:
                                    # fallback: yt_dlp (will use session_key=url internally)
                                    final_from_ydl = download_with_youtube_dl(url, save_folder, custom_name=None, quality=quality, session_key=url, overwrite_existing=overwrite_existing)
                                    if final_from_ydl:
                                        downloaded_any = True
                                        final_path = final_from_ydl
                                else:
                                    downloaded_any = True
                                    final_path = resolved

                        if downloaded_any:
                            return final_path
                        else:
                            print_if_not_ignored("No downloadable video links or all skipped due to existing files.", settings)
                else:
                    print_if_not_ignored("No video links found. Retrying...", settings)
            except (NoSuchWindowException, WebDriverException) as e:
                log_error(f"WebDriver error: {e}. Retrying...")
                print_if_not_ignored(f"WebDriver error: {e}. Retrying...", settings)
            except Exception as e:
                log_error(f"Error: {e}. Retrying...")
                print_if_not_ignored(f"Error: {e}. Retrying...", settings)
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        print_if_not_ignored("WebDriver could not be closed properly.", settings)
        else:
            return download_with_youtube_dl(url, save_folder, custom_name, quality)

    return None

def download_videos_from_list(file_path, browser_path, save_folder, minimize_browser, overwrite_existing, force=False, quality=None):
    """Downloads multiple videos listed in a file."""
    settings = load_settings(SETTINGS_PATH)
    try:
        with open(file_path, 'r') as file:
            urls = file.readlines()

        total_videos = len(urls)
        video_save_paths = []
        for index, url in enumerate(urls):
            url = url.strip()
            if url:
                tentative_video_name = f"video_{index + 1}.mp4"
                save_path = os.path.join(save_folder, tentative_video_name)
                if not check_file_exists(save_path, overwrite_existing):
                    video_save_paths.append((url, save_path))

        for video_index, (url, save_path) in enumerate(video_save_paths):
            if stop_download.is_set():
                print_if_not_ignored("\nAbort signal received. Terminating further downloads.", settings)
                break

            print_if_not_ignored(f"\n[{video_index + 1}/{len(video_save_paths)}] Starting download for: {url}", settings)
            start_time = time.time()
            final_path = download_video_from_page(url, browser_path, save_folder, video_index,
                                                  len(video_save_paths), minimize_browser, overwrite_existing,
                                                  force=force, quality=quality)
            elapsed_time = time.time() - start_time
            if final_path:
                print(f"Download completed in {elapsed_time:.2f} seconds: {final_path}")
            else:
                print(f"Download failed in {elapsed_time:.2f} seconds.")
    except Exception as e:
        log_error(f"Error processing list: {e}")
        print_if_not_ignored(f"Error processing list: {e}", settings)

# ====== Session-based filename counters to number files from same URL/session ======
session_filename_counters = {}
session_lock = threading.Lock()

def resolve_available_filename(save_folder, base_name, ext=".mp4", overwrite_existing=False, session_key=None):
    """
    Determine an available filename in save_folder.

    Behavior:
    - If overwrite_existing True: return base_name+ext (may overwrite).
    - If overwrite_existing False:
        * If the base file does not exist -> return base_name+ext and (if session_key) initialize session counter for this base.
        * If the base file exists:
            - If no session_key provided -> return None (skip; respect overwrite_existing=False).
            - If session_key provided:
                - If this session already has a counter for this base -> find next NAME(n) that doesn't exist and return it.
                - If this session has no counter for this base -> return None (skip) — prevents numbering across separate runs.
    """
    # sanitize base name for filesystem safety (sanitize_filename must exist)
    safe_base = sanitize_filename(base_name)

    if not ext.startswith("."):
        ext = "." + ext

    base_candidate = os.path.join(save_folder, f"{safe_base}{ext}")

    if overwrite_existing:
        # If overwriting is allowed, always return the base path (will overwrite)
        return base_candidate

    # If base file does not exist -> use it.
    if not os.path.exists(base_candidate):
        # If session_key provided, initialize the counter for this base so subsequent files in this session can be numbered.
        if session_key:
            with session_lock:
                counters = session_filename_counters.setdefault(session_key, {})
                # initialize to 1 meaning the next duplicate will be NAME(1)
                if safe_base not in counters:
                    counters[safe_base] = 1
        return base_candidate

    # base file exists and overwrite not allowed
    # If no session_key, we must skip (respect overwrite_existing = False)
    if not session_key:
        return None

    # If session_key provided, only allow numbering if this session already used the base (i.e. we created it earlier in this session)
    with session_lock:
        counters = session_filename_counters.setdefault(session_key, {})
        # If this base was not created in this session, skip (respect global setting across process boundaries)
        if safe_base not in counters:
            return None

        # Otherwise generate the next numbered filename within this session
        idx = counters.get(safe_base, 1)
        while True:
            candidate = os.path.join(save_folder, f"{safe_base}({idx}){ext}")
            if not os.path.exists(candidate):
                # store next index for future duplicates in this session
                counters[safe_base] = idx + 1
                return candidate
            idx += 1

# ---------------------------
# yt_dlp progress hook
# ---------------------------
def human_readable_size(num, suffix='B'):
    # simple bytes -> human string
    try:
        num = float(num)
    except Exception:
        return "0B"
    for unit in ['','K','M','G','T','P']:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}P{suffix}"


def ytdlp_progress_hook(d):
    """
    yt_dlp progress hook. Wird von yt_dlp aufgerufen, Status in d['status'].
    Mögliche keys: status ('downloading'|'finished'|'error'), downloaded_bytes, total_bytes, eta, speed, filename
    """
    try:
        status = d.get('status')
        filename = d.get('filename') or d.get('info_dict', {}).get('title') or ''
        if status == 'downloading':
            downloaded = d.get('downloaded_bytes') or 0
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            speed = d.get('speed') or 0
            eta = d.get('eta')
            if total:
                pct = downloaded * 100.0 / total
                pct_str = f"{pct:5.1f}%"
            else:
                pct_str = "  ?.%"

            speed_str = f"{human_readable_size(speed)}/s" if speed else "-"
            eta_str = f"{int(eta)}s" if eta else "-"
            # Print a single-line progress (carriage return)
            print(f"\rDownloading: {os.path.basename(filename)} | {pct_str} | {human_readable_size(downloaded)}/{human_readable_size(total) if total else '??'} | {speed_str} | ETA {eta_str}", end='', flush=True)
        elif status == 'finished':
            # finish line with newline
            print()  # finish previous line
            print(f"Finished: {os.path.basename(d.get('filename') or '')} (saved)")
        elif status == 'error':
            print() 
            print(f"Error downloading: {d.get('filename') or ''}")
    except Exception:
        # Fail silently (do not break yt_dlp)
        pass

def get_direct_media_url(entry_obj, entry_url_fallback, quality='best', ydl_instance=None):
    """
    Versucht, aus einem entry-Objekt (wie aus info['entries']) eine konkrete media-URL und Meta zurückzugeben.
    - entry_obj: das entry-Dict (kann fields 'url','formats','requested_formats' etc. enthalten)
    - entry_url_fallback: falls nötig, wird diese URL für re-extraction verwendet
    Returns: (media_url, meta_dict) or (None, {})
    meta_dict keys: ext, filesize, duration, format_id
    """
    meta = {}
    # 1) entry direct url
    if entry_obj.get('url') and isinstance(entry_obj.get('url'), str):
        media_url = entry_obj.get('url')
        meta['ext'] = entry_obj.get('ext') or ''
        meta['filesize'] = entry_obj.get('filesize') or entry_obj.get('filesize_approx')
        meta['duration'] = entry_obj.get('duration')
        return media_url, meta

    # 2) formats list
    if entry_obj.get('formats'):
        formats = entry_obj.get('formats', [])
        # choose best by height then bitrate
        def score(f):
            return ((f.get('height') or 0), (f.get('tbr') or 0))
        formats_sorted = sorted(formats, key=score, reverse=True)
        chosen = formats_sorted[0] if formats_sorted else None
        if chosen:
            media_url = chosen.get('url')
            meta['ext'] = chosen.get('ext') or chosen.get('format_id') or ''
            meta['filesize'] = chosen.get('filesize') or chosen.get('filesize_approx')
            meta['duration'] = chosen.get('duration') or entry_obj.get('duration')
            meta['format_id'] = chosen.get('format_id')
            return media_url, meta

    # 3) requested_formats
    if entry_obj.get('requested_formats'):
        rf = entry_obj.get('requested_formats')[0]
        media_url = rf.get('url')
        meta['ext'] = rf.get('ext') or ''
        meta['filesize'] = rf.get('filesize') or rf.get('filesize_approx')
        meta['duration'] = rf.get('duration')
        return media_url, meta

    # 4) fallback: try to re-extract via provided ydl_instance or temporary one
    try:
        close_temp = False
        if ydl_instance is None:
            import yt_dlp
            ydl_instance = yt_dlp.YoutubeDL({'quiet': True, 'format': quality})
            close_temp = True
        entry_info = None
        try:
            entry_info = ydl_instance.extract_info(entry_url_fallback, download=False)
        except Exception:
            entry_info = None
        if entry_info:
            if entry_info.get('url') and isinstance(entry_info.get('url'), str):
                media_url = entry_info.get('url')
                meta['ext'] = entry_info.get('ext') or ''
                meta['filesize'] = entry_info.get('filesize') or entry_info.get('filesize_approx')
                meta['duration'] = entry_info.get('duration')
                if close_temp:
                    try:
                        ydl_instance.close()
                    except Exception:
                        pass
                return media_url, meta
            if entry_info.get('formats'):
                formats = entry_info.get('formats', [])
                def score2(f): return ((f.get('height') or 0), (f.get('tbr') or 0))
                chosen = sorted(formats, key=score2, reverse=True)[0] if formats else None
                if chosen:
                    media_url = chosen.get('url')
                    meta['ext'] = chosen.get('ext') or chosen.get('format_id') or ''
                    meta['filesize'] = chosen.get('filesize') or chosen.get('filesize_approx')
                    meta['duration'] = chosen.get('duration') or entry_info.get('duration')
                    if close_temp:
                        try:
                            ydl_instance.close()
                        except Exception:
                            pass
                    return media_url, meta
    except Exception:
        pass

    return None, {}

def download_media_url(media_url, target_path, settings, original_page_url=None, max_retries=3):
    """
    Robust download + status:
     - requests streaming mit tqdm wenn Content-Length vorhanden
     - ffmpeg fallback (mit Headern) wenn server 403/401 oder requests scheitert
    Returns True on success, False on failure.
    """
    if not media_url:
        return False

    ua = settings.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    referer = original_page_url or settings.get('last_page_referer') or ''
    headers = {'User-Agent': ua}
    if referer:
        headers['Referer'] = referer

    session = requests.Session()
    session.headers.update(headers)

    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            with session.get(media_url, stream=True, timeout=(10, 60), allow_redirects=True) as r:
                status = r.status_code
                if status == 200:
                    total_size = int(r.headers.get('content-length', 0) or 0)
                    tmp = target_path + ".part"
                    block_size = 1024 * 1024
                    # If we know total size, use tqdm
                    if total_size > 0:
                        with open(tmp, "wb") as fh, tqdm(total=total_size, unit='B', unit_scale=True, desc=os.path.basename(target_path), leave=True) as pbar:
                            for chunk in r.iter_content(chunk_size=block_size):
                                if chunk:
                                    fh.write(chunk)
                                    pbar.update(len(chunk))
                    else:
                        # Unknown total size -> simple progress dots
                        print(f"Downloading (unknown size): {os.path.basename(target_path)} ...", end='', flush=True)
                        with open(tmp, "wb") as fh:
                            for chunk in r.iter_content(chunk_size=block_size):
                                if chunk:
                                    fh.write(chunk)
                        print(" done")
                    # Retry atomic rename if system sleep interrupted
                    try:
                        os.replace(tmp, target_path)
                    except OSError as e:
                        log_error(f"Atomic replace failed: {e}. Retrying in 2s...")
                        time.sleep(2)
                        try:
                            os.replace(tmp, target_path)
                        except Exception as e2:
                            log_error(f"Second attempt to replace temp file failed: {e2}")
                            # Clean up temp if exists
                            try:
                                if os.path.exists(tmp):
                                    os.remove(tmp)
                            except Exception:
                                pass
                            raise

                    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                        return True
                    else:
                        log_error(f"Downloaded file zero-sized or missing after requests: {target_path}")
                        time.sleep(1 + attempt)
                        continue
                elif status in (403, 401):
                    log_info(f"HTTP {status} received for {media_url} - will try ffmpeg fallback (attempt {attempt}).")
                    break  # try ffmpeg next
                else:
                    log_info(f"HTTP {status} for {media_url} - retrying (attempt {attempt})")
                    time.sleep(1 + attempt)
                    continue
        except requests.exceptions.RequestException as e:
            log_info(f"Requests error when downloading {media_url}: {e} - retrying (attempt {attempt})")
            time.sleep(1 + attempt)
            continue

    # ffmpeg fallback
    try:
        print(f"Starting ffmpeg fallback for {os.path.basename(target_path)} ...")
        ff_headers = ""
        ff_headers += f"User-Agent: {ua}\\r\\n"
        if referer:
            ff_headers += f"Referer: {referer}\\r\\n"
        ff_cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-headers", ff_headers,
            "-i", media_url,
            "-c", "copy",
            target_path
        ]
        proc = subprocess.run(ff_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
        if proc.returncode == 0 and os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            print(f"ffmpeg finished: {os.path.basename(target_path)}")
            return True
        else:
            stderr = proc.stderr.decode(errors='ignore') if proc.stderr else ''
            log_error(f"ffmpeg failed (rc={proc.returncode}) for {media_url}. stderr: {stderr[:1000]}")
    except Exception as e:
        log_error(f"ffmpeg invocation error for {media_url}: {e}")

    return False

# ================================
# Main CLI Entry Point
# ================================

def main():
    """Main entry point for the command-line interface."""
    parser = argparse.ArgumentParser(description="Video Downloader")
    parser.add_argument('-l', '--link', help="Direct URL to a video", type=str)
    parser.add_argument('-u', '--urls', help="Comma-separated list of URLs to download", type=str)
    parser.add_argument('-r', '--list', help="Path to a file containing video URLs", type=str)
    parser.add_argument('-p', '--path', help="Path to save downloaded videos", type=str)
    parser.add_argument('-n', '--name', help="Optional name for the downloaded video (single downloads only)", type=str)
    parser.add_argument('-H', '--hidden', help="Hide all console output", action='store_true')
    parser.add_argument('-f', '--force', help="Force the use of yt_dlp for downloading", action='store_true')
    parser.add_argument('-q', '--quality', help="Download quality (e.g. best, worst, 720p)", type=str)
    
    # Configuration-related arguments
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--config', action='store_true', help="Open the configuration file")
    group.add_argument('--list-config', action='store_true', help="Display current configuration settings")
    group.add_argument('--example-config', action='store_true', help="Generate an example configuration file")
    
    args = parser.parse_args()
    settings = load_settings(SETTINGS_PATH)
    hidden_output = is_output_hidden(settings, args)
    browser_path = settings.get('browser_path')
    minimize_browser = settings.get('minimized', 'false').lower() == 'true'
    overwrite_existing = settings.get('overwrite_existing', 'false').lower() == 'true'
    quality = args.quality or settings.get('default_quality', 'best')

    # Determine default save folder based on settings/use of -p
    if args.path:
        save_folder = args.path
    else:
        if settings.get('use_cwd_as_default', 'false').lower() == 'true':
            save_folder = os.getcwd()
        else:
            save_folder = DEFAULT_DOWNLOAD_DIR
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    if args.config or args.list_config or args.example_config:
        handle_config(args)
        return

    if not browser_path or not os.path.exists(browser_path):
        print("Error: The specified browser path is invalid or does not exist.")
        return

    # Gather URLs from --link, --urls, or --list
    url_list = []
    if args.link:
        url_list.append(args.link.strip())
    if args.urls:
        url_list += [u.strip() for u in args.urls.split(',') if u.strip()]
    if args.list:
        try:
            with open(args.list, 'r') as f:
                url_list += [line.strip() for line in f if line.strip()]
        except Exception as e:
            log_error(f"Error reading list file: {e}")
            print_if_not_ignored(f"Error reading list file: {e}", settings)
            return

    if not url_list:
        print("Error: Either a link, URLs, or a list must be specified.")
        parser.print_help()
        return

    # Download each URL
    for idx, url in enumerate(url_list):
        if stop_download.is_set():
            break
        if len(url_list) == 1:
            start_time = time.time()
            final_path = download_video_from_page(url, browser_path, save_folder, 0, 1, minimize_browser, overwrite_existing, custom_name=args.name, force=args.force, quality=quality)
            elapsed_time = time.time() - start_time
            if final_path:
                print(f"Download completed in {elapsed_time:.2f} seconds: {final_path}")
            else:
                print(f"Download failed in {elapsed_time:.2f} seconds.")
        else:
            print_if_not_ignored(f"\n[{idx+1}/{len(url_list)}] Starting download for: {url}", settings)
            start_time = time.time()
            final_path = download_video_from_page(url, browser_path, save_folder, idx, len(url_list), minimize_browser, overwrite_existing, force=args.force, quality=quality)
            elapsed_time = time.time() - start_time
            if final_path:
                print(f"Download completed in {elapsed_time:.2f} seconds: {final_path}")
            else:
                print(f"Download failed in {elapsed_time:.2f} seconds.")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda sig, frame: stop_download.set())
    main()