"""
HTML Optimizer for LLM extraction.

Prepares HTML content for LLM processing by removing unnecessary elements
while preserving the content structure that LLM can understand.
"""

from __future__ import annotations

import json
import re
from typing import Optional


def optimize_html(html: str, max_chars: int = 100000) -> str:
    """
    Clean HTML for LLM processing.

    Removes scripts, styles, and other non-content elements while
    preserving the HTML structure that LLM can read and extract from.

    Args:
        html: Raw HTML content
        max_chars: Maximum characters to return

    Returns:
        Cleaned HTML suitable for LLM extraction
    """
    import logging
    logger = logging.getLogger(__name__)

    if not html:
        return ""

    logger.info(f"Before optimize: {len(html)} chars, has ₽: {'₽' in html}")

    # Remove scripts, styles, and other non-content elements
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<svg[^>]*>.*?</svg>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

    logger.info(f"After strip: {len(html)} chars, has ₽: {'₽' in html}")

    # Collapse whitespace
    html = re.sub(r'\s+', ' ', html)

    logger.info(f"After whitespace: {len(html)} chars, has ₽: {'₽' in html}")

    # Truncate if needed
    if len(html) > max_chars:
        html = html[:max_chars] + "\n[truncated]"
        logger.info(f"After truncate: {len(html)} chars, has ₽: {'₽' in html}")

    return html.strip()


def extract_structured_hints(html: str) -> dict[str, Optional[str]]:
    """
    Extract structured data from JSON-LD and Open Graph tags.
    """
    hints: dict[str, Optional[str]] = {}

    # Open Graph tags
    og_patterns = {
        'og_title': r'<meta\s+(?:property=["\']og:title["\'].*?content=["\']([^"\']*)["\']|content=["\']([^"\']*)["\'].*?property=["\']og:title["\'])',
        'og_description': r'<meta\s+(?:property=["\']og:description["\'].*?content=["\']([^"\']*)["\']|content=["\']([^"\']*)["\'].*?property=["\']og:description["\'])',
        'og_image': r'<meta\s+(?:property=["\']og:image["\'].*?content=["\']([^"\']*)["\']|content=["\']([^"\']*)["\'].*?property=["\']og:image["\'])',
        'og_price': r'<meta\s+property=["\'](?:og:price:amount|product:price:amount)["\'].*?content=["\']([^"\']*)["\']',
        'og_currency': r'<meta\s+property=["\'](?:og:price:currency|product:price:currency)["\'].*?content=["\']([^"\']*)["\']',
    }

    for key, pattern in og_patterns.items():
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            # Get first non-None group
            value = next((g for g in match.groups() if g), None)
            if value:
                hints[key] = value

    # JSON-LD schema.org data
    jsonld_matches = re.findall(
        r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE
    )
    for jsonld_content in jsonld_matches:
        try:
            data = json.loads(jsonld_content)

            # Handle @graph wrapper
            if isinstance(data, dict) and '@graph' in data:
                data = data['@graph']

            items = data if isinstance(data, list) else [data]

            for item in items:
                if not isinstance(item, dict):
                    continue

                item_type = str(item.get('@type', ''))
                if 'Product' in item_type:
                    hints['schema_name'] = hints.get('schema_name') or item.get('name')
                    hints['schema_description'] = hints.get('schema_description') or item.get('description')

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
    max_chars: int = 100000,
) -> str:
    """
    Format HTML content for LLM extraction.

    Args:
        html: Raw HTML content
        url: Page URL
        title: Page title
        max_chars: Maximum characters for content

    Returns:
        Formatted content for LLM
    """
    import logging
    logger = logging.getLogger(__name__)

    # Extract structured hints first
    hints = extract_structured_hints(html)

    # Build the prompt content
    parts = [f"URL: {url}", f"Page title: {title}"]

    # Add structured hints if available
    if hints:
        hint_lines = ["", "=== Structured metadata ==="]
        if hints.get('schema_price'):
            hint_lines.append(f"  PRICE: {hints['schema_price']} {hints.get('schema_currency', '')}")
        if hints.get('og_price'):
            hint_lines.append(f"  OG_PRICE: {hints['og_price']} {hints.get('og_currency', '')}")
        for key, value in hints.items():
            if value and key not in ('schema_price', 'schema_currency', 'og_price', 'og_currency'):
                hint_lines.append(f"  {key}: {value}")
        parts.append('\n'.join(hint_lines))

    # Add cleaned HTML - LLM will extract from this
    content = optimize_html(html, max_chars=max_chars)
    parts.append(f"\nPage HTML:\n{content}")

    result = '\n'.join(parts)
    logger.info(f"Formatted content: {len(result)} chars, has ₽: {'₽' in result}")
    return result
