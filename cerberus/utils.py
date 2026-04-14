import os
import re
import threading
import logging
import sys

# ================================
# Logging Setup
# ================================
logger = logging.getLogger("cerberus")

def setup_logging(log_path):
    """
    Sets up the logging configuration.
    Writes to both a file and the console.
    """
    logger.setLevel(logging.DEBUG)

    # Formatter with timestamp, level, thread name, and message
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # File Handler
    try:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Error setting up file logger: {e}")

    # Prevent duplicate logs if main.py is reloaded or something
    logger.propagate = False

def log_info(message):
    logger.info(message)

def log_error(message):
    logger.error(message)

def custom_print(*args, hidden=False, **kwargs):
    """Prints to console only if hidden is False."""
    if not hidden:
        print(*args, **kwargs)

def print_if_not_ignored(message, settings):
    """
    Prints message to console only if 'ignoreerrors' is not set to true.
    """
    if settings.get('ignoreerrors', 'false').lower() != 'true':
        print(message)

# ================================
# Utility Functions
# ================================

INVALID_RE = re.compile(f'[{re.escape("<>:\"/\\\\|?*")}\x00-\x1f]')

def sanitize_filename(name, max_length=200):
    """
    Removes/replaces invalid filename characters for Windows/Linux.
    - replaces invalid characters with '_' and shortens length
    - removes leading/trailing whitespace and dots
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

# ====== Session-based filename counters to number files from same URL/session ======
session_filename_counters = {}
session_lock = threading.Lock()

def resolve_available_filename(save_folder, base_name, ext=".mp4", overwrite_existing=False, session_key=None):
    """
    Determine an available filename in save_folder.
    """
    # sanitize base name for filesystem safety
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

    # If base file exists and overwrite not allowed
    if not session_key:
        return None

    # If session_key provided, we need careful session-based numbering
    with session_lock:
        counters = session_filename_counters.setdefault(session_key, {})
        # If this is the first time we see this filename in THIS session
        if safe_base not in counters:
            # We skip this one because the file exists on disk and it's the "original" name.
            # Mark as 1 so the NEXT occurrence of this name gets NAME(1)
            counters[safe_base] = 1
            return None

        # This name has been seen in this session before (either was skipped or downloaded)
        idx = counters.get(safe_base, 1)
        while True:
            candidate = os.path.join(save_folder, f"{safe_base}({idx}){ext}")
            if not os.path.exists(candidate):
                counters[safe_base] = idx + 1
                return candidate
            idx += 1
