import os
import time
import json
import subprocess
import threading
import requests
import yt_dlp
import shutil
import random
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# Global progress bar instance for library-wide access
rich_progress = None
rich_tasks = {}
rich_lock = threading.Lock()

try:
    from ..config import SETTINGS_PATH, load_settings, get_default_download_dir
    from ..utils import (
        log_info, log_error, sanitize_filename, resolve_available_filename,
        human_readable_size, print_if_not_ignored, interaction_lock
    )
    from ..events import stop_download
    from ..ui import create_progress_bar, ask_for_name
except (ImportError, ValueError):
    from config import SETTINGS_PATH, load_settings, get_default_download_dir
    from utils import (
        log_info, log_error, sanitize_filename, resolve_available_filename,
        human_readable_size, print_if_not_ignored, interaction_lock
    )
    from events import stop_download
    from ui import create_progress_bar, ask_for_name

def get_progress_bar():
    global rich_progress
    # Wait if an interactive naming prompt is active
    with interaction_lock:
        with rich_lock:
            if rich_progress is None:
                rich_progress = create_progress_bar()
                rich_progress.start()
    return rich_progress

def stop_progress_bar():
    global rich_progress
    if rich_progress is not None:
        try:
            rich_progress.stop()
        except Exception:
            pass
        rich_progress = None
        rich_tasks.clear()

def get_yt_dlp_browser(browser_path):
    """Maps browser path to yt-dlp browser name."""
    if not browser_path:
        return 'chrome'
    path_lower = browser_path.lower()
    if 'brave' in path_lower:
        return 'brave'
    if 'chrome' in path_lower:
        return 'chrome'
    if 'chromium' in path_lower:
        return 'chromium'
    if 'firefox' in path_lower:
        return 'firefox'
    if 'opera' in path_lower:
        return 'opera'
    if 'edge' in path_lower:
        return 'edge'
    if 'safari' in path_lower:
        return 'safari'
    if 'vivaldi' in path_lower:
        return 'vivaldi'
    return 'chrome'

def ytdlp_progress_hook(d):
    """
    yt_dlp progress hook using Rich for professional parallel output.
    """
    progress = get_progress_bar()
    filename = os.path.basename(d.get('filename', 'video'))
    
    try:
        status = d.get('status')
        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes') or 0
            
            with rich_lock:
                if filename not in rich_tasks:
                    rich_tasks[filename] = progress.add_task(
                        f"[cyan]Downloading {filename[:30]}...", 
                        total=total,
                        threads=d.get('n_threads', '')
                    )
                task_id = rich_tasks[filename]

                progress.update(task_id, completed=downloaded, total=total, threads=d.get('n_threads', ''))
        elif status == 'finished':
            with rich_lock:
                if filename in rich_tasks:
                    task_id = rich_tasks[filename]
                    progress.update(task_id, completed=d.get('total_bytes', 0), threads=d.get('n_threads', ''))
                    # Remove task after completion to keep HUD clean in multithreading
                    progress.remove_task(task_id)
                    del rich_tasks[filename]
            
        elif status == 'error':
            with rich_lock:
                if filename in rich_tasks:
                    progress.stop_task(rich_tasks[filename])
    except Exception as e:
        log_error(f"Error in Rich progress hook: {e}")

def parse_rate_limit(rate_str):
    """Parses strings like '500K', '1M' into bytes per second."""
    if not rate_str:
        return None
    try:
        rate_str = rate_str.upper().strip()
        units = {'K': 1024, 'M': 1024*1024, 'G': 1024*1024*1024}
        if rate_str[-1] in units:
            return int(float(rate_str[:-1]) * units[rate_str[-1]])
        return int(rate_str)
    except Exception:
        return None

