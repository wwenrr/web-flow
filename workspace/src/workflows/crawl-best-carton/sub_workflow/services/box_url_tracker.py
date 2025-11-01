from html.parser import HTMLParser
from typing import List, Set

from src.common.base.singleton import Singleton


class BoxUrlTracker(Singleton):
    """
    Service to track and extract box URLs from HTML content.
    Finds URLs matching pattern /cardboard/box/xxx.html
    """

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._tracked_urls: Set[str] = set()

    def perform(self, html_content: str) -> List[str]:
        """
        Extract box URLs from HTML content.
        
        Args:
            html_content: HTML content string
            
        Returns:
            List[str]: List of box URLs (e.g., "/cardboard/box/0035.html")
        """
        parser = _BoxUrlParser()
        parser.feed(html_content)
        box_urls = parser.urls
        self._tracked_urls.update(box_urls)
        return box_urls

    def get_tracked_urls(self) -> List[str]:
        """
        Get all tracked box URLs.
        
        Returns:
            List[str]: List of all tracked box URLs
        """
        return sorted(list(self._tracked_urls))

    def is_tracked(self, url: str) -> bool:
        """
        Check if a URL has been tracked.
        
        Args:
            url: URL to check
            
        Returns:
            bool: True if URL has been tracked
        """
        return url in self._tracked_urls

    def clear_tracked(self) -> None:
        """
        Clear all tracked URLs.
        """
        self._tracked_urls.clear()


class _BoxUrlParser(HTMLParser):
    """
    Helper class to parse HTML and extract box URLs matching /cardboard/box/xxx.html pattern.
    """

    def __init__(self):
        super().__init__()
        self.urls: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "a":
            for attr_name, attr_value in attrs:
                if attr_name == "href" and attr_value:
                    if self._is_box_url(attr_value):
                        # Normalize URL (remove domain if present, ensure it starts with /)
                        normalized = self._normalize_url(attr_value)
                        if normalized not in self.urls:
                            self.urls.append(normalized)

    def _is_box_url(self, url: str) -> bool:
        """
        Check if URL matches pattern /cardboard/box/xxx.html
        
        Args:
            url: URL to check
            
        Returns:
            bool: True if URL matches pattern
        """
        if not url:
            return False
        
        # Remove domain and query params
        clean_url = url.split("?")[0].split("#")[0]
        
        # Check if it matches /cardboard/box/xxx.html pattern
        if "/cardboard/box/" in clean_url and clean_url.endswith(".html"):
            # Extract the part after /cardboard/box/
            parts = clean_url.split("/cardboard/box/")
            if len(parts) == 2:
                filename = parts[1]
                # Check if filename is a number followed by .html
                if filename.replace(".html", "").isdigit():
                    return True
        return False

    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL to relative path starting with /cardboard/box/
        
        Args:
            url: URL to normalize
            
        Returns:
            str: Normalized URL path
        """
        # Remove domain if present
        if "http://" in url or "https://" in url:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            url = parsed.path
        
        # Remove query params and fragments
        url = url.split("?")[0].split("#")[0]
        
        # Ensure it starts with /
        if not url.startswith("/"):
            url = "/" + url
        
        return url

