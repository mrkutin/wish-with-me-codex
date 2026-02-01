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
    import logging
    logger = logging.getLogger(__name__)

    prices: list[str] = []

    # Debug: log samples around currency symbols
    for symbol in ['₽', '$', '€']:
        idx = html.find(symbol)
        if idx >= 0:
            sample_start = max(0, idx - 30)
            sample_end = min(len(html), idx + 10)
            sample = html[sample_start:sample_end].replace('\n', ' ').replace('\r', '')
            logger.info(f"Found {symbol} in HTML at pos {idx}, context: ...{repr(sample)}...")
            break  # Just log one sample

    # Common price patterns (Russian and international)
    # Note: Russian prices often have spaces as thousand separators: "93 499"
    patterns = [
        # Russian ruble formats - with flexible spacing
        r'(\d{1,3}(?:[\s\u00a0]\d{3})+)\s*(?:₽|руб\.?|RUB)',  # "93 499 ₽" with space/nbsp
        r'(\d{4,})\s*(?:₽|руб\.?|RUB)',  # "93499₽" no space
        r'(\d{1,3}(?:[.,]\d{3})+)\s*(?:₽|руб\.?|RUB)',  # "93.499₽" or "93,499₽"
        r'(?:₽|руб\.?|RUB)\s*(\d[\d\s\u00a0.,]*\d)',  # "₽ 93 499"
        # Dollar formats
        r'\$\s*(\d[\d\s\u00a0.,]*\d)',
        r'(\d[\d\s\u00a0.,]*\d)\s*\$',
        # Euro formats
        r'€\s*(\d[\d\s\u00a0.,]*\d)',
        r'(\d[\d\s\u00a0.,]*\d)\s*€',
        # Generic price with currency code
        r'(\d{1,3}(?:[\s\u00a0,]\d{3})*(?:[.,]\d{2})?)\s*(?:USD|EUR|RUB|GBP)',
        # Price-like patterns near currency words (fallback)
        r'(?:price|цена|стоимость)[:\s]*(\d[\d\s\u00a0.,]*\d)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0] if match[0] else match[1] if len(match) > 1 else ''
            if match:
                # Clean up the number - remove spaces, nbsp, normalize separators
                clean = re.sub(r'[\s\u00a0]', '', match)  # Remove spaces and nbsp
                # Handle different decimal/thousand separators
                # If ends with ,XX or .XX it's likely decimal
                if re.match(r'.*[.,]\d{2}$', clean):
                    clean = clean[:-3].replace('.', '').replace(',', '') + clean[-3:]
                else:
                    clean = clean.replace('.', '').replace(',', '')
                if clean and clean.isdigit() and 3 <= len(clean) <= 10:  # Reasonable price
                    prices.append(clean)

    # Sort by value (likely the main price is a larger number on product pages)
    prices = sorted(set(prices), key=lambda x: int(x) if x.isdigit() else 0, reverse=True)
    return prices[:5]  # Return top 5 unique prices


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
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Price candidates from regex: {prices}")
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
    # Find ALL JSON-LD blocks, not just the first one
    jsonld_matches = re.findall(
        r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE
    )
    for jsonld_content in jsonld_matches:
        try:
            import json
            data = json.loads(jsonld_content)

            # Handle @graph wrapper (common pattern)
            if isinstance(data, dict) and '@graph' in data:
                data = data['@graph']

            # Handle list of items
            items = data if isinstance(data, list) else [data]

            for item in items:
                if not isinstance(item, dict):
                    continue

                item_type = item.get('@type', '')
                if isinstance(item_type, list):
                    item_type = ' '.join(item_type)

                if 'Product' in str(item_type):
                    hints['schema_name'] = hints.get('schema_name') or item.get('name')
                    hints['schema_description'] = hints.get('schema_description') or item.get('description')

                    # Extract price from offers
                    offers = item.get('offers') or item.get('Offers')
                    if offers:
                        if isinstance(offers, list) and offers:
                            offers = offers[0]
                        if isinstance(offers, dict):
                            price = offers.get('price') or offers.get('lowPrice') or offers.get('highPrice')
                            if price:
                                hints['schema_price'] = str(price)
                            hints['schema_currency'] = hints.get('schema_currency') or offers.get('priceCurrency')
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
    import logging
    logger = logging.getLogger(__name__)

    # Extract structured hints first
    hints = extract_structured_hints(html)
    logger.info(f"Structured hints extracted: {hints}")

    # Build the prompt content
    parts = [f"URL: {url}", f"Page title: {title}"]

    # Add structured hints if available - prioritize price info
    if hints:
        hint_lines = ["", "=== Structured metadata (IMPORTANT - use this if available) ==="]

        # Price hints first (most important)
        if hints.get('schema_price'):
            hint_lines.append(f"  PRICE: {hints['schema_price']} {hints.get('schema_currency', '')}")
        if hints.get('og_price'):
            hint_lines.append(f"  OG_PRICE: {hints['og_price']} {hints.get('og_currency', '')}")

        # Then other hints
        for key, value in hints.items():
            if value and key not in ('schema_price', 'schema_currency', 'og_price', 'og_currency'):
                hint_lines.append(f"  {key}: {value}")

        parts.append('\n'.join(hint_lines))

    # Add optimized page content
    content = optimize_html(html, max_chars=max_chars)
    parts.append(f"\nPage content:\n{content}")

    return '\n'.join(parts)
