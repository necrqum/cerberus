import time
import json
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import NoSuchElementException, NoSuchWindowException, WebDriverException

try:
    from ..utils import log_error, sanitize_filename
except (ImportError, ValueError):
    from utils import log_error, sanitize_filename

def extract_video_name(driver):
    """Extracts the title of the video from the page."""
    try:
        title_element = driver.find_element(By.TAG_NAME, 'title')
        video_title = title_element.get_attribute('innerText')
        return video_title
    except NoSuchWindowException:
        raise
    except Exception as e:
        log_error(f"Error extracting video title: {e}")
        return "video"

def intercept_media_url(url, browser_path, minimize_browser, cookies=None, wait_time=5):
    """
    Initializes a browser, loads the URL, and intercepts media URLs from performance logs.
    Returns (video_name, video_links).
    
    Args:
        url: The URL to load
        browser_path: Path to the browser executable
        minimize_browser: Whether to run in minimized/headless mode
        cookies: Optional cookies to set before loading the page
        wait_time: Seconds to wait for page and video to load (default: 5)
    """
    driver = None
    video_links = []
    video_name = "video"
    
    try:
        options = Options()
        options.binary_location = browser_path
        options.add_argument("--incognito")
        
        # Performance logging for interception
        capabilities = DesiredCapabilities.CHROME.copy()
        capabilities['goog:loggingPrefs'] = {'performance': 'ALL'}
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        if minimize_browser:
            options.add_argument("--window-position=0,3000")
            options.add_argument("--headless=new")

        driver = webdriver.Chrome(service=ChromeService(), options=options)
        
        # Some sites (like Newgrounds) might need cookies before loading the main URL
        if cookies:
            driver.get("about:blank") # Need to be on some page to add cookies
            domain = "." + url.split("/")[2].replace("www.", "")
            for c in cookies:
                try:
                    driver.add_cookie({'name': c.name, 'value': c.value, 'domain': domain})
                except:
                    pass
        
        driver.get(url)
        time.sleep(wait_time) # Wait for page and potentially video to load

        video_name = extract_video_name(driver)
        
        logs = driver.get_log('performance')
        for log in logs:
            log_message = json.loads(log['message'])
            message = log_message.get('message', {})
            if message.get('method') == 'Network.responseReceived':
                response = message.get('params', {}).get('response', {})
                mime = response.get('mimeType', '')
                r_url = response.get('url', '')
                if 'video' in mime or any(ext in r_url for ext in ('.mp4', '.m3u8', '.wav')):
                    if r_url and r_url not in video_links:
                        video_links.append(r_url)
                        
    except (NoSuchWindowException, WebDriverException) as e:
        log_error(f"WebDriver error: {e}")
        raise
    except Exception as e:
        log_error(f"Error during Selenium interception: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
                
    return video_name, video_links

def extract_main_video_url(driver):
    """Searches for and extracts the main video URL from the page via <video> tag."""
    try:
        video_element = driver.find_element(By.TAG_NAME, 'video')
        video_url = video_element.get_attribute('src')
        if video_url and any(ext in video_url for ext in (".mp4", ".wav")):
            return video_url
    except NoSuchElementException:
        pass
    except Exception as e:
        log_error(f"Error extracting main video URL: {e}")
    return None
