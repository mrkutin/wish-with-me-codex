from __future__ import annotations

import html
import logging
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# Minimum size in pixels for product images (filters icons/badges)
MIN_PRODUCT_IMAGE_SIZE = 50


class ImageCandidate:
    """Represents an image found in HTML with its relevant attributes."""

    def __init__(self, src: str, **attrs: Any) -> None:
        self.src = src
        self.alt = attrs.get("alt", "")
        self.title = attrs.get("title", "")
        self.class_name = attrs.get("class", "")
        self.width = attrs.get("width", "")
        self.height = attrs.get("height", "")
        # Collect data-* attributes
        self.data_attrs = {k: v for k, v in attrs.items() if k.startswith("data-")}

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"src": self.src}
        if self.alt:
            result["alt"] = self.alt
        if self.title:
            result["title"] = self.title
        if self.class_name:
            result["class"] = self.class_name
        if self.width:
            result["width"] = self.width
        if self.height:
            result["height"] = self.height
        if self.data_attrs:
            result["data"] = self.data_attrs
        return result

    def __repr__(self) -> str:
        return f"ImageCandidate(src={self.src!r}, alt={self.alt!r})"


class ImageExtractor(HTMLParser):
    """Fast HTML parser to extract image tags and their attributes."""

    def __init__(self) -> None:
        super().__init__()
        self.images: list[ImageCandidate] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            attrs_dict = {k: v or "" for k, v in attrs}
            src = attrs_dict.get("src", "").strip()
            if src and not self._is_excluded(src, attrs_dict):
                # Remove 'src' from attrs_dict to avoid passing it twice
                other_attrs = {k: v for k, v in attrs_dict.items() if k != "src"}
                self.images.append(ImageCandidate(src, **other_attrs))

    def _is_excluded(self, src: str, attrs: dict[str, str]) -> bool:
        """Filter out non-product images like icons, badges, tracking pixels."""
        src_lower = src.lower()

        # Exclude tiny images (likely icons/badges)
        try:
            width = int(attrs.get("width", "0") or "0")
            height = int(attrs.get("height", "0") or "0")

            # If only width is set and it's tiny, exclude
            if width > 0 and width < MIN_PRODUCT_IMAGE_SIZE and height == 0:
                return True
            # If only height is set and it's tiny, exclude
            if height > 0 and height < MIN_PRODUCT_IMAGE_SIZE and width == 0:
                return True
            # If both are set, exclude only if BOTH are tiny
            if width > 0 and height > 0 and width < MIN_PRODUCT_IMAGE_SIZE and height < MIN_PRODUCT_IMAGE_SIZE:
                return True
        except (ValueError, TypeError):
            pass

        # Exclude common non-product patterns using word boundaries
        excluded_patterns = [
            r'\bicon\b',
            r'\blogo\b',
            r'\bbadge\b',
            r'\bsprite\b',
            r'\bplaceholder\b',
            r'\bpixel\b',
            r'\btracking\b',
            r'\banalytics\b',
            r'\bcounter\b',
            r'\.gif$',  # .gif at end of path only
            r'\b1x1\b',
            r'\bblank\b',
            r'\bspacer\b',
            r'\bavatar\b',
            r'\buser\b',
            r'\bprofile\b',
        ]

        for pattern in excluded_patterns:
            if re.search(pattern, src_lower):
                return True
            if re.search(pattern, attrs.get("class", "").lower()):
                return True
            if re.search(pattern, attrs.get("alt", "").lower()):
                return True

        return False


def extract_images_from_html(html: str, base_url: str | None = None) -> list[dict[str, Any]]:
    """
    Extract product image candidates from HTML.

    Returns list of image dictionaries with src and relevant attributes.
    Filters out icons, badges, tracking pixels, data URIs, etc.
    """
    parser = ImageExtractor()
    try:
        parser.feed(html)
    except Exception as e:
        # Log parsing errors for observability
        logger.warning("HTML parsing failed, returning partial results: %s", str(e), exc_info=True)

    images = []
    for img in parser.images:
        src = img.src

        # Skip data URIs - they're already embedded and can be huge
        if src.startswith("data:"):
            continue

        # Resolve relative URLs if base_url provided
        if base_url and not src.startswith(("http://", "https://")):
            try:
                src = urljoin(base_url, src)
                # Validate the resolved URL is well-formed
                parsed = urlparse(src)
                if not parsed.scheme or not parsed.netloc:
                    logger.debug("Skipping malformed URL after resolution: %s", src)
                    continue
            except Exception as e:
                logger.debug("Failed to resolve URL %s: %s", src, str(e))
                continue

        img_dict = img.to_dict()
        img_dict["src"] = src
        images.append(img_dict)

    return images


def format_images_for_llm(images: list[dict[str, Any]], max_images: int = 20) -> str:
    """
    Format image candidates as compact text for LLM.

    Limits to top N images and formats as simple list.
    Escapes HTML entities to prevent injection attacks.
    """
    if not images:
        return "No images found."

    # Limit number of images to avoid bloating prompt
    limited = images[:max_images]

    lines = []
    for i, img in enumerate(limited, 1):
        parts = [f"{i}. {img['src']}"]
        if img.get("alt"):
            # Escape to prevent XSS/injection
            parts.append(f"alt=\"{html.escape(img['alt'])}\"")
        if img.get("title"):
            parts.append(f"title=\"{html.escape(img['title'])}\"")
        if img.get("class"):
            parts.append(f"class=\"{html.escape(img['class'])}\"")
        lines.append(" ".join(parts))

    return "\n".join(lines)
