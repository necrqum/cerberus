# cerberus/tests/test_config.py

import os
import shutil
import tempfile
import pytest
from cerberus.config import load_settings, get_config_dir, build_settings

def test_get_config_dir():
    # get_config_dir depends on platform.system() and environment variables
    # We can at least check if it returns a path that exists or can be created
    config_dir = get_config_dir()
    assert config_dir is not None
    assert os.path.isdir(config_dir)

def test_load_settings():
    # Create a temporary settings file
    tmp_dir = tempfile.mkdtemp()
    settings_file = os.path.join(tmp_dir, "Settings.txt")
    
    try:
        # Test loading non-existent file (should call build_settings and return defaults)
        settings = load_settings(settings_file)
        assert os.path.exists(settings_file)
        assert 'browser_path' in settings
        assert settings['overwrite_existing'] == 'false'
        
        # Test loading existing file
        with open(settings_file, 'w') as f:
            f.write("browser_path=/custom/browser\n")
            f.write("overwrite_existing=true\n")
            f.write("custom_key=custom_value\n")
            f.write("# comment\n")
            f.write("   \n") # empty line
            
        settings = load_settings(settings_file)
        assert settings['browser_path'] == "/custom/browser"
        assert settings['overwrite_existing'] == "true"
        assert settings['custom_key'] == "custom_value"
        
        # Test defaults
        assert settings['default_quality'] == "best"
        
    finally:
        shutil.rmtree(tmp_dir)

def test_build_settings():
    tmp_dir = tempfile.mkdtemp()
    settings_file = os.path.join(tmp_dir, "Settings.txt")
    
    try:
        build_settings(settings_file)
        assert os.path.exists(settings_file)
        
        with open(settings_file, 'r') as f:
            content = f.read()
            assert "browser_path=" in content
            
    finally:
        shutil.rmtree(tmp_dir)
