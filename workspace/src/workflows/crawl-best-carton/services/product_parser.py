import re
from html.parser import HTMLParser
from typing import Any


class ProductParser:
    """
    Service to parse product HTML and extract product information.
    """

    def perform(self, html_content: str, url: str = "") -> dict[str, Any]:
        """
        Parse HTML content and extract product information.
        
        Args:
            html_content: HTML content from #section_specs element
            url: Product URL (optional, used to extract product_id)
        
        Returns:
            dict: Product information with keys: url, product_id, length, width, height, volume,
                  outer_length, outer_width, outer_height, outer_volume, weight
        """
        parser = _ProductHTMLParser()
        parser.feed(html_content)
        
        # Calculate outer volume from outer dimensions
        outer_volume = 0.0
        if parser.outer_length and parser.outer_width and parser.outer_height:
            outer_volume = parser.outer_length * parser.outer_width * parser.outer_height
        
        result: dict[str, Any] = {
            "url": url,
            "product_id": self._extract_product_id(url),
            "length": parser.internal_length or 0.0,
            "width": parser.internal_width or 0.0,
            "height": parser.internal_height or 0.0,
            "volume": parser.volume or 0.0,
            "outer_length": parser.outer_length or 0.0,
            "outer_width": parser.outer_width or 0.0,
            "outer_height": parser.outer_height or 0.0,
            "outer_volume": outer_volume,
            "weight": parser.weight or 0.0,
        }
        
        return result

    def _extract_product_id(self, url: str) -> str:
        """
        Extract product ID from URL.
        
        Args:
            url: Product URL (e.g., "https://www.bestcarton.com/cardboard/box/1883.html")
        
        Returns:
            str: Product ID extracted from URL or empty string
        """
        if not url:
            return ""
        
        # Extract from URL like /cardboard/box/1883.html -> 1883
        match = re.search(r'/box/(\d+)\.html', url)
        if match:
            return match.group(1)
        
        # Extract from URL like /cardboard/box/xxx.html -> xxx
        match = re.search(r'/box/([^/]+)\.html', url)
        if match:
            return match.group(1)
        
        return ""


class _ProductHTMLParser(HTMLParser):
    """
    Helper class to parse product HTML and extract dimensions and volume.
    """

    def __init__(self):
        super().__init__()
        self.internal_length: float | None = None
        self.internal_width: float | None = None
        self.internal_height: float | None = None
        self.outer_length: float | None = None
        self.outer_width: float | None = None
        self.outer_height: float | None = None
        self.volume: float | None = None
        self.weight: float | None = None
        self._in_internal_dims = False
        self._in_external_dims = False
        self._in_volume = False
        self._in_weight = False
        self._current_data = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "dt":
            self._current_data = ""
        elif tag == "dd":
            self._current_data = ""

    def handle_data(self, data: str) -> None:
        self._current_data += data.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "dt":
            text = self._current_data.strip()
            if "内寸法" in text:
                self._in_internal_dims = True
            elif "外寸法" in text:
                self._in_external_dims = True
            elif "容量" in text:
                self._in_volume = True
            elif "重量" in text:
                self._in_weight = True
            else:
                self._in_internal_dims = False
                self._in_external_dims = False
                self._in_volume = False
                self._in_weight = False
        elif tag == "dd":
            text = self._current_data.strip()
            
            if self._in_internal_dims:
                # Parse format: 630×200×200 mm
                dims = self._parse_dimensions(text)
                if dims:
                    self.internal_length, self.internal_width, self.internal_height = dims
                self._in_internal_dims = False
            elif self._in_external_dims:
                # Parse format: 636×206×212(深さ) mm
                dims = self._parse_dimensions(text)
                if dims:
                    self.outer_length, self.outer_width, self.outer_height = dims
                self._in_external_dims = False
            elif self._in_volume:
                # Parse format: 25.2 L
                volume = self._parse_volume(text)
                if volume is not None:
                    self.volume = volume
                self._in_volume = False
            elif self._in_weight:
                # Parse format: 365 g
                weight = self._parse_weight(text)
                if weight is not None:
                    self.weight = weight
                self._in_weight = False
            
            self._current_data = ""

    def _parse_dimensions(self, text: str) -> tuple[float, float, float] | None:
        """
        Parse dimensions from text like "630×200×200 mm" or "636×206×212(深さ) mm".
        
        Args:
            text: Text containing dimensions
        
        Returns:
            tuple[float, float, float] | None: (length, width, height) in cm, or None
        """
        # Remove unit and extra text
        text = re.sub(r'\([^)]*\)', '', text)  # Remove (深さ)
        text = re.sub(r'\s*mm\s*$', '', text)  # Remove mm
        text = re.sub(r'\s*cm\s*$', '', text)  # Remove cm
        
        # Match pattern: number×number×number
        match = re.search(r'(\d+(?:\.\d+)?)×(\d+(?:\.\d+)?)×(\d+(?:\.\d+)?)', text)
        if match:
            length = float(match.group(1))
            width = float(match.group(2))
            height = float(match.group(3))
            
            # Convert mm to cm if needed (assuming values > 100 are in mm)
            if length > 100:
                length = length / 10.0
            if width > 100:
                width = width / 10.0
            if height > 100:
                height = height / 10.0
            
            return (length, width, height)
        
        return None

    def _parse_volume(self, text: str) -> float | None:
        """
        Parse volume from text like "25.2 L".
        
        Args:
            text: Text containing volume
        
        Returns:
            float | None: Volume in L (or converted to cm³ if needed), or None
        """
        # Match pattern: number L or numberL
        match = re.search(r'(\d+(?:\.\d+)?)\s*L', text, re.IGNORECASE)
        if match:
            volume_l = float(match.group(1))
            # Convert L to cm³ (1 L = 1000 cm³)
            return volume_l * 1000.0
        
        # Match pattern: number cm³ or numbercm³
        match = re.search(r'(\d+(?:\.\d+)?)\s*cm³', text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        
        return None

    def _parse_weight(self, text: str) -> float | None:
        """
        Parse weight from text like "365 g" or "968 g".
        
        Args:
            text: Text containing weight
        
        Returns:
            float | None: Weight in g, or None
        """
        # Match pattern: number g or numberg
        match = re.search(r'(\d+(?:\.\d+)?)\s*g', text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        
        # Match pattern: number kg or numberkg
        match = re.search(r'(\d+(?:\.\d+)?)\s*kg', text, re.IGNORECASE)
        if match:
            # Convert kg to g
            return float(match.group(1)) * 1000.0
        
        return None

