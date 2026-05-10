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
    """
    driver = None
    video_links = []
    video_name = "video"
    
    try:
        options = Options()
        options.binary_location = browser_path
        options.add_argument("--incognito")
        
        # Performance logging for interception
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        if minimize_browser:
            options.add_argument("--window-position=0,3000")
            options.add_argument("--headless=new")

        driver = webdriver.Chrome(service=ChromeService(), options=options)
        
        if cookies:
            driver.get("about:blank")
            domain = "." + url.split("/")[2].replace("www.", "")
            for c in cookies:
                try:
                    driver.add_cookie({'name': c.name, 'value': c.value, 'domain': domain})
                except:
                    pass
        
        driver.get(url)
        time.sleep(wait_time)

        video_name = extract_video_name(driver)
        
        # Method 1: Performance logs (Intercepted URLs)
        logs = driver.get_log('performance')
        for log in logs:
            log_message = json.loads(log['message'])
            message = log_message.get('message', {})
            method = message.get('method')
            
            # Check both responseReceived and requestWillBeSent
            if method in ('Network.responseReceived', 'Network.requestWillBeSent'):
                params = message.get('params', {})
                r_url = params.get('response', {}).get('url') if method == 'Network.responseReceived' else params.get('request', {}).get('url')
                mime = params.get('response', {}).get('mimeType', '') if method == 'Network.responseReceived' else ''
                
                if r_url and r_url not in video_links:
                    if 'video' in mime or any(ext in r_url.lower() for ext in ('.mp4', '.m3u8', '.wav')):
                        # Filter out some noise
                        if not any(x in r_url for x in ('google-analytics', 'doubleclick', 'facebook.com')):
                            video_links.append(r_url)

        # Method 2: DOM Search (<video> tags)
        main_url = extract_main_video_url(driver)
        if main_url and main_url not in video_links:
            video_links.insert(0, main_url) # Prioritize direct DOM hits
                        
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
