# cerberus/tests/test_utils.py

import os
import shutil
import tempfile
import pytest
from cerberus.utils import sanitize_filename, resolve_available_filename

def test_sanitize_filename():
    # Test valid filename
    assert sanitize_filename("valid_filename") == "valid_filename"
    
    # Test invalid characters
    assert sanitize_filename("invalid:filename?") == "invalid_filename_"
    assert sanitize_filename("with/slash\\backslash") == "with_slash_backslash"
    assert sanitize_filename("with<angle>brackets") == "with_angle_brackets"
    assert sanitize_filename("with\"quotes\"") == "with_quotes_"
    assert sanitize_filename("with|pipe") == "with_pipe"
    assert sanitize_filename("with*asterisk") == "with_asterisk"
    
    # Test control characters
    assert sanitize_filename("with\nnewline") == "with_newline"
    
    # Test empty or None
    assert sanitize_filename("") == "video"
    assert sanitize_filename(None) == "video"
    
    # Test length limit (default 200)
    long_name = "a" * 300
    sanitized = sanitize_filename(long_name)
    assert len(sanitized) == 200
    assert sanitized == "a" * 200

    # Test trailing dots/spaces
    assert sanitize_filename("file. ") == "file"
    assert sanitize_filename("file...") == "file"

def test_resolve_available_filename():
    # Setup temporary directory
    tmp_dir = tempfile.mkdtemp()
    try:
        base_name = "test_video"
        ext = ".mp4"
        
        # 1. Base file does not exist
        resolved = resolve_available_filename(tmp_dir, base_name, ext)
        expected = os.path.join(tmp_dir, base_name + ext)
        assert resolved == expected
        
        # 2. Base file exists, overwrite_existing=False, no session_key
        # Create the file
        with open(expected, 'w') as f:
            f.write("dummy")
        
        resolved = resolve_available_filename(tmp_dir, base_name, ext, overwrite_existing=False)
        assert resolved is None
        
        # 3. Base file exists, overwrite_existing=True
        resolved = resolve_available_filename(tmp_dir, base_name, ext, overwrite_existing=True)
        assert resolved == expected
        
        # 4. Session-based numbering
        session_key = "session_1"
        # The base file already exists from previous step, and we haven't seen it in this session.
        # So it should return None (to signal skip) and mark it as seen.
        resolved = resolve_available_filename(tmp_dir, base_name, ext, session_key=session_key)
        assert resolved is None
        
        # Now we've seen it in this session, the NEXT one should be numbered (1).
        resolved = resolve_available_filename(tmp_dir, base_name, ext, session_key=session_key)
        expected_numbered = os.path.join(tmp_dir, f"{base_name}(1){ext}")
        assert resolved == expected_numbered
        
        # Create the numbered file
        with open(expected_numbered, 'w') as f:
            f.write("dummy1")
            
        # The next one should be (2)
        resolved = resolve_available_filename(tmp_dir, base_name, ext, session_key=session_key)
        expected_numbered_2 = os.path.join(tmp_dir, f"{base_name}(2){ext}")
        assert resolved == expected_numbered_2
        
    finally:
        shutil.rmtree(tmp_dir)
