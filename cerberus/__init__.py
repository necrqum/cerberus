# cerberus/__init__.py

from .main import main
from .downloader import (
    download_video_from_page,
    download_videos_from_list,
)
from .config import load_settings
from .adapters.ytdlp import download_with_youtube_dl
from .adapters.selenium import extract_video_name, extract_main_video_url

__all__ = [
    "load_settings",
    "download_with_youtube_dl",
    "extract_video_name",
    "extract_main_video_url",
    "download_video_from_page",
    "download_videos_from_list",
    "main",
]
