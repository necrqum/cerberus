import os
import platform
import subprocess
import shutil
import logging
from datetime import datetime

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
LOGS_DIR = os.path.join(CONFIG_DIR, "Logs")
DEFAULT_DOWNLOAD_DIR = os.path.join(CONFIG_DIR, "Downloads")

# Ensure necessary folders exist
for folder in [CONFIG_DIR, DEFAULT_DOWNLOAD_DIR, LOGS_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def get_session_log_path():
    """Generates a unique log path for the current session based on timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return os.path.join(LOGS_DIR, f"Cerberus_{timestamp}.log")

def detect_browser_path():
    """
    Auto-detect browser path based on the operating system.
    Returns the path to the first found browser, or None if none found.
    Uses shutil.which for efficient PATH searching.
    """
    system = platform.system()
    
    browser_names = []
    if system == "Windows":
        browser_names = ["chrome.exe", "chromium.exe", "brave.exe", "msedge.exe", "firefox.exe"]
    elif system == "Darwin":
        browser_names = ["Google Chrome", "Chromium", "Brave Browser"]
    else:
        browser_names = ["google-chrome", "chromium-browser", "chromium", "brave-browser", "brave", "firefox", "opera", "microsoft-edge"]
    
    for browser in browser_names:
        found = shutil.which(browser)
        if found:
            return found
    
    return None

def build_settings(file_path=SETTINGS_PATH):
    """Creates the Settings.txt file if it does not exist."""
    if not os.path.exists(file_path):
        detected_browser = detect_browser_path()
        
        if platform.system() == "Windows":
            default_browser = "C:/PATH/TO/BROWSER/Browser.exe"
        elif detected_browser:
            default_browser = detected_browser
        else:
            default_browser = "/usr/bin/chromium-browser"
        
        with open(file_path, 'w') as f:
            f.write(f"browser_path={default_browser}\n")
            f.write("# use --list-config to see the current/standart -config-settings\n")
            f.write("# use --example-config to view all available config-settings\n")
        # Since log_info is in utils, we might need to handle logging here differently or pass logger
        logging.info(f"Settings file created at {file_path}")

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
        logging.error(f"Settings file {file_path} not found. Creating default.")
        build_settings(file_path)
        # Try loading again after building
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    if line.strip() and '=' in line and not line.strip().startswith('#'):
                        key, value = line.split('=', 1)
                        settings[key.strip()] = value.strip()
        except Exception as e:
            logging.error(f"Error reading newly created settings file: {e}")
    # Ensure defaults
    if 'overwrite_existing' not in settings:
        settings['overwrite_existing'] = 'false'
    if 'sort_by' not in settings:
        settings['sort_by'] = 'none'
    if 'default_quality' not in settings:
        settings['default_quality'] = 'best'
    if 'use_cwd_as_default' not in settings:
        settings['use_cwd_as_default'] = 'false'
    if 'default_download_dir' not in settings:
        settings['default_download_dir'] = 'DEFAULT' # will use DEFAULT_DOWNLOAD_DIR
    return settings

def get_default_download_dir(settings):
    """
    Determines the default download directory based on settings.
    Priority:
    1) use_cwd_as_default = true  -> current working directory
    2) default_download_dir = DEFAULT -> DEFAULT_DOWNLOAD_DIR
    3) default_download_dir = <path>  -> that path
    """
    if settings.get('use_cwd_as_default', 'false').lower() == 'true':
        return os.getcwd()

    custom_dir = settings.get('default_download_dir', 'DEFAULT')

    if not custom_dir or custom_dir.upper() == 'DEFAULT':
        return DEFAULT_DOWNLOAD_DIR

    return os.path.expanduser(custom_dir)

def save_settings(settings, file_path=SETTINGS_PATH):
    """Saves settings to the Settings.txt file."""
    try:
        with open(file_path, 'w') as f:
            for key, value in settings.items():
                f.write(f"{key}={value}\n")
        logging.info(f"Settings saved to {file_path}")
    except Exception as e:
        logging.error(f"Error saving settings: {e}")

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
        logging.error(f"Error opening file {file_path}: {e}")

def run_setup_wizard():
    """Interactive setup wizard for first-time configuration."""
    print("\n" + "="*40)
    print("      Cerberus Setup Wizard")
    print("="*40 + "\n")
    
    settings = load_settings(SETTINGS_PATH)
    
    # 1. Browser Selection
    detected_browser = detect_browser_path()
    print(f"Detecting browser... ", end="", flush=True)
    if detected_browser:
        print(f"Found: {detected_browser}")
        use_detected = input(f"Use this browser? [Y/n]: ").strip().lower()
        if use_detected == 'n':
            settings['browser_path'] = input("Enter full path to your browser executable: ").strip()
        else:
            settings['browser_path'] = detected_browser
    else:
        print("Not found.")
        settings['browser_path'] = input("Enter full path to your browser executable: ").strip()
    
    # 2. Download Directory
    print(f"\nDefault download directory: {DEFAULT_DOWNLOAD_DIR}")
    use_default_dir = input(f"Use this directory? [Y/n]: ").strip().lower()
    if use_default_dir == 'n':
        custom_dir = input("Enter absolute path for downloads: ").strip()
        settings['default_download_dir'] = custom_dir
    else:
        settings['default_download_dir'] = 'DEFAULT'
    
    # 3. Other common settings
    print("\nAdditional Settings:")
    
    minimized = input("Run browser in background (minimized)? [Y/n]: ").strip().lower()
    settings['minimized'] = 'true' if minimized != 'n' else 'false'
    
    quality = input("Default video quality (best/worst/720p/etc) [best]: ").strip()
    settings['default_quality'] = quality if quality else 'best'
    
    # Check for FFmpeg
    print(f"\nChecking for FFmpeg... ", end="", flush=True)
    ffmpeg_found = shutil.which("ffmpeg")
    if ffmpeg_found:
        print(f"Found: {ffmpeg_found}")
    else:
        print("NOT FOUND. Please install FFmpeg and add it to your PATH for full functionality.")
    
    save_settings(settings)
    print("\n" + "="*40)
    print("      Setup Completed Successfully!")
    print("="*40 + "\n")

def handle_config(args, custom_print_func=print):
    """
    Handles configuration commands:
      - --list-config: displays the current settings.
      - --example-config: creates an example configuration file.
      - --config (alone): opens the Settings.txt file in the default editor.
    """
    if not os.path.exists(SETTINGS_PATH):
        build_settings(SETTINGS_PATH)

    if args.list_config:
        settings = load_settings(SETTINGS_PATH)
        custom_print_func("Current Settings:")
        for key in sorted(settings.keys()):
            custom_print_func(f"{key} = {settings[key]}")
    elif args.example_config:
        example_path = os.path.join(CONFIG_DIR, "example_settings.txt")
        example_browser = detect_browser_path() or "/usr/bin/chromium-browser"
        with open(example_path, 'w') as f:
            f.write(
                f"""browser_path={example_browser}
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
default_download_dir=DEFAULT   # DEFAULT or absolute path (used when use_cwd_as_default=false)
selenium_wait_time=5   # seconds to wait for page load in selenium
"""
            )
        custom_print_func(f"Example configuration created at {example_path}")
    else:
        custom_print_func(f"Opening settings file at {SETTINGS_PATH}...")
        open_file(SETTINGS_PATH)
