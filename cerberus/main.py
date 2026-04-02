# cerberus/main.py

import os
import signal
import argparse
import time
import logging
from concurrent.futures import ThreadPoolExecutor

from .config import (
    SETTINGS_PATH, load_settings, handle_config, get_default_download_dir, run_setup_wizard
)
from .utils import (
    log_error, custom_print, print_if_not_ignored
)
from .downloader import (
    download_video_from_page
)
from .events import stop_download

def is_output_hidden(settings, args):
    """Checks whether console output should be hidden."""
    return settings.get('output_always_hidden', 'false').lower() == 'true' or args.hidden

def sigint_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    stop_download.set()

def main():
    """Main entry point for the command-line interface."""
    signal.signal(signal.SIGINT, sigint_handler)
    parser = argparse.ArgumentParser(description="Cerberus Video Downloader")
    parser.add_argument('-l', '--link', help="Direct URL to a video", type=str)
    parser.add_argument('-u', '--urls', help="Comma-separated list of URLs to download", type=str)
    parser.add_argument('-r', '--list', help="Path to a file containing video URLs", type=str)
    parser.add_argument('-p', '--path', help="Path to save downloaded videos", type=str)
    parser.add_argument('-n', '--name', help="Optional name for the downloaded video (single downloads only)", type=str)
    parser.add_argument('-H', '--hidden', help="Hide all console output", action='store_true')
    parser.add_argument('-f', '--force', help="Force the use of yt_dlp for downloading", action='store_true')
    parser.add_argument('-q', '--quality', help="Download quality (e.g. best, worst, 720p)", type=str)
    parser.add_argument('-t', '--threads', help="Number of parallel downloads (default: 1)", type=int, default=1)
    
    # Configuration-related arguments
    group = parser.parse_known_args()[0]
    parser.add_argument('--setup', action='store_true', help="Run the interactive setup wizard")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--config', action='store_true', help="Open the configuration file")
    group.add_argument('--list-config', action='store_true', help="Display current configuration settings")
    group.add_argument('--example-config', action='store_true', help="Generate an example configuration file")
    
    args = parser.parse_args()

    # Trigger wizard if Settings.txt doesn't exist or requested via --setup
    if args.setup or not os.path.exists(SETTINGS_PATH):
        run_setup_wizard()
        if args.setup:
            return

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
        save_folder = get_default_download_dir(settings)

    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    if args.config or args.list_config or args.example_config:
        handle_config(args, custom_print_func=lambda msg: custom_print(msg, hidden=hidden_output))
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

    def process_video(idx_and_url):
        idx, url = idx_and_url
        if stop_download.is_set():
            return
        
        print_if_not_ignored(f"\n[{idx+1}/{len(url_list)}] Starting download for: {url}", settings)
        start_time_video = time.time()
        final_path = download_video_from_page(
            url, browser_path, save_folder, idx, len(url_list), 
            minimize_browser, overwrite_existing, 
            custom_name=args.name if len(url_list) == 1 else None, 
            force=args.force, quality=quality
        )
        elapsed_time_video = time.time() - start_time_video
        if final_path:
            print(f"[{idx+1}/{len(url_list)}] Completed in {elapsed_time_video:.2f}s: {final_path}")
        else:
            print(f"[{idx+1}/{len(url_list)}] Failed in {elapsed_time_video:.2f}s.")

    # Execute downloads
    if args.threads > 1:
        print(f"Starting parallel downloads with {args.threads} threads...")
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            executor.map(process_video, enumerate(url_list))
    else:
        for idx_and_url in enumerate(url_list):
            process_video(idx_and_url)
            if stop_download.is_set():
                break

if __name__ == "__main__":
    main()
