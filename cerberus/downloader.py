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
    from .ui import print_info, print_success, print_error, print_header, ask_for_name
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
    from ui import print_info, print_success, print_error, print_header, ask_for_name

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
                             force=False, quality=None, limit_rate=None, settings_dict=None, threads=1):
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
        final_path = ytdlp.download_with_youtube_dl(
            video_url=url, 
            save_folder=save_folder, 
            custom_name=custom_name, 
            quality=quality, 
            limit_rate=limit_rate, 
            settings_dict=settings_dict
        )
    else:
        for attempt in range(3):
            if attempt < 2:
                print_info(f"Selenium attempt {attempt+1} of 2...")
                wait_time = int(settings.get('selenium_wait_time', 5))
                try:
                    raw_name, unique_video_links = selenium.intercept_media_url(url, browser_path, minimize_browser, cookies=ng_cookies, wait_time=wait_time)
                    
                    if unique_video_links:
                        # Improved deduplication: Normalize URLs and filter duplicates
                        final_links = []
                        seen_clean = set()
                        for l in unique_video_links:
                            # Strip tokens, session IDs, and known generic prefixes
                            clean_l = l.split('?')[0].split('#')[0]
                            if clean_l not in seen_clean:
                                seen_clean.add(clean_l)
                                final_links.append(l)
                        
                        video_name = sanitize_filename(raw_name)
                        downloaded_any = False

                        for idx, video_url_found in enumerate(final_links):
                            if downloaded_any:
                                break
                                
                            # Add thread count to progress hook if in parallel mode
                            n_threads_str = f"Thread Pool: {threads}" if threads > 1 else ""
                            
                            # We wrap the hook to inject thread info
                            def hooked_progress(d):
                                d['n_threads'] = n_threads_str
                                ytdlp.ytdlp_progress_hook(d)

                            # Interactive Naming Prompt
                            entry_custom_name = custom_name
                            if entry_custom_name == "__INTERACTIVE__":
                                # Use video_name (scraped from page) as reference
                                prompt_title = video_name
                                if len(final_links) > 1:
                                    prompt_title += f" [Part {idx+1}]"
                                entry_custom_name = ask_for_name(prompt_title)

                            if entry_custom_name:
                                base_raw = entry_custom_name[:-4] if entry_custom_name.lower().endswith(".mp4") else entry_custom_name
                                base = sanitize_filename(base_raw)
                                if len(final_links) > 1 and entry_custom_name == custom_name:
                                    # Only index if it was a global bulk name. 
                                    # If user typed it interactively, they might have included the index.
                                    candidate = os.path.join(save_folder, f"{base}({idx+1}).mp4")
                                else:
                                    candidate = os.path.join(save_folder, f"{base}.mp4")
                                if os.path.exists(candidate) and not overwrite_existing:
                                    print_info(f"Skipping existing file: {candidate}")
                                    continue
                                current_save_path = candidate
                                ok = ytdlp.download_media_url(
                                    media_url=video_url_found, 
                                    target_path=current_save_path, 
                                    settings=settings, 
                                    original_page_url=url, 
                                    limit_rate=limit_rate, 
                                    progress_hooks=[hooked_progress]
                                )
                                if not ok:
                                    current_save_path = ytdlp.download_with_youtube_dl(
                                        video_url=video_url_found, 
                                        save_folder=save_folder, 
                                        custom_name=base, 
                                        quality=quality, 
                                        session_key=url, 
                                        overwrite_existing=overwrite_existing, 
                                        limit_rate=limit_rate, 
                                        settings_dict=settings_dict, 
                                        progress_hooks=[hooked_progress]
                                    )
                                if current_save_path:
                                    downloaded_any = True
                                    final_path = current_save_path
                            else:
                                resolved = resolve_available_filename(save_folder, video_name, ext=".mp4", overwrite_existing=overwrite_existing, session_key=url)
                                if resolved is None:
                                    # This happens if it was already skipped once in this session or exists without session key
                                    # Check if the base file exists
                                    base_file = os.path.join(save_folder, f"{video_name}.mp4")
                                    if os.path.exists(base_file) and not overwrite_existing:
                                         print_info(f"Skipping existing file: {base_file}")
                                    continue
                                
                                # We wrap the hook to inject thread info
                                def hooked_progress(d):
                                    d['n_threads'] = n_threads_str
                                    ytdlp.ytdlp_progress_hook(d)

                                ok = ytdlp.download_media_url(
                                    media_url=video_url_found, 
                                    target_path=resolved, 
                                    settings=settings, 
                                    original_page_url=url, 
                                    limit_rate=limit_rate, 
                                    progress_hooks=[hooked_progress]
                                )
                                if not ok:
                                    final_from_ydl = ytdlp.download_with_youtube_dl(
                                        video_url=video_url_found, 
                                        save_folder=save_folder, 
                                        custom_name=None, 
                                        quality=quality, 
                                        session_key=url, 
                                        overwrite_existing=overwrite_existing, 
                                        limit_rate=limit_rate, 
                                        settings_dict=settings_dict, 
                                        progress_hooks=[hooked_progress]
                                    )
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
                final_path = ytdlp.download_with_youtube_dl(
                    video_url=url, 
                    save_folder=save_folder, 
                    custom_name=custom_name, 
                    quality=quality, 
                    limit_rate=limit_rate, 
                    settings_dict=settings_dict
                )

    if final_path:
        run_post_processing_hook(final_path, url, settings)
    
    return final_path

