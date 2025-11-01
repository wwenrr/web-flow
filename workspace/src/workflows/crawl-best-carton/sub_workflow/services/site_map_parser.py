from html.parser import HTMLParser
from typing import List

from src.common.base.singleton import Singleton


class SiteMapParser(Singleton):
    """
    Service to parse site map HTML and extract category URLs.
    """

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True

    def perform(self, html_content: str) -> List[str]:
        """
        Parse category URLs from HTML content.
        
        Args:
            html_content: HTML content string
            
        Returns:
            List[str]: List of category URLs (starting with /category/)
        """
        parser = _HtmlUrlParser()
        parser.feed(html_content)
        category_urls = [url for url in parser.urls if url.startswith("/category/")]
        return category_urls


class _HtmlUrlParser(HTMLParser):
    """
    Helper class to parse HTML and extract href attributes from <a> tags.
    """

    def __init__(self):
        super().__init__()
        self.urls: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "a":
            for attr_name, attr_value in attrs:
                if attr_name == "href" and attr_value:
                    self.urls.append(attr_value)

