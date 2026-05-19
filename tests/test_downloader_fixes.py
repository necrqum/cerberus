import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from cerberus.adapters import ytdlp

def test_download_media_url_html_corruption_prevention():
    """Verify that download_media_url fails if Content-Type is text/html."""
    target_path = "test.mp4"
    settings = {"user_agent": "test-agent"}
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.__enter__.return_value = mock_response
    
    with patch("requests.Session.get", return_value=mock_response):
        result = ytdlp.download_media_url("http://example.com/page", target_path, settings)
        assert result is False
        assert not os.path.exists(target_path)

def test_download_media_url_429_backoff_and_ffmpeg_skip():
    """Verify that 429 causes retries and skips ffmpeg fallback on max retries."""
    target_path = "test.mp4"
    settings = {"user_agent": "test-agent"}
    
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.__enter__.return_value = mock_response
    
    # We'll patch time.sleep to avoid waiting
    with patch("requests.Session.get", return_value=mock_response) as mock_get:
        with patch("time.sleep"):
            # We also need to patch subprocess.run to make sure it's NOT called
            with patch("subprocess.run") as mock_run:
                result = ytdlp.download_media_url("http://example.com/video", target_path, settings, max_retries=2)
                assert result is False
                assert mock_get.call_count == 2
                assert mock_run.call_count == 0

def test_download_media_url_success_with_content_type():
    """Verify that download_media_url succeeds with video/mp4."""
    tmp_dir = tempfile.mkdtemp()
    target_path = os.path.join(tmp_dir, "test.mp4")
    settings = {"user_agent": "test-agent"}
    
    try:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "video/mp4", "content-length": "100"}
        mock_response.iter_content.return_value = [b"a" * 50, b"b" * 50]
        mock_response.__enter__.return_value = mock_response
        
        with patch("requests.Session.get", return_value=mock_response):
            # We need to bypass the 20KB check for this test or provide 20KB
            mock_response.headers["content-length"] = str(30000)
            mock_response.iter_content.return_value = [b"a" * 15000, b"b" * 16000]
            
            result = ytdlp.download_media_url("http://example.com/video", target_path, settings)
            assert result is True
            assert os.path.exists(target_path)
            assert os.path.getsize(target_path) == 31000
    finally:
        shutil.rmtree(tmp_dir)

def test_download_videos_from_list_logic():
    """Verify that download_videos_from_list sets is_pre_extracted correctly."""
    from cerberus.downloader import download_videos_from_list
    
    url_items = [{"url": "http://example.com/album", "name": None}]
    browser_path = "/usr/bin/chrome"
    save_folder = "/tmp/downloads"
    
    with patch("cerberus.downloader.download_video_from_page") as mock_download_page:
        with patch("cerberus.downloader.load_settings", return_value={}):
            # 1. Non-interactive mode
            download_videos_from_list(
                url_items, browser_path, save_folder, False, False, 
                custom_name=None, settings_dict={}
            )
            # Should call with is_pre_extracted=False
            args, kwargs = mock_download_page.call_args
            assert kwargs['is_pre_extracted'] is False
            
            # 2. Interactive mode
            # Mock prepare_naming_for_url to avoid actual extraction
            with patch("cerberus.downloader.prepare_naming_for_url", return_value=[{"url": "http://cdn.com/video.mp4", "name": "custom"}]):
                download_videos_from_list(
                    url_items, browser_path, save_folder, False, False, 
                    custom_name="__INTERACTIVE__", settings_dict={}
                )
                # Should call with is_pre_extracted=True
                args, kwargs = mock_download_page.call_args
                assert kwargs['is_pre_extracted'] is True
