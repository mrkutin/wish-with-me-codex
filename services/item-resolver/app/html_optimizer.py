"""
HTML Optimizer for LLM extraction.

Extracts clean, minimal text content from HTML pages for LLM processing.
Designed for limited context windows (e.g., DeepSeek's 64K tokens).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Optional


class ContentExtractor(HTMLParser):
    """
    Extract visible text content from HTML, stripping scripts, styles, and other artifacts.

    This parser:
    - Removes script, style, noscript, svg, iframe content
    - Preserves text structure with newlines
    - Keeps meaningful whitespace
    - Does NOT hardcode any site-specific selectors
    """

    # Tags whose content should be completely ignored
    IGNORED_TAGS = frozenset({
        'script', 'style', 'noscript', 'svg', 'iframe', 'object', 'embed',
        'template', 'canvas', 'audio', 'video', 'source', 'track',
        'map', 'area', 'base', 'link', 'meta', 'head', 'title',
    })

    # Tags that should add a newline after their content
    BLOCK_TAGS = frozenset({
        'p', 'div', 'section', 'article', 'main', 'aside', 'header', 'footer',
        'nav', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'tr', 'td', 'th',
        'blockquote', 'pre', 'address', 'figure', 'figcaption', 'form',
        'fieldset', 'legend', 'details', 'summary', 'br', 'hr',
    })

    def __init__(self) -> None:
        super().__init__()
        self._text_parts: list[str] = []
        self._ignore_depth = 0
        self._current_tag_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        self._current_tag_stack.append(tag_lower)

        if tag_lower in self.IGNORED_TAGS:
            self._ignore_depth += 1

        # Add newline before block elements for structure
        if tag_lower in self.BLOCK_TAGS and self._text_parts:
            self._text_parts.append('\n')

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower in self.IGNORED_TAGS:
            self._ignore_depth = max(0, self._ignore_depth - 1)

        # Add newline after block elements
        if tag_lower in self.BLOCK_TAGS:
            self._text_parts.append('\n')

        # Pop from stack if matching
        if self._current_tag_stack and self._current_tag_stack[-1] == tag_lower:
            self._current_tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._ignore_depth > 0:
            return

        # Normalize whitespace but preserve meaningful content
        text = data.strip()
        if text:
            self._text_parts.append(text)
            self._text_parts.append(' ')

    def handle_entityref(self, name: str) -> None:
        if self._ignore_depth > 0:
            return
        # Convert common entities
        entities = {
            'nbsp': ' ', 'amp': '&', 'lt': '<', 'gt': '>',
            'quot': '"', 'apos': "'", 'mdash': '—', 'ndash': '–',
            'laquo': '«', 'raquo': '»', 'copy': '©', 'reg': '®',
            'euro': '€', 'pound': '£', 'yen': '¥',
        }
        self._text_parts.append(entities.get(name, f'&{name};'))

    def handle_charref(self, name: str) -> None:
        if self._ignore_depth > 0:
            return
        try:
            if name.startswith('x') or name.startswith('X'):
                char = chr(int(name[1:], 16))
            else:
                char = chr(int(name))
            self._text_parts.append(char)
        except (ValueError, OverflowError):
            self._text_parts.append(f'&#{name};')

    def get_text(self) -> str:
        """Return the extracted text content."""
        return ''.join(self._text_parts)


def _normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace while preserving paragraph structure.

    - Collapse multiple spaces to single space
    - Collapse multiple newlines to double newline (paragraph break)
    - Strip leading/trailing whitespace from lines
    """
    # Split into lines and strip each
    lines = [line.strip() for line in text.split('\n')]

    # Remove empty lines but keep paragraph structure
    result_lines: list[str] = []
    prev_empty = False

    for line in lines:
        if not line:
            if not prev_empty and result_lines:
                result_lines.append('')  # Keep one empty line for paragraph break
            prev_empty = True
        else:
            # Collapse multiple spaces within line
            line = re.sub(r' +', ' ', line)
            result_lines.append(line)
            prev_empty = False

    return '\n'.join(result_lines)


