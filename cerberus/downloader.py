# cerberus/downloader.py

import os
import threading
import requests
import logging
import time

# Modular Imports
try:
    from .config import (
        CONFIG_DIR, SETTINGS_PATH, LOG_PATH, DEFAULT_DOWNLOAD_DIR,
        get_config_dir, detect_browser_path, load_settings, build_settings, 
        handle_config, get_default_download_dir
    )
    from .utils import (
        log_info, log_error, custom_print, sanitize_filename,
        resolve_available_filename, human_readable_size,
        session_lock, session_filename_counters, print_if_not_ignored
    )
    from .events import stop_download
    from .adapters import ytdlp
    from .adapters import selenium
except (ImportError, ValueError):
    from config import (
        CONFIG_DIR, SETTINGS_PATH, LOG_PATH, DEFAULT_DOWNLOAD_DIR,
        get_config_dir, detect_browser_path, load_settings, build_settings, 
        handle_config, get_default_download_dir
    )
    from utils import (
        log_info, log_error, custom_print, sanitize_filename,
        resolve_available_filename, human_readable_size,
        session_lock, session_filename_counters, print_if_not_ignored
    )
    from events import stop_download
    import adapters.ytdlp as ytdlp
    import adapters.selenium as selenium

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
                session_req = requests.Session()
                login_payload = {'username': ng_user, 'password': ng_pass}
                try:
                    session_req.post("https://www.newgrounds.com/login", data=login_payload)
                    ng_cookies = session_req.cookies
                except Exception as e:
                    log_error(f"Error performing Newgrounds login: {e}")
                    ng_cookies = None

    # If force or known host, use yt_dlp directly
    if force or any(host in url for host in known_hosts):
        return ytdlp.download_with_youtube_dl(url, save_folder, custom_name, quality)

    for attempt in range(3):
        if attempt < 2:
            print_if_not_ignored(f"\nSelenium attempt {attempt+1} of 2...", settings)
            wait_time = int(settings.get('selenium_wait_time', 5))
            try:
                raw_name, unique_video_links = selenium.intercept_media_url(url, browser_path, minimize_browser, cookies=ng_cookies, wait_time=wait_time)
                
                if unique_video_links:
                    video_name = sanitize_filename(raw_name)
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
                            ok = ytdlp.download_media_url(video_url_found, current_save_path, settings, original_page_url=url)
                            
                            if not ok:
                                # fallback to yt_dlp single-download
                                current_save_path = ytdlp.download_with_youtube_dl(video_url_found, save_folder, custom_name=base, quality=quality, session_key=url, overwrite_existing=overwrite_existing)
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
                            ok = ytdlp.download_media_url(video_url_found, resolved, settings, original_page_url=url)
                            if not ok:
                                # fallback: yt_dlp (will use session_key=url internally)
                                final_from_ydl = ytdlp.download_with_youtube_dl(url, save_folder, custom_name=None, quality=quality, session_key=url, overwrite_existing=overwrite_existing)
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
            except Exception as e:
                log_error(f"Error during Selenium interception: {e}")
                print_if_not_ignored(f"Error during Selenium interception: {e}", settings)
        else:
            print_if_not_ignored("\nSelenium attempts failed - falling back to yt_dlp (attempt 3)...", settings)
            return ytdlp.download_with_youtube_dl(url, save_folder, custom_name, quality)

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
                # We can't know the video name yet without visiting the page, 
                # but we can check if a generic video_N.mp4 exists if we were to use that.
                # Actually, download_video_from_page handles its own existence checks.
                video_save_paths.append(url)

        for video_index, url in enumerate(video_save_paths):
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

