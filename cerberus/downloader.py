# cerberus/downloader.py

import os
import threading
import requests
import logging
import time
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor

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
    from .ui import print_info, print_success, print_error, print_header
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
    from ui import print_info, print_success, print_error, print_header

# ================================
# Logging Setup
# ================================
logger = logging.getLogger("cerberus")

QUEUE_PATH = os.path.join(CONFIG_DIR, "queue.json")

def load_queue():
    if os.path.exists(QUEUE_PATH):
        try:
            with open(QUEUE_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            log_error(f"Error loading queue: {e}")
    return {"urls": [], "completed": []}

def save_queue(queue):
    try:
        with open(QUEUE_PATH, 'w') as f:
            json.dump(queue, f, indent=4)
    except Exception as e:
        log_error(f"Error saving queue: {e}")

def run_post_processing_hook(final_path, url, settings):
    command_template = settings.get('post_download_command')
    if not command_template:
        return

    try:
        command = command_template.format(
            file_path=final_path,
            filename=os.path.basename(final_path),
            url=url
        )
        print_info(f"Running post-processing command: {command}")
        subprocess.run(command, shell=True, check=True)
        print_success("Post-processing completed.")
    except Exception as e:
        print_error(f"Post-processing failed: {e}")

def download_video_from_page(url, browser_path, save_folder, video_index, total_videos,
                             minimize_browser, overwrite_existing, custom_name=None, 
                             force=False, quality=None, limit_rate=None, settings_dict=None):
    """
    Attempts to download a video from a webpage. Supports settings_dict for library use.
    """
    settings = settings_dict if settings_dict is not None else load_settings(SETTINGS_PATH)
    
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

    final_path = None

    # If force or known host, use yt_dlp directly
    if force or any(host in url for host in known_hosts):
        final_path = ytdlp.download_with_youtube_dl(url, save_folder, custom_name, quality, limit_rate=limit_rate, settings_dict=settings_dict)
    else:
        for attempt in range(3):
            if attempt < 2:
                print_info(f"Selenium attempt {attempt+1} of 2...")
                wait_time = int(settings.get('selenium_wait_time', 5))
                try:
                    raw_name, unique_video_links = selenium.intercept_media_url(url, browser_path, minimize_browser, cookies=ng_cookies, wait_time=wait_time)
                    
                    if unique_video_links:
                        # Improved deduplication: Normalize URLs and filter duplicates
                        seen_clean = set()
                        final_links = []
                        for l in unique_video_links:
                            clean_l = l.split('?')[0] if '?' in l else l
                            if clean_l not in seen_clean:
                                seen_clean.add(clean_l)
                                final_links.append(l)
                        
                        video_name = sanitize_filename(raw_name)
                        downloaded_any = False

                        for idx, video_url_found in enumerate(final_links):
                            if custom_name:
                                base_raw = custom_name[:-4] if custom_name.lower().endswith(".mp4") else custom_name
                                base = sanitize_filename(base_raw)
                                if len(final_links) > 1:
                                    candidate = os.path.join(save_folder, f"{base}({idx+1}).mp4")
                                else:
                                    candidate = os.path.join(save_folder, f"{base}.mp4")
                                if os.path.exists(candidate) and not overwrite_existing:
                                    continue
                                current_save_path = candidate
                                ok = ytdlp.download_media_url(video_url_found, current_save_path, settings, original_page_url=url, limit_rate=limit_rate)
                                if not ok:
                                    current_save_path = ytdlp.download_with_youtube_dl(video_url_found, save_folder, custom_name=base, quality=quality, session_key=url, overwrite_existing=overwrite_existing, limit_rate=limit_rate, settings_dict=settings_dict)
                                if current_save_path:
                                    downloaded_any = True
                                    final_path = current_save_path
                            else:
                                resolved = resolve_available_filename(save_folder, video_name, ext=".mp4", overwrite_existing=overwrite_existing, session_key=url)
                                if resolved is None:
                                    continue
                                ok = ytdlp.download_media_url(video_url_found, resolved, settings, original_page_url=url, limit_rate=limit_rate)
                                if not ok:
                                    # Use the found video URL for yt_dlp instead of the page URL to avoid duplicates if possible
                                    final_from_ydl = ytdlp.download_with_youtube_dl(video_url_found, save_folder, custom_name=None, quality=quality, session_key=url, overwrite_existing=overwrite_existing, limit_rate=limit_rate, settings_dict=settings_dict)
                                    if final_from_ydl:
                                        downloaded_any = True
                                        final_path = final_from_ydl
                                else:
                                    downloaded_any = True
                                    final_path = resolved

                        if downloaded_any:
                            break
                    else:
                        print_info("No video links found. Retrying...")
                except Exception as e:
                    log_error(f"Error during Selenium interception: {e}")
            else:
                print_info("Selenium attempts failed - falling back to yt_dlp (attempt 3)...")
                final_path = ytdlp.download_with_youtube_dl(url, save_folder, custom_name, quality, limit_rate=limit_rate, settings_dict=settings_dict)

    if final_path:
        run_post_processing_hook(final_path, url, settings)
    
    return final_path

def download_videos_from_list(urls, browser_path, save_folder, minimize_browser, overwrite_existing, force=False, quality=None, limit_rate=None, settings_dict=None, threads=1):
    """Downloads multiple videos from a list of URLs."""
    settings = settings_dict if settings_dict is not None else load_settings(SETTINGS_PATH)
    
    # Manage queue if not in library mode
    queue = None
    if settings_dict is None:
        queue = load_queue()
        queue["urls"] = [u for u in urls if u not in queue["completed"]]
        save_queue(queue)

    urls_to_download = [u for u in urls if not queue or u not in queue["completed"]]
    total_videos = len(urls_to_download)

    def download_task(url_info):
        index, url = url_info
        if stop_download.is_set():
            return None

        print_header(f"Starting {index + 1}/{total_videos}")
        print_info(f"URL: {url}")
        
        start_time = time.time()
        final_path = download_video_from_page(url, browser_path, save_folder, index,
                                              total_videos, minimize_browser, overwrite_existing,
                                              force=force, quality=quality, limit_rate=limit_rate,
                                              settings_dict=settings_dict)
        elapsed_time = time.time() - start_time
        
        if final_path:
            print_success(f"Completed in {elapsed_time:.2f}s: {os.path.basename(final_path)}")
            if queue:
                with session_lock: # Ensure thread-safe queue updates
                    if url not in queue["completed"]:
                        queue["completed"].append(url)
                        save_queue(queue)
        else:
            print_error(f"Failed in {elapsed_time:.2f}s: {url}")
        return final_path

    if threads > 1:
        print_info(f"Downloading with {threads} parallel threads...")
        with ThreadPoolExecutor(max_workers=threads) as executor:
            list(executor.map(download_task, enumerate(urls_to_download)))
    else:
        for item in enumerate(urls_to_download):
            if stop_download.is_set():
                break
            download_task(item)

    if queue and not stop_download.is_set() and not urls_to_download:
        # Clear queue on successful completion
        if os.path.exists(QUEUE_PATH):
            os.remove(QUEUE_PATH)
