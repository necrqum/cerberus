import os
import platform
import subprocess
import shutil
import logging
import json
from datetime import datetime

# ================================
# Central Configuration Management
# ================================

def get_config_dir():
    """
    Returns the path to the centralized configuration directory.
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
PROFILES_PATH = os.path.join(CONFIG_DIR, "profiles.json")
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
    """Auto-detect browser path."""
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
    """Creates default Settings.txt."""
    if not os.path.exists(file_path):
        detected_browser = detect_browser_path()
        default_browser = detected_browser if detected_browser else ("/usr/bin/chromium-browser" if platform.system() != "Windows" else "C:/PATH/TO/BROWSER/Browser.exe")
        with open(file_path, 'w') as f:
            f.write(f"browser_path={default_browser}\n")
            f.write("minimized=false\n")
            f.write("default_quality=best\n")
            f.write("# use --list-config to see the current/standart -config-settings\n")
        logging.info(f"Settings file created at {file_path}")

def load_settings(file_path=SETTINGS_PATH):
    """Loads settings from Settings.txt."""
    settings = {}
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip() and '=' in line and not line.strip().startswith('#'):
                    key, value = line.split('=', 1)
                    settings[key.strip()] = value.strip()
    except FileNotFoundError:
        build_settings(file_path)
        return load_settings(file_path)
    # Defaults
    defaults = {
        'overwrite_existing': 'false',
        'sort_by': 'none',
        'default_quality': 'best',
        'use_cwd_as_default': 'false',
        'default_download_dir': 'DEFAULT'
    }
    for k, v in defaults.items():
        if k not in settings:
            settings[k] = v
    return settings

def load_profiles():
    if os.path.exists(PROFILES_PATH):
        try:
            with open(PROFILES_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading profiles: {e}")
    return {}

def save_profiles(profiles):
    try:
        with open(PROFILES_PATH, 'w') as f:
            json.dump(profiles, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving profiles: {e}")

def get_settings_with_profile(profile_name=None):
    settings = load_settings()
    if profile_name:
        profiles = load_profiles()
        if profile_name in profiles:
            settings.update(profiles[profile_name])
        else:
            logging.warning(f"Profile '{profile_name}' not found. Using defaults.")
    return settings

def get_default_download_dir(settings):
    if settings.get('use_cwd_as_default', 'false').lower() == 'true':
        return os.getcwd()
    custom_dir = settings.get('default_download_dir', 'DEFAULT')
    if not custom_dir or custom_dir.upper() == 'DEFAULT':
        return DEFAULT_DOWNLOAD_DIR
    return os.path.expanduser(custom_dir)

def save_settings(settings, file_path=SETTINGS_PATH):
    try:
        with open(file_path, 'w') as f:
            for key, value in settings.items():
                f.write(f"{key}={value}\n")
    except Exception as e:
        logging.error(f"Error saving settings: {e}")

def open_file(file_path):
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
    print("\n" + "="*40)
    print("      Cerberus Setup Wizard")
    print("="*40 + "\n")
    if os.path.exists(SETTINGS_PATH):
        choice = input("Existing configuration found. Reset? [r/A]: ").strip().lower()
        if choice != 'r':
            return
    settings = load_settings()
    detected_browser = detect_browser_path()
    if detected_browser:
        use_detected = input(f"Use {detected_browser}? [Y/n]: ").strip().lower()
        settings['browser_path'] = detected_browser if use_detected != 'n' else input("Enter browser path: ").strip()
    else:
        settings['browser_path'] = input("Enter browser path: ").strip()
    save_settings(settings)
    print("\nSetup Completed!")

def handle_config(args, custom_print_func=print):
    if not os.path.exists(SETTINGS_PATH):
        build_settings()
    if args.list_config:
        settings = load_settings()
        custom_print_func("Current Settings:")
        for key in sorted(settings.keys()):
            custom_print_func(f"{key} = {settings[key]}")
    elif args.example_config:
        example_path = os.path.join(CONFIG_DIR, "example_settings.txt")
        with open(example_path, 'w') as f:
            f.write("browser_path=/path/to/browser\nminimized=false\ndefault_quality=best\npost_download_command=echo {filename} downloaded\n")
        custom_print_func(f"Example config created at {example_path}")
    else:
        open_file(SETTINGS_PATH)
