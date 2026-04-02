import os
import time
import json
import subprocess
import requests
import yt_dlp
import shutil
from tqdm import tqdm
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# Global progress bar instance
pbar = None

try:
    from ..config import SETTINGS_PATH, load_settings, get_default_download_dir
    from ..utils import (
        log_info, log_error, sanitize_filename, resolve_available_filename,
        human_readable_size, print_if_not_ignored
    )
    from ..events import stop_download
except (ImportError, ValueError):
    from config import SETTINGS_PATH, load_settings, get_default_download_dir
    from utils import (
        log_info, log_error, sanitize_filename, resolve_available_filename,
        human_readable_size, print_if_not_ignored
    )
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from events import stop_download

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
    yt_dlp progress hook using tqdm for professional output.
    """
    global pbar
    try:
        status = d.get('status')
        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes') or 0
            
            if pbar is None:
                filename = os.path.basename(d.get('filename', 'video'))
                pbar = tqdm(
                    total=total,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=f"Downloading {filename[:30]}",
                    leave=True,
                    dynamic_ncols=True
                )
            
            pbar.n = downloaded
            pbar.refresh()
            
        elif status == 'finished':
            if pbar:
                pbar.close()
                pbar = None
            print(f"Finished: {os.path.basename(d.get('filename', ''))}")
            
        elif status == 'error':
            if pbar:
                pbar.close()
                pbar = None
            print(f"Error downloading: {os.path.basename(d.get('filename', ''))}")
    except Exception:
        if pbar:
            pbar.close()
            pbar = None

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
    Robust download + unified progress reporting.
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

                    downloaded = 0
                    start_time = time.time()

                    # Ensure parent dir exists
                    parent = os.path.dirname(target_path)
                    if parent:
                        os.makedirs(parent, exist_ok=True)

                    with open(tmp, "wb") as fh:
                        for chunk in r.iter_content(chunk_size=block_size):
                            if stop_download.is_set():
                                break
                            if not chunk:
                                continue
                            fh.write(chunk)
                            downloaded += len(chunk)

                            # Build progress dict compatible with ytdlp_progress_hook
                            progress_dict = {
                                'status': 'downloading',
                                'filename': os.path.basename(target_path),
                                'downloaded_bytes': downloaded,
                                'total_bytes': total_size,
                            }
                            try:
                                ytdlp_progress_hook(progress_dict)
                            except Exception:
                                pass
                    
                    if stop_download.is_set():
                        if os.path.exists(tmp):
                            os.remove(tmp)
                        return False

                    # Atomic replace
                    try:
                        os.replace(tmp, target_path)
                    except OSError as e:
                        log_error(f"Atomic replace failed: {e}. Retrying in 2s...")
                        time.sleep(2)
                        try:
                            os.replace(tmp, target_path)
                        except Exception as e2:
                            log_error(f"Second attempt to replace temp file failed: {e2}")
                            try:
                                if os.path.exists(tmp):
                                    os.remove(tmp)
                            except Exception:
                                pass
                            raise

                    # Verify file and call finished hook
                    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                        try:
                            ytdlp_progress_hook({'status': 'finished', 'filename': os.path.basename(target_path)})
                        except Exception:
                            pass
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
        try:
            ytdlp_progress_hook({'status': 'downloading', 'filename': os.path.basename(target_path), 'downloaded_bytes': 0, 'total_bytes': 0, 'speed': 0, 'eta': None})
        except Exception:
            pass

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
            try:
                ytdlp_progress_hook({'status': 'finished', 'filename': os.path.basename(target_path)})
            except Exception:
                pass
            print(f"ffmpeg finished: {os.path.basename(target_path)}")
            return True
        else:
            stderr = proc.stderr.decode(errors='ignore') if proc.stderr else ''
            log_error(f"ffmpeg failed (rc={proc.returncode}) for {media_url}. stderr: {stderr[:1000]}")
    except Exception as e:
        log_error(f"ffmpeg invocation error for {media_url}: {e}")

    return False

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
    base_dir = get_default_download_dir(settings)

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
    }
    
    # YouTube-specific cookie handling
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

    # Try to extract info once
    try:
        with yt_dlp.YoutubeDL(common_opts) as ydl:
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
        ydl_for_info = yt_dlp.YoutubeDL(common_opts)

        media_seen = set()
        final_paths = []

        for idx, entry in enumerate(unique_entries):
            entry_url = entry.get('webpage_url') or entry.get('url') or video_url

            # Try to get media_url from entry, prefer non-extractive access
            media_url, meta = get_direct_media_url(entry, entry_url, quality=quality, ydl_instance=ydl_for_info)

            # If still no media_url, mark for controlled yt_dlp fallback
            used_fallback_ydl_download = False
            if not media_url:
                used_fallback_ydl_download = True

            # Deduplicate by media_url (if available), else by entry key
            dedupe_key = media_url if media_url else (entry.get('id') or entry.get('webpage_url') or entry.get('url'))
            if dedupe_key in media_seen:
                continue
            media_seen.add(dedupe_key)

            # Resolve target path using session_key
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
                # Controlled yt_dlp download for this entry
                ydl_opts_entry = common_opts.copy()
                ydl_opts_entry.update({
                    'outtmpl': target_path,
                    'noplaylist': True,
                    'progress_hooks': [ytdlp_progress_hook],
                    'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
                })
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

    ydl_opts = common_opts.copy()
    ydl_opts.update({
        'outtmpl': target_path,
        'noplaylist': True,
        'progress_hooks': [ytdlp_progress_hook],
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
    })

    try:
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