def get_direct_media_url(entry_obj, entry_url_fallback, quality='best', ydl_instance=None):
    """
    Versucht, aus einem entry-Objekt eine konkrete media-URL und Meta zurückzugeben.
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

    # 4) fallback: try to re-extract
    try:
        close_temp = False
        if ydl_instance is None:
            ydl_instance = yt_dlp.YoutubeDL({'quiet': True, 'format': quality})
            close_temp = True
        entry_info = None
        try:
            entry_info = get_info_with_retry(entry_url_fallback, max_retries=3)
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

def get_info_with_retry(video_url, settings_dict=None, max_retries=5):
    """Extracts metadata with exponential backoff for 429 errors."""
    settings = settings_dict if settings_dict is not None else load_settings(SETTINGS_PATH)
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
    }
    if 'youtube.com' in video_url or 'youtu.be' in video_url:
        if settings.get('use_browser_cookies', 'false').lower() == 'true':
            browser_name = get_yt_dlp_browser(settings.get('browser_path'))
            opts['cookiesfrombrowser'] = (browser_name,)
    
    for attempt in range(max_retries):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(video_url, download=False)
        except Exception as e:
            e_str = str(e)
            if "429" in e_str or "Too Many Requests" in e_str:
                wait_time = (2 ** attempt) * 15 + random.randint(1, 30)
                log_info(f"Extraction Rate Limited (429) for {video_url}. Backing off for {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                continue
            log_error(f"Error fetching info for {video_url}: {e}")
            break
    return None

def get_info(video_url, settings_dict=None):
    """Extracts metadata without downloading (alias for get_info_with_retry)."""
    return get_info_with_retry(video_url, settings_dict=settings_dict)

def download_media_url(media_url, target_path, settings, original_page_url=None, max_retries=3, limit_rate=None, progress_hooks=None):
    """
    Robust download + unified progress reporting with bandwidth limiting.
    """
    if not media_url:
        return False

    hooks = progress_hooks or [ytdlp_progress_hook]
    
    ua = settings.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    referer = original_page_url or settings.get('last_page_referer') or ''
    headers = {'User-Agent': ua}
    if referer:
        headers['Referer'] = referer

    # Parse rate limit
    bytes_per_second = parse_rate_limit(limit_rate)

    session = requests.Session()
    session.headers.update(headers)

    tmp = target_path + ".part"
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            with session.get(media_url, stream=True, timeout=(10, 60), allow_redirects=True) as r:
                status = r.status_code
                if status == 200:
                    ctype = r.headers.get('Content-Type', '').lower()
                    if 'text/html' in ctype or 'text/plain' in ctype:
                         log_error(f"URL returned {ctype} instead of media for {os.path.basename(target_path)}. Extraction likely failed.")
                         return False

                    total_size = int(r.headers.get('content-length', 0) or 0)
                    
                    # Resume logic
                    downloaded = 0
                    mode = "wb"
                    headers_resume = headers.copy()
                    
                    if os.path.exists(tmp):
                        downloaded = os.path.getsize(tmp)
                        if 0 < downloaded < total_size:
                            headers_resume['Range'] = f"bytes={downloaded}-"
                            mode = "ab"
                            log_info(f"Resuming download from byte {downloaded} for {os.path.basename(target_path)}")
                        else:
                            downloaded = 0 # Restart if file is same size or larger (corruption?)

                    # Re-request with range if needed
                    if mode == "ab":
                        r.close()
                        r = session.get(media_url, stream=True, timeout=(10, 60), headers=headers_resume)
                        # Check if server supports range
                        if r.status_code != 206:
                            log_info("Server does not support Range requests, restarting download.")
                            mode = "wb"
                            downloaded = 0

                    block_size = 1024 * 1024
                    start_time = time.time()

                    # Ensure parent dir exists
                    parent = os.path.dirname(target_path)
                    if parent:
                        os.makedirs(parent, exist_ok=True)

                    with open(tmp, mode) as fh:
                        for chunk in r.iter_content(chunk_size=block_size):
                            if stop_download.is_set():
                                break
                            if not chunk:
                                continue
                            
                            chunk_start = time.time()
                            fh.write(chunk)
                            downloaded += len(chunk)

                            # Bandwidth limiting
                            if bytes_per_second:
                                elapsed = time.time() - chunk_start
                                expected_time = len(chunk) / bytes_per_second
                                if elapsed < expected_time:
                                    time.sleep(expected_time - elapsed)

                            # Build progress dict compatible with ytdlp_progress_hook
                            progress_dict = {
                                'status': 'downloading',
                                'filename': os.path.basename(target_path),
                                'downloaded_bytes': downloaded,
                                'total_bytes': total_size,
                            }
                            try:
                                for h in hooks:
                                    h(progress_dict)
                            except Exception:
                                pass
                    
                    if stop_download.is_set():
                        # Do not remove .part file on stop, allow resume
                        return False

                    # Atomic replace
                    try:
                        if not os.path.exists(tmp):
                             log_error(f"Part file disappeared before replace: {tmp}")
                             return False
                        os.replace(tmp, target_path)
                    except OSError as e:
                        log_error(f"Atomic replace failed: {e}. Retrying in 2s...")
                        time.sleep(2)
                        try:
                            if os.path.exists(tmp):
                                os.replace(tmp, target_path)
                            else:
                                 log_error(f"Part file missing on retry replace: {tmp}")
                                 return False
                        except Exception as e2:
                            log_error(f"Second attempt to replace temp file failed: {e2}")
                            raise

                    # Verify file and call finished hook
                    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                        try:
                            for h in hooks:
                                h({'status': 'finished', 'filename': os.path.basename(target_path)})
                        except Exception:
                            pass
                        return True
                    else:
                        log_error(f"Downloaded file zero-sized or missing after requests: {target_path}")
                        time.sleep(1 + attempt)
                        continue

                elif status == 429:
                    # Enhanced exponential backoff for rate limiting
                    # Randomized to prevent thundering herd
                    wait_time = (2 ** attempt) * 10 + random.randint(1, 15)
                    log_info(f"HTTP 429 (Too Many Requests) for {os.path.basename(target_path)}. Backing off for {wait_time}s... (Attempt {attempt}/{max_retries})")
                    time.sleep(wait_time)
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

    # Verify file and call finished hook
    if os.path.exists(target_path):
        fsize = os.path.getsize(target_path)
        # 20KB minimum (more conservative)
        if fsize > 20480:
            try:
                for h in hooks:
                    h({'status': 'finished', 'filename': os.path.basename(target_path)})
            except Exception:
                pass
            return True
        else:
            log_error(f"Downloaded file too small ({fsize} bytes), likely corrupted. Deleting: {target_path}")
            try:
                os.remove(target_path)
            except Exception:
                pass

    # ffmpeg fallback (Only if not a 429/rate-limiting issue)
    # Status 401/403 might be bypassable by ffmpeg's different network stack
    try:
        if attempt >= max_retries:
             log_error(f"Max retries reached for {media_url}. Skipping ffmpeg fallback to avoid further rate limiting.")
             return False

        try:
            for h in hooks:
                h({'status': 'downloading', 'filename': os.path.basename(target_path), 'downloaded_bytes': 0, 'total_bytes': 0, 'speed': 0, 'eta': None})
        except Exception:
            pass

        log_info(f"Starting ffmpeg fallback for {os.path.basename(target_path)} ...")
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
        
        if proc.returncode == 0 and os.path.exists(target_path) and os.path.getsize(target_path) > 10240:
            try:
                for h in hooks:
                    h({'status': 'finished', 'filename': os.path.basename(target_path)})
            except Exception:
                pass
            log_info(f"ffmpeg finished successfully: {os.path.basename(target_path)}")
            return True
        else:
            stderr = proc.stderr.decode(errors='ignore') if proc.stderr else ''
            # Clean up potentially corrupted file
            if os.path.exists(target_path):
                os.remove(target_path)
            log_error(f"ffmpeg failed or produced empty file (rc={proc.returncode}) for {media_url}. stderr: {stderr[:500]}")
    except Exception as e:
        log_error(f"ffmpeg invocation error for {media_url}: {e}")

    return False

def sort_downloaded_file(file_path, original_url, settings):
    """
    Moves downloaded file into a subfolder based on 'sort_by' setting.
    """
    sort_by = settings.get('sort_by', 'none').lower()
    if sort_by == 'none':
        return file_path

    # Determine base download directory
    base_dir = get_default_download_dir(settings)

    platform_folder = None
    artist_folder = None
    genre_folder = None

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

    if sort_by == "platform":
        if soup:
            og_site = soup.find("meta", property="og:site_name")
            if og_site and og_site.get("content"):
                platform_folder = og_site["content"].strip().lower().replace(" ", "_")
        if not platform_folder:
            domain = urlparse(original_url).netloc
            platform_folder = domain.replace("www.", "").split(".")[0].lower()
        dest_dir = os.path.join(base_dir, platform_folder)
    elif sort_by == "artist":
        if soup:
            author_meta = soup.find("meta", attrs={"name": "author"})
            if author_meta and author_meta.get("content"):
                artist_folder = author_meta["content"].strip().lower().replace(" ", "_")
        if not artist_folder:
            artist_folder = "unknown_artist"
        dest_dir = os.path.join(base_dir, artist_folder)
    elif sort_by == "genre":
        if soup:
            genre_meta = soup.find("meta", attrs={"name": "genre"})
            if genre_meta and genre_meta.get("content"):
                genre_folder = genre_meta["content"].strip().lower().replace(" ", "_")
        if not genre_folder:
            genre_folder = "unknown_genre"
        dest_dir = os.path.join(base_dir, genre_folder)
    else:
        dest_dir = base_dir

    try:
        os.makedirs(dest_dir, exist_ok=True)
        new_path = os.path.join(dest_dir, os.path.basename(file_path))
        shutil.move(file_path, new_path)
        return new_path
    except Exception as e:
        log_error(f"Error moving file to sorted folder: {e}")
        return file_path

def download_with_youtube_dl(video_url, save_folder, custom_name=None, quality=None, session_key=None, overwrite_existing=None, limit_rate=None, settings_dict=None, progress_hooks=None):
    """
    Public entry point for yt_dlp download. Supports settings_dict for library use.
    """
    settings = settings_dict if settings_dict is not None else load_settings(SETTINGS_PATH)
    
    yt_verbose = settings.get('yt_verbose', 'false').lower() == 'true'
    if quality is None:
        quality = settings.get('default_quality', 'best')
    if overwrite_existing is None:
        overwrite_existing = settings.get('overwrite_existing', 'false').lower() == 'true'

    # Common options for yt_dlp
    common_opts = {
        'format': quality,
        'quiet': not yt_verbose,
        'no_warnings': True,
        'useragent': settings.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'),
        'socket_timeout': int(settings.get('socket_timeout', 60)),
        'retries': int(settings.get('retries', 10)),
        'ratelimit': parse_rate_limit(limit_rate),
        'progress_hooks': progress_hooks or [ytdlp_progress_hook],
    }
    
    if 'youtube.com' in video_url or 'youtu.be' in video_url:
        if settings.get('use_browser_cookies', 'false').lower() == 'true':
            browser_name = get_yt_dlp_browser(settings.get('browser_path'))
            common_opts['cookiesfrombrowser'] = (browser_name,)

    if settings.get('cookies_file'):
        common_opts['cookiefile'] = settings['cookies_file']
    if settings.get('proxy'):
        common_opts['proxy'] = settings['proxy']
    if settings.get('ignoreerrors', 'false').lower() == 'true':
        common_opts['ignoreerrors'] = True

    info = get_info_with_retry(video_url, settings_dict=settings_dict)

    base_title = None
    if custom_name:
        base_title = custom_name[:-4] if custom_name.lower().endswith(".mp4") else custom_name
    else:
        if info:
            base_title = info.get('title') or info.get('fulltitle') or info.get('id')
    if not base_title:
        base_title = "video"

    if info and info.get('entries'):
        raw_entries = [e for e in info.get('entries') if e]
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

        ydl_for_info = yt_dlp.YoutubeDL(common_opts)
        media_seen = set()
        final_paths = []

        for idx, entry in enumerate(unique_entries):
            entry_url = entry.get('webpage_url') or entry.get('url') or video_url
            media_url, meta = get_direct_media_url(entry, entry_url, quality=quality, ydl_instance=ydl_for_info)

            used_fallback_ydl_download = False
            if not media_url:
                used_fallback_ydl_download = True

            dedupe_key = media_url if media_url else (entry.get('id') or entry.get('webpage_url') or entry.get('url'))
            if dedupe_key in media_seen:
                continue
            media_seen.add(dedupe_key)

            # If custom_name was provided, we use base_title (which is derived from custom_name)
            # If it's a playlist/album, we append an index to avoid all videos having same name.
            if custom_name == "__INTERACTIVE__":
                entry_title_orig = entry.get('title') or base_title
                entry_custom = ask_for_name(entry_title_orig)
                if entry_custom:
                    entry_title = entry_custom
                else:
                    entry_title = entry_title_orig
            elif custom_name:
                if len(unique_entries) > 1:
                    entry_title = f"{base_title}({idx+1})"
                else:
                    entry_title = base_title
            else:
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
                ok = download_media_url(
                    media_url=media_url, 
                    target_path=target_path, 
                    settings=settings, 
                    original_page_url=entry_url,
                    progress_hooks=progress_hooks
                )
                if not ok:
                    used_fallback_ydl_download = True
                else:
                    saved_path = target_path

            if used_fallback_ydl_download:
                ydl_opts_entry = common_opts.copy()
                ydl_opts_entry.update({
                    'outtmpl': target_path,
                    'noplaylist': True,
                    'progress_hooks': progress_hooks or [ytdlp_progress_hook],
                    'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
                })
                try:
                    with yt_dlp.YoutubeDL(ydl_opts_entry) as ydl_single:
                        ydl_single.download([entry_url])
                    saved_path = target_path
                except Exception as e:
                    log_error(f"Fallback yt_dlp download failed: {e}")
                    continue

            try:
                moved = sort_downloaded_file(saved_path, entry_url, settings)
                final_paths.append(moved if moved else saved_path)
            except Exception:
                final_paths.append(saved_path)

        try:
            ydl_for_info.close()
        except Exception:
            pass

        return final_paths[-1] if final_paths else None

    # Single video path
    final_entry_title = base_title
    if custom_name == "__INTERACTIVE__":
        res = ask_for_name(base_title)
        if res:
            final_entry_title = res

    target_path = resolve_available_filename(save_folder, final_entry_title, ext=".mp4", overwrite_existing=overwrite_existing, session_key=session_key or video_url)
    if target_path is None:
        print_if_not_ignored(f"Skipping existing file: {os.path.join(save_folder, final_entry_title + '.mp4')}", settings)
        return None

    ydl_opts = common_opts.copy()
    ydl_opts.update({
        'outtmpl': target_path,
        'noplaylist': True,
        'progress_hooks': progress_hooks or [ytdlp_progress_hook],
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
    })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        try:
            final_path = sort_downloaded_file(target_path, video_url, settings)
            return final_path if final_path else target_path
        except Exception:
            return target_path
    except Exception as e:
        log_error(f"Error downloading video with yt_dlp: {e}")
        return None
