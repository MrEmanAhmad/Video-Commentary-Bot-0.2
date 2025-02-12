"""
Step 1: Video download module
Downloads videos from various sources using yt-dlp
"""

import logging
import os
import re
from pathlib import Path
from typing import Tuple, Dict, Optional, Any
import yt_dlp
from datetime import datetime
import json
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

# Constants
MAX_VIDEO_DURATION = 120  # Maximum video duration in seconds (2 minutes)

class VideoDownloader:
    """Downloads videos using yt-dlp."""
    
    def __init__(self, output_dir: Path):
        """
        Initialize video downloader.
        
        Args:
            output_dir: Directory to save downloaded videos
        """
        self.output_dir = output_dir
        self.cookie_file = None
    
    def _get_youtube_cookies(self, url: str) -> Optional[str]:
        """Get cookies from YouTube using Selenium in headless mode."""
        try:
            logger.info("Initializing headless Chrome for cookie extraction...")
            
            # Configure Chrome options for headless mode
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")  # New headless mode
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            
            # Add stealth settings
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Set Chrome binary path based on OS
            if os.name == 'nt':  # Windows
                chrome_paths = [
                    os.environ.get('CHROME_BIN'),
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                ]
            else:  # Linux/Mac
                chrome_paths = [
                    os.environ.get('CHROME_BIN'),
                    '/usr/bin/google-chrome',
                    '/usr/bin/google-chrome-stable'
                ]
            
            # Find the first existing Chrome binary
            chrome_binary = next((path for path in chrome_paths if path and os.path.exists(path)), None)
            if chrome_binary:
                logger.info(f"Found Chrome binary at: {chrome_binary}")
                chrome_options.binary_location = chrome_binary
            else:
                logger.warning("Chrome binary not found in standard locations")
            
            # Create a temporary file for cookies
            cookie_fd, cookie_path = tempfile.mkstemp(suffix='.txt')
            os.close(cookie_fd)
            
            # Initialize Chrome driver with webdriver_manager
            service = Service(ChromeDriverManager(cache_valid_range=7).install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            try:
                # Set CDP command to modify navigator.webdriver flag
                driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
                })
                
                logger.info("Navigating to YouTube...")
                driver.get("https://www.youtube.com")
                
                # Wait for cookies to be set
                driver.implicitly_wait(5)
                
                # Get all cookies
                cookies = driver.get_cookies()
                
                # Write cookies in Netscape format
                with open(cookie_path, 'w', encoding='utf-8') as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    for cookie in cookies:
                        secure = "TRUE" if cookie.get('secure', False) else "FALSE"
                        http_only = "TRUE" if cookie.get('httpOnly', False) else "FALSE"
                        expiry = cookie.get('expiry', 0)
                        
                        cookie_line = (
                            f".youtube.com\tTRUE\t/\t{secure}\t{expiry}\t"
                            f"{cookie['name']}\t{cookie['value']}\n"
                        )
                        f.write(cookie_line)
                
                logger.info("Successfully extracted YouTube cookies")
                return cookie_path
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"Error getting YouTube cookies: {str(e)}")
            if os.path.exists(cookie_path):
                os.unlink(cookie_path)
            return None
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL to ensure compatibility."""
        # Convert x.com to twitter.com
        if 'x.com' in url:
            url = url.replace('x.com', 'twitter.com')
        # Ensure HTTPS
        if url.startswith('http://'):
            url = 'https://' + url[7:]
        return url
        
    def _sanitize_filename(self, title: str) -> str:
        """
        Sanitize the filename to remove problematic characters.
        
        Args:
            title: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove invalid characters
        title = re.sub(r'[<>:"/\\|?*]', '', title)
        # Replace spaces and dots with underscores
        title = re.sub(r'[\s.]+', '_', title)
        # Ensure it's not empty and not too long
        if not title:
            title = 'video'
        return title[:100].strip('_')  # Limit length to 100 chars
        
    def _get_ydl_opts(self, is_twitter: bool = False, cookie_file: Optional[str] = None) -> Dict[str, Any]:
        """Get yt-dlp options."""
        video_dir = self.output_dir / "video"
        video_dir.mkdir(parents=True, exist_ok=True)
        
        # Use timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        opts = {
            'outtmpl': str(video_dir / f'video_{timestamp}.%(ext)s'),
            'progress_hooks': [self._progress_hook],
            'verbose': True,
            'format': 'best',
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'no_warnings': True,
            'quiet': False,
            'extract_flat': False,
            'cookiefile': cookie_file,
            'source_address': '0.0.0.0',
            'force_generic_extractor': False,
            'sleep_interval': 1,
            'max_sleep_interval': 5,
            'sleep_interval_requests': 1,
            'max_sleep_interval_requests': 5,
            'http_chunk_size': 10485760,
            'retries': 10,
            'fragment_retries': 10,
            'retry_sleep_functions': {'http': lambda n: 5},
            'socket_timeout': 30,
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"'
            }
        }
        
        if is_twitter:
            opts.update({
                'extractor_args': {
                    'twitter': {
                        'api_key': None  # Let yt-dlp handle API key internally
                    }
                },
                'compat_opts': {
                    'no-youtube-unavailable-videos',
                    'no-youtube-prefer-utc',
                    'no-twitter-fail-incomplete'
                }
            })
        
        return opts
    
    def _progress_hook(self, d: Dict[str, Any]) -> None:
        """
        Progress hook for download status.
        
        Args:
            d: Download status dictionary
        """
        if d['status'] == 'finished':
            logger.info('Download completed')
            logger.info(f'Downloaded file: {d["filename"]}')
                
    def download(self, url: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Download video from URL.
        
        Args:
            url: Video URL
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Video metadata (dict or None)
            - Video title (str or None)
        """
        try:
            # Normalize URL first
            url = self._normalize_url(url)
            logger.info(f"Downloading video from: {url}")
            
            # Get YouTube cookies if needed
            cookie_file = None
            if 'youtube.com' in url or 'youtu.be' in url:
                cookie_file = self._get_youtube_cookies(url)
                if not cookie_file:
                    logger.warning("Failed to get YouTube cookies, attempting download without them")
            
            # First extract info without downloading to check duration
            with yt_dlp.YoutubeDL({'quiet': True, 'cookiefile': cookie_file}) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and info.get('duration', 0) > MAX_VIDEO_DURATION:
                    logger.error(f"Video duration ({info['duration']} seconds) exceeds maximum allowed duration ({MAX_VIDEO_DURATION} seconds)")
                    return False, None, None
            
            # If duration is acceptable, proceed with download
            is_twitter = 'twitter.com' in url
            with yt_dlp.YoutubeDL(self._get_ydl_opts(is_twitter, cookie_file)) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if info:
                    metadata = {
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration', 0),
                        'description': info.get('description', ''),
                        'uploader': info.get('uploader', 'Unknown'),
                        'view_count': info.get('view_count', 0),
                        'like_count': info.get('like_count', 0),
                        'upload_date': info.get('upload_date', '')
                    }
                    
                    # Save metadata
                    metadata_file = self.output_dir / "video_metadata.json"
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
                    
                    return True, metadata, self._sanitize_filename(info.get('title', 'video'))
                
        except Exception as e:
            logger.error(f"yt-dlp download error: {str(e)}")
            
        finally:
            # Cleanup cookie file
            if cookie_file and os.path.exists(cookie_file):
                try:
                    os.unlink(cookie_file)
                except Exception as e:
                    logger.warning(f"Failed to cleanup cookie file: {str(e)}")
            
        return False, None, None

def execute_step(url_or_path: str, output_dir: Path) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    Execute video download step.
    
    Args:
        url_or_path: Video URL or local file path
        output_dir: Directory to save downloaded video
        
    Returns:
        Tuple containing:
        - Success status (bool)
        - Video metadata (dict or None)
        - Video title (str or None)
    """
    downloader = VideoDownloader(output_dir)
    return downloader.download(url_or_path)

async def download_from_url(url: str, output_dir: Path) -> str:
    """
    Download video from URL asynchronously.
    
    Args:
        url: Video URL
        output_dir: Directory to save downloaded video
        
    Returns:
        Path to downloaded video file
    
    Raises:
        Exception if download fails
    """
    success, metadata, video_title = execute_step(url, output_dir)
    
    if not success:
        raise Exception("Failed to download video")
        
    # Look for the timestamp-based video file
    video_dir = output_dir / "video"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")  # Use partial timestamp for matching
    video_files = list(video_dir.glob(f"video_{timestamp}*.mp4"))
    
    if not video_files:
        raise Exception("Downloaded video file not found")
        
    # Return the most recently created file if multiple matches
    video_path = max(video_files, key=lambda p: p.stat().st_mtime)
    return str(video_path) 