def download_videos_from_list(url_items, browser_path, save_folder, minimize_browser, overwrite_existing, force=False, quality=None, limit_rate=None, settings_dict=None, threads=1, custom_name=None):
    """Downloads multiple videos from a list of URL items (dict with 'url' and optional 'name')."""
    settings = settings_dict if settings_dict is not None else load_settings(SETTINGS_PATH)
    
    # Manage queue if not in library mode
    queue = None
    if settings_dict is None:
        queue = load_queue()
        # Filter out already completed
        url_items = [item for item in url_items if item["url"] not in queue["completed"]]
        
        # Deduplicate the list to prevent parallel threads from starting same URL
        seen_urls = set()
        unique_items = []
        for item in url_items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                unique_items.append(item)
        url_items = unique_items
        
        queue["urls"] = [item["url"] for item in url_items]
        save_queue(queue)

    total_videos = len(url_items)

    def download_task(item_info):
        index, item = item_info
        url = item["url"]
        item_name = item.get("name") # Name from list (URL:::Name)
        
        if stop_download.is_set():
            return None

        # Priority: 1. Name from list | 2. Global -n argument | 3. Original
        final_custom_name = item_name or custom_name

        print_header(f"Starting {index + 1}/{total_videos}")
        if final_custom_name == "__INTERACTIVE__":
            print_info(f"URL: {url} (Interactive Mode)")
        elif final_custom_name:
            print_info(f"URL: {url} (Custom Name: {final_custom_name})")
        else:
            print_info(f"URL: {url}")
        
        start_time = time.time()
        final_path = download_video_from_page(
            url=url, 
            browser_path=browser_path, 
            save_folder=save_folder, 
            video_index=index,
            total_videos=total_videos, 
            minimize_browser=minimize_browser, 
            overwrite_existing=overwrite_existing,
            custom_name=final_custom_name,
            force=force, 
            quality=quality, 
            limit_rate=limit_rate,
            settings_dict=settings_dict, 
            threads=threads
        )
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
            list(executor.map(download_task, enumerate(url_items)))
    else:
        for item in enumerate(url_items):
            if stop_download.is_set():
                break
            download_task(item)

    if queue and not stop_download.is_set() and not url_items:
        # Clear queue on successful completion
        if os.path.exists(QUEUE_PATH):
            os.remove(QUEUE_PATH)