def _extract_price_info(html: str) -> list[str]:
    """
    Extract price-related information from HTML using common patterns.

    This finds prices in various formats without hardcoding selectors.
    """
    prices: list[str] = []

    # Common price patterns (Russian and international)
    patterns = [
        # Russian ruble formats
        r'(\d[\d\s,.]*)\s*(?:₽|руб\.?|RUB|rub)',
        r'(?:₽|руб\.?|RUB)\s*(\d[\d\s,.]*)',
        # Dollar/Euro formats
        r'\$\s*(\d[\d\s,.]*)',
        r'(\d[\d\s,.]*)\s*\$',
        r'€\s*(\d[\d\s,.]*)',
        r'(\d[\d\s,.]*)\s*€',
        # Generic price with currency code
        r'(\d{1,3}(?:[\s,]\d{3})*(?:[.,]\d{2})?)\s*(?:USD|EUR|RUB|GBP)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0] if match[0] else match[1] if len(match) > 1 else ''
            if match:
                # Clean up the number
                clean = re.sub(r'[\s]', '', match)
                if clean and len(clean) <= 15:  # Reasonable price length
                    prices.append(clean)

    return list(set(prices))[:5]  # Return unique prices, max 5


def optimize_html(
    html: str,
    max_chars: int = 30000,
    include_price_hints: bool = True,
) -> str:
    """
    Extract optimized text content from HTML for LLM processing.

    Args:
        html: Raw HTML content
        max_chars: Maximum characters to return (default 30K for DeepSeek)
        include_price_hints: Whether to extract and prepend price hints

    Returns:
        Clean text content suitable for LLM extraction
    """
    if not html:
        return ""

    # Extract text content
    parser = ContentExtractor()
    try:
        parser.feed(html)
    except Exception:
        # If parsing fails, try a simple regex fallback
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = _normalize_whitespace(text)
    else:
        text = parser.get_text()

    # Normalize whitespace
    text = _normalize_whitespace(text)

    # Optionally prepend price hints
    if include_price_hints:
        prices = _extract_price_info(html)
        if prices:
            price_hint = f"[Price candidates found: {', '.join(prices)}]\n\n"
            text = price_hint + text

    # Truncate if needed
    if len(text) > max_chars:
        text = text[:max_chars]
        # Try to end at a sentence or word boundary
        last_period = text.rfind('.')
        last_newline = text.rfind('\n')
        last_space = text.rfind(' ')

        # Prefer sentence boundary, then paragraph, then word
        cut_point = max(last_period, last_newline, last_space)
        if cut_point > max_chars * 0.8:  # Only if we're not losing too much
            text = text[:cut_point + 1]

        text = text.rstrip() + "\n[content truncated]"

    return text


def extract_structured_hints(html: str) -> dict[str, Optional[str]]:
    """
    Extract structured data hints from HTML meta tags and schema.org markup.

    This provides additional context without relying on page structure.
    """
    hints: dict[str, Optional[str]] = {}

    # Open Graph tags
    og_patterns = {
        'og_title': r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']*)["\']',
        'og_description': r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']*)["\']',
        'og_image': r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']*)["\']',
        'og_price': r'<meta\s+property=["\'](?:og:price:amount|product:price:amount)["\']\s+content=["\']([^"\']*)["\']',
        'og_currency': r'<meta\s+property=["\'](?:og:price:currency|product:price:currency)["\']\s+content=["\']([^"\']*)["\']',
    }

    for key, pattern in og_patterns.items():
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            hints[key] = match.group(1)

    # Also try reversed attribute order
    og_patterns_rev = {
        'og_title': r'<meta\s+content=["\']([^"\']*)["\'].*?property=["\']og:title["\']',
        'og_description': r'<meta\s+content=["\']([^"\']*)["\'].*?property=["\']og:description["\']',
    }

    for key, pattern in og_patterns_rev.items():
        if key not in hints:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                hints[key] = match.group(1)

    # JSON-LD schema.org data (basic extraction)
    jsonld_match = re.search(
        r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE
    )
    if jsonld_match:
        try:
            import json
            data = json.loads(jsonld_match.group(1))
            if isinstance(data, dict):
                if data.get('@type') == 'Product' or 'Product' in str(data.get('@type', '')):
                    hints['schema_name'] = data.get('name')
                    hints['schema_description'] = data.get('description')
                    if 'offers' in data:
                        offers = data['offers']
                        if isinstance(offers, list) and offers:
                            offers = offers[0]
                        if isinstance(offers, dict):
                            hints['schema_price'] = str(offers.get('price', ''))
                            hints['schema_currency'] = offers.get('priceCurrency')
        except Exception:
            pass

    return {k: v for k, v in hints.items() if v}


def format_html_for_llm(
    html: str,
    url: str,
    title: str,
    max_chars: int = 30000,
) -> str:
    """
    Format HTML content for LLM extraction, including structured hints.

    Args:
        html: Raw HTML content
        url: Page URL
        title: Page title
        max_chars: Maximum characters for main content

    Returns:
        Formatted text prompt content for LLM
    """
    # Extract structured hints first
    hints = extract_structured_hints(html)

    # Build the prompt content
    parts = [f"URL: {url}", f"Page title: {title}"]

    # Add structured hints if available
    if hints:
        hint_lines = ["", "Structured metadata found:"]
        for key, value in hints.items():
            if value:
                hint_lines.append(f"  {key}: {value}")
        parts.append('\n'.join(hint_lines))

    # Add optimized page content
    content = optimize_html(html, max_chars=max_chars)
    parts.append(f"\nPage content:\n{content}")

    return '\n'.join(parts)
