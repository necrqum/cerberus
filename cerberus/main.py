import os
import sys
import signal
import argparse
import time
import logging

from .config import (
    SETTINGS_PATH, load_settings, handle_config, get_default_download_dir, 
    run_setup_wizard, get_session_log_path, get_settings_with_profile,
    add_profile, delete_profile
)
from .utils import (
    log_error, custom_print, print_if_not_ignored, setup_logging
)
from .downloader import (
    download_video_from_page, download_videos_from_list, load_queue
)
from .events import stop_download
from .ui import setup_rich_logging, print_info, print_header, print_error

def is_output_hidden(settings, args):
    """Checks whether console output should be hidden."""
    return settings.get('output_always_hidden', 'false').lower() == 'true' or args.hidden

def sigint_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    if stop_download.is_set():
        # Force exit on second Ctrl+C
        print("\n[bold red]Forcing exit...[/bold red]")
        os._exit(1)
    stop_download.set()
    from .adapters.ytdlp import stop_progress_bar
    stop_progress_bar()
    print("\n[bold yellow]Abort signal received. Finishing active tasks... (Press Ctrl+C again to force exit)[/bold yellow]")

def main():
    """Main entry point for the command-line interface."""
    # Initialize session-specific logging
    session_log_path = get_session_log_path()
    setup_logging(session_log_path)
    setup_rich_logging()
    
    signal.signal(signal.SIGINT, sigint_handler)
    parser = argparse.ArgumentParser(description="Cerberus Video Downloader")
    parser.add_argument('-l', '--link', help="Direct URL to a video", type=str)
    parser.add_argument('-u', '--urls', help="Comma-separated list of URLs to download", type=str)
    parser.add_argument('-r', '--list', help="Path to a file containing video URLs", type=str)
    parser.add_argument('-p', '--path', help="Path to save downloaded videos", type=str)
    parser.add_argument('-n', '--name', help="Optional name (omit value for interactive mode)", type=str, nargs='?', const='__INTERACTIVE__')
    parser.add_argument('-H', '--hidden', help="Hide all console output", action='store_true')
    parser.add_argument('-f', '--force', help="Force the use of yt_dlp for downloading", action='store_true')
    parser.add_argument('-q', '--quality', help="Download quality (e.g. best, worst, 720p)", type=str)
    parser.add_argument('-t', '--threads', help="Number of parallel downloads", type=int, default=1)
    parser.add_argument('-b', '--limit-rate', help="Maximum download speed (e.g. 500K, 1M)", type=str)
    parser.add_argument('-P', '--profile', help="Use a named download profile", type=str)
    parser.add_argument('--add-profile', help="Add/Update a profile (format: name:key=val,key2=val2)", type=str)
    parser.add_argument('--del-profile', help="Delete a profile", type=str)
    parser.add_argument('--resume', action='store_true', help="Resume the last interrupted download queue")
    
    parser.add_argument('--setup', action='store_true', help="Run the interactive setup wizard")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--config', action='store_true', help="Open the configuration file")
    group.add_argument('--list-config', action='store_true', help="Display current configuration settings")
    group.add_argument('--example-config', action='store_true', help="Generate an example configuration file")
    
    args = parser.parse_args()

    # Show help if no arguments are provided
    if len(sys.argv) == 1:
        parser.print_help()
        return

    if args.setup or not os.path.exists(SETTINGS_PATH):
        run_setup_wizard()
        if args.setup:
            return

    settings = get_settings_with_profile(args.profile)
    hidden_output = is_output_hidden(settings, args)
    
    if args.config or args.list_config or args.example_config:
        handle_config(args, custom_print_func=lambda msg: custom_print(msg, hidden=hidden_output))
        return

    if args.add_profile:
        add_profile(args.add_profile)
        return

    if args.del_profile:
        delete_profile(args.del_profile)
        return

    browser_path = settings.get('browser_path')
    minimize_browser = settings.get('minimized', 'false').lower() == 'true'
    overwrite_existing = settings.get('overwrite_existing', 'false').lower() == 'true'
    quality = args.quality or settings.get('default_quality', 'best')
    limit_rate = args.limit_rate or settings.get('default_limit_rate')

    if args.path:
        save_folder = args.path
    else:
        save_folder = get_default_download_dir(settings)

    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    url_items = []
    if args.resume:
        queue = load_queue()
        res_urls = queue.get("urls", [])
        if not res_urls:
            print_info("No interrupted queue found to resume.")
            return
        url_items = [{"url": u, "name": None} for u in res_urls]
    else:
        raw_list = []
        if args.link:
            raw_list.append(args.link.strip())
        if args.urls:
            raw_list += [u.strip() for u in args.urls.split(',') if u.strip()]
        if args.list:
            try:
                with open(args.list, 'r') as f:
                    raw_list += [line.strip() for line in f if line.strip()]
            except Exception as e:
                print_error(f"Error reading list file: {e}")

        # Parse 'URL:::Name' format
        for item in raw_list:
            if ":::" in item:
                u, n = item.split(":::", 1)
                url_items.append({"url": u.strip(), "name": n.strip()})
            else:
                url_items.append({"url": item, "name": None})

    if not url_items:
        print_info("No URLs provided for download.")
        parser.print_help()
        return

    if not browser_path or not os.path.exists(browser_path):
        print_error("Invalid browser path in settings.")
        return

    from .adapters.ytdlp import stop_progress_bar
    try:
        download_videos_from_list(
            url_items, browser_path, save_folder, minimize_browser, overwrite_existing,
            force=args.force, quality=quality, limit_rate=limit_rate, threads=args.threads,
            custom_name=args.name
        )
    finally:
        stop_progress_bar()

if __name__ == "__main__":
    main()
