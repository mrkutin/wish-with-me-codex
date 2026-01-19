from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin


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
            if width > 0 and height > 0 and (width < 50 or height < 50):
                return True
        except (ValueError, TypeError):
            pass

        # Exclude common non-product patterns
        excluded_patterns = [
            "icon",
            "logo",
            "badge",
            "sprite",
            "placeholder",
            "pixel",
            "tracking",
            "analytics",
            "counter",
            ".gif",  # Tracking pixels often use gif
            "1x1",
            "blank",
            "spacer",
            "avatar",
            "user",
            "profile",
        ]

        for pattern in excluded_patterns:
            if pattern in src_lower:
                return True
            if pattern in attrs.get("class", "").lower():
                return True
            if pattern in attrs.get("alt", "").lower():
                return True

        return False


def extract_images_from_html(html: str, base_url: str | None = None) -> list[dict[str, Any]]:
    """
    Extract product image candidates from HTML.

    Returns list of image dictionaries with src and relevant attributes.
    Filters out icons, badges, tracking pixels, etc.
    """
    parser = ImageExtractor()
    try:
        parser.feed(html)
    except Exception:
        # HTML parsing errors - return what we got so far
        pass

    images = []
    for img in parser.images:
        # Resolve relative URLs if base_url provided
        src = img.src
        if base_url and not src.startswith(("http://", "https://", "data:")):
            src = urljoin(base_url, src)

        img_dict = img.to_dict()
        img_dict["src"] = src
        images.append(img_dict)

    return images


def format_images_for_llm(images: list[dict[str, Any]], max_images: int = 20) -> str:
    """
    Format image candidates as compact text for LLM.

    Limits to top N images and formats as simple list.
    """
    if not images:
        return "No images found."

    # Limit number of images to avoid bloating prompt
    limited = images[:max_images]

    lines = []
    for i, img in enumerate(limited, 1):
        parts = [f"{i}. {img['src']}"]
        if img.get("alt"):
            parts.append(f"alt=\"{img['alt']}\"")
        if img.get("title"):
            parts.append(f"title=\"{img['title']}\"")
        if img.get("class"):
            parts.append(f"class=\"{img['class']}\"")
        lines.append(" ".join(parts))

    return "\n".join(lines)
