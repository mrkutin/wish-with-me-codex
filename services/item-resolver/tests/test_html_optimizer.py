"""
Unit tests for HTML optimizer module.

Tests optimize_html, extract_structured_hints, and format_html_for_llm functions.
"""

from __future__ import annotations

import pytest

from app.html_optimizer import (
    extract_structured_hints,
    format_html_for_llm,
    optimize_html,
)


# =============================================================================
# optimize_html tests
# =============================================================================


class TestOptimizeHtml:
    """Tests for the optimize_html function."""

    def test_removes_script_tags(self) -> None:
        """Script tags and their content should be completely removed."""
        html = '<html><head><script>alert("xss")</script></head><body>content</body></html>'
        result = optimize_html(html)
        assert "<script" not in result
        assert "alert" not in result
        assert "content" in result

    def test_removes_script_tags_with_attributes(self) -> None:
        """Script tags with various attributes should be removed."""
        html = '<script type="text/javascript" src="app.js">var x = 1;</script><p>text</p>'
        result = optimize_html(html)
        assert "<script" not in result
        assert "var x" not in result
        assert "text" in result

    def test_removes_style_tags(self) -> None:
        """Style tags and their CSS content should be completely removed."""
        html = "<html><head><style>.red { color: red; }</style></head><body>content</body></html>"
        result = optimize_html(html)
        assert "<style" not in result
        assert ".red" not in result
        assert "color: red" not in result
        assert "content" in result

    def test_removes_style_tags_with_attributes(self) -> None:
        """Style tags with media queries and other attributes should be removed."""
        html = '<style type="text/css" media="screen">body { margin: 0; }</style><div>keep</div>'
        result = optimize_html(html)
        assert "<style" not in result
        assert "margin" not in result
        assert "keep" in result

    def test_removes_svg_tags(self) -> None:
        """SVG elements and their content should be completely removed."""
        html = '<div><svg width="100" height="100"><circle cx="50" cy="50" r="40"/></svg>text</div>'
        result = optimize_html(html)
        assert "<svg" not in result
        assert "circle" not in result
        assert "text" in result

    def test_removes_nested_svg(self) -> None:
        """Nested SVG content should be fully removed."""
        html = '<svg><g><path d="M0 0"/><text>icon</text></g></svg><span>visible</span>'
        result = optimize_html(html)
        assert "<svg" not in result
        assert "<path" not in result
        assert "icon" not in result
        assert "visible" in result

    def test_removes_noscript_tags(self) -> None:
        """Noscript tags and their content should be completely removed."""
        html = "<noscript><p>Enable JavaScript</p></noscript><p>main content</p>"
        result = optimize_html(html)
        assert "<noscript" not in result
        assert "Enable JavaScript" not in result
        assert "main content" in result

    def test_removes_html_comments(self) -> None:
        """HTML comments should be completely removed."""
        html = "<!-- This is a comment --><p>content</p><!-- Another comment -->"
        result = optimize_html(html)
        assert "<!--" not in result
        assert "-->" not in result
        assert "This is a comment" not in result
        assert "content" in result

    def test_removes_multiline_comments(self) -> None:
        """Multiline HTML comments should be removed."""
        html = """<!--
        This is a
        multiline comment
        --><div>text</div>"""
        result = optimize_html(html)
        assert "<!--" not in result
        assert "multiline" not in result
        assert "text" in result

    def test_collapses_whitespace(self) -> None:
        """Multiple spaces, tabs, and newlines should collapse to single space."""
        html = "<p>word1    word2</p>"
        result = optimize_html(html)
        assert "    " not in result
        assert "word1 word2" in result

    def test_collapses_newlines_and_tabs(self) -> None:
        """Newlines and tabs should be collapsed."""
        html = "<div>\n\t\ttext\n\n\tmore</div>"
        result = optimize_html(html)
        assert "\n" not in result
        assert "\t" not in result
        assert "text" in result
        assert "more" in result

    def test_truncates_long_content(self) -> None:
        """Content exceeding max_chars should be truncated."""
        html = "x" * 200
        result = optimize_html(html, max_chars=100)
        # 100 chars + newline + "[truncated]"
        assert len(result) <= 100 + len("\n[truncated]")

    def test_adds_truncated_marker(self) -> None:
        """Truncated content should end with [truncated] marker."""
        html = "a" * 500
        result = optimize_html(html, max_chars=100)
        assert result.endswith("[truncated]")

    def test_no_truncation_marker_when_within_limit(self) -> None:
        """Content within limit should not have truncation marker."""
        html = "<p>short content</p>"
        result = optimize_html(html, max_chars=1000)
        assert "[truncated]" not in result

    def test_empty_input(self) -> None:
        """Empty input should return empty string."""
        assert optimize_html("") == ""

    def test_none_like_empty_input(self) -> None:
        """Whitespace-only input should return empty string after strip."""
        result = optimize_html("   ")
        assert result == ""

    def test_preserves_important_tags(self) -> None:
        """Important content tags should be preserved."""
        html = "<html><body><div><p>paragraph</p><span>inline</span><a href='#'>link</a></div></body></html>"
        result = optimize_html(html)
        assert "<body>" in result or "<body" in result
        assert "<div>" in result
        assert "<p>" in result
        assert "<span>" in result
        assert "<a" in result
        assert "paragraph" in result
        assert "inline" in result
        assert "link" in result

    def test_preserves_product_related_tags(self) -> None:
        """Tags commonly used for product info should be preserved."""
        html = '<h1>Product Name</h1><h2 class="price">$99.99</h2><img src="photo.jpg" alt="product">'
        result = optimize_html(html)
        assert "<h1>" in result
        assert "Product Name" in result
        assert "$99.99" in result
        assert "<img" in result

    def test_case_insensitive_tag_removal(self) -> None:
        """Tag removal should be case-insensitive."""
        html = "<SCRIPT>bad</SCRIPT><STYLE>css</STYLE><SVG></SVG><NOSCRIPT>js</NOSCRIPT>content"
        result = optimize_html(html)
        assert "bad" not in result
        assert "css" not in result
        assert "js" not in result
        assert "content" in result


# =============================================================================
# extract_structured_hints tests
# =============================================================================


class TestExtractStructuredHints:
    """Tests for the extract_structured_hints function."""

    def test_extracts_og_title(self) -> None:
        """Should extract og:title from meta tag."""
        html = '<meta property="og:title" content="Product Title">'
        hints = extract_structured_hints(html)
        assert hints.get("og_title") == "Product Title"

    def test_extracts_og_title_reversed_attributes(self) -> None:
        """Should extract og:title when content comes before property."""
        html = '<meta content="Reversed Title" property="og:title">'
        hints = extract_structured_hints(html)
        assert hints.get("og_title") == "Reversed Title"

    def test_extracts_og_price(self) -> None:
        """Should extract og:price:amount from meta tag."""
        html = '<meta property="og:price:amount" content="29.99">'
        hints = extract_structured_hints(html)
        assert hints.get("og_price") == "29.99"

    def test_extracts_product_price_amount(self) -> None:
        """Should extract product:price:amount from meta tag."""
        html = '<meta property="product:price:amount" content="49.99">'
        hints = extract_structured_hints(html)
        assert hints.get("og_price") == "49.99"

    def test_extracts_og_currency(self) -> None:
        """Should extract og:price:currency from meta tag."""
        html = '<meta property="og:price:currency" content="USD">'
        hints = extract_structured_hints(html)
        assert hints.get("og_currency") == "USD"

    def test_extracts_og_image(self) -> None:
        """Should extract og:image from meta tag."""
        html = '<meta property="og:image" content="https://example.com/image.jpg">'
        hints = extract_structured_hints(html)
        assert hints.get("og_image") == "https://example.com/image.jpg"

    def test_extracts_og_image_reversed_attributes(self) -> None:
        """Should extract og:image when content comes before property."""
        html = '<meta content="https://example.com/photo.png" property="og:image">'
        hints = extract_structured_hints(html)
        assert hints.get("og_image") == "https://example.com/photo.png"

    def test_extracts_og_description(self) -> None:
        """Should extract og:description from meta tag."""
        html = '<meta property="og:description" content="This is a product description">'
        hints = extract_structured_hints(html)
        assert hints.get("og_description") == "This is a product description"

    def test_extracts_og_description_reversed_attributes(self) -> None:
        """Should extract og:description when content comes before property."""
        html = '<meta content="Reversed description" property="og:description">'
        hints = extract_structured_hints(html)
        assert hints.get("og_description") == "Reversed description"

    def test_extracts_jsonld_product(self) -> None:
        """Should extract Product type from JSON-LD."""
        html = '''
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "JSON-LD Product",
            "description": "A great product"
        }
        </script>
        '''
        hints = extract_structured_hints(html)
        assert hints.get("schema_name") == "JSON-LD Product"
        assert hints.get("schema_description") == "A great product"

    def test_extracts_jsonld_price(self) -> None:
        """Should extract offers.price from JSON-LD Product."""
        html = '''
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "Priced Item",
            "offers": {
                "price": "199.99"
            }
        }
        </script>
        '''
        hints = extract_structured_hints(html)
        assert hints.get("schema_price") == "199.99"

    def test_extracts_jsonld_low_price(self) -> None:
        """Should extract offers.lowPrice from JSON-LD Product."""
        html = '''
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "Range Priced",
            "offers": {
                "lowPrice": "50.00",
                "highPrice": "100.00"
            }
        }
        </script>
        '''
        hints = extract_structured_hints(html)
        assert hints.get("schema_price") == "50.00"

    def test_extracts_jsonld_currency(self) -> None:
        """Should extract priceCurrency from JSON-LD Product offers."""
        html = '''
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "Currency Product",
            "offers": {
                "price": "99.99",
                "priceCurrency": "EUR"
            }
        }
        </script>
        '''
        hints = extract_structured_hints(html)
        assert hints.get("schema_currency") == "EUR"

    def test_extracts_jsonld_name(self) -> None:
        """Should extract name from JSON-LD Product."""
        html = '''
        <script type="application/ld+json">
        {"@type": "Product", "name": "Schema Product Name"}
        </script>
        '''
        hints = extract_structured_hints(html)
        assert hints.get("schema_name") == "Schema Product Name"

    def test_extracts_jsonld_image(self) -> None:
        """JSON-LD image is not currently extracted (only name, description, price, currency)."""
        # The current implementation doesn't extract image from JSON-LD
        # This test documents the current behavior
        html = '''
        <script type="application/ld+json">
        {"@type": "Product", "name": "Image Product", "image": "https://example.com/product.jpg"}
        </script>
        '''
        hints = extract_structured_hints(html)
        assert hints.get("schema_name") == "Image Product"
        # schema_image is not extracted by current implementation
        assert "schema_image" not in hints

    def test_handles_malformed_jsonld(self) -> None:
        """Malformed JSON-LD should be gracefully ignored."""
        html = '''
        <script type="application/ld+json">
        {not valid json: missing quotes}
        </script>
        <meta property="og:title" content="Fallback Title">
        '''
        hints = extract_structured_hints(html)
        # Should not raise, and should still extract OG tags
        assert hints.get("og_title") == "Fallback Title"
        assert "schema_name" not in hints

    def test_handles_multiple_jsonld(self) -> None:
        """Should extract from multiple JSON-LD blocks.

        Note: Current implementation keeps first name (via `or` logic) but
        overwrites price with each product found. This test documents actual behavior.
        """
        html = '''
        <script type="application/ld+json">
        {"@type": "Organization", "name": "Org Name"}
        </script>
        <script type="application/ld+json">
        {"@type": "Product", "name": "First Product", "offers": {"price": "10"}}
        </script>
        <script type="application/ld+json">
        {"@type": "Product", "name": "Second Product", "offers": {"price": "20"}}
        </script>
        '''
        hints = extract_structured_hints(html)
        # Name keeps first value (via `or` logic)
        assert hints.get("schema_name") == "First Product"
        # Price gets overwritten by last product (direct assignment)
        assert hints.get("schema_price") == "20"

    def test_handles_jsonld_graph(self) -> None:
        """Should handle JSON-LD with @graph wrapper."""
        html = '''
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "Organization", "name": "Org"},
                {"@type": "Product", "name": "Graph Product", "offers": {"price": "55"}}
            ]
        }
        </script>
        '''
        hints = extract_structured_hints(html)
        assert hints.get("schema_name") == "Graph Product"
        assert hints.get("schema_price") == "55"

    def test_handles_jsonld_array(self) -> None:
        """Should handle JSON-LD as array."""
        html = '''
        <script type="application/ld+json">
        [
            {"@type": "BreadcrumbList", "name": "Breadcrumb"},
            {"@type": "Product", "name": "Array Product"}
        ]
        </script>
        '''
        hints = extract_structured_hints(html)
        assert hints.get("schema_name") == "Array Product"

    def test_handles_jsonld_offers_array(self) -> None:
        """Should extract price from first offer in offers array."""
        html = '''
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "Multi-offer Product",
            "offers": [
                {"price": "15.00", "priceCurrency": "USD"},
                {"price": "20.00", "priceCurrency": "USD"}
            ]
        }
        </script>
        '''
        hints = extract_structured_hints(html)
        assert hints.get("schema_price") == "15.00"
        assert hints.get("schema_currency") == "USD"

    def test_empty_html(self) -> None:
        """Empty HTML should return empty dict."""
        hints = extract_structured_hints("")
        assert hints == {}

    def test_no_structured_data(self) -> None:
        """HTML without structured data should return empty dict."""
        html = "<html><body><p>Just plain content</p></body></html>"
        hints = extract_structured_hints(html)
        assert hints == {}

    def test_extracts_both_og_and_jsonld(self) -> None:
        """Should extract from both OG tags and JSON-LD."""
        html = '''
        <meta property="og:title" content="OG Title">
        <meta property="og:image" content="https://og.com/image.jpg">
        <script type="application/ld+json">
        {"@type": "Product", "name": "Schema Name", "offers": {"price": "100"}}
        </script>
        '''
        hints = extract_structured_hints(html)
        assert hints.get("og_title") == "OG Title"
        assert hints.get("og_image") == "https://og.com/image.jpg"
        assert hints.get("schema_name") == "Schema Name"
        assert hints.get("schema_price") == "100"


# =============================================================================
# format_html_for_llm tests
# =============================================================================


class TestFormatHtmlForLlm:
    """Tests for the format_html_for_llm function."""

    def test_includes_url_header(self) -> None:
        """Formatted output should include URL header."""
        result = format_html_for_llm("<html></html>", "https://example.com/product", "Title")
        assert "URL: https://example.com/product" in result

    def test_includes_title_header(self) -> None:
        """Formatted output should include page title header."""
        result = format_html_for_llm("<html></html>", "https://example.com", "My Product Title")
        assert "Page title: My Product Title" in result

    def test_includes_structured_hints_section(self) -> None:
        """Formatted output should include structured metadata section when hints exist."""
        html = '''
        <meta property="og:title" content="Hint Title">
        <script type="application/ld+json">
        {"@type": "Product", "name": "Product", "offers": {"price": "99", "priceCurrency": "USD"}}
        </script>
        '''
        result = format_html_for_llm(html, "https://example.com", "Title")
        assert "=== Structured metadata ===" in result
        assert "PRICE: 99 USD" in result
        assert "og_title: Hint Title" in result

    def test_includes_og_price_in_hints(self) -> None:
        """OG price should be shown in hints section."""
        html = '''
        <meta property="og:price:amount" content="49.99">
        <meta property="og:price:currency" content="EUR">
        '''
        result = format_html_for_llm(html, "https://example.com", "Title")
        assert "OG_PRICE: 49.99 EUR" in result

    def test_no_hints_section_when_empty(self) -> None:
        """No structured metadata section when no hints found."""
        html = "<html><body>Plain content</body></html>"
        result = format_html_for_llm(html, "https://example.com", "Title")
        assert "=== Structured metadata ===" not in result

    def test_includes_optimized_html(self) -> None:
        """Formatted output should include cleaned HTML content."""
        html = "<html><body><div>Product content</div></body></html>"
        result = format_html_for_llm(html, "https://example.com", "Title")
        assert "Page HTML:" in result
        assert "Product content" in result

    def test_optimized_html_removes_scripts(self) -> None:
        """HTML in output should have scripts removed."""
        html = "<script>alert('bad')</script><p>Good content</p>"
        result = format_html_for_llm(html, "https://example.com", "Title")
        assert "alert" not in result
        assert "Good content" in result

    def test_respects_max_chars(self) -> None:
        """HTML should be truncated according to max_chars."""
        html = "<p>" + "x" * 1000 + "</p>"
        result = format_html_for_llm(html, "https://example.com", "Title", max_chars=100)
        assert "[truncated]" in result

    def test_full_format_integration(self) -> None:
        """Full integration test with all components."""
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Awesome Product</title>
            <meta property="og:title" content="OG Product Name">
            <meta property="og:description" content="Product description">
            <meta property="og:image" content="https://cdn.example.com/product.jpg">
            <meta property="og:price:amount" content="199.99">
            <meta property="og:price:currency" content="USD">
            <script type="application/ld+json">
            {
                "@type": "Product",
                "name": "Schema Product Name",
                "description": "Detailed product description",
                "offers": {
                    "price": "199.99",
                    "priceCurrency": "USD"
                }
            }
            </script>
            <style>.price { color: green; }</style>
            <script>console.log('analytics');</script>
        </head>
        <body>
            <!-- Navigation -->
            <nav>Menu</nav>
            <main>
                <h1>Awesome Product</h1>
                <p class="price">$199.99</p>
                <p>This is the product description visible on the page.</p>
                <svg><circle/></svg>
                <noscript>Enable JS</noscript>
            </main>
        </body>
        </html>
        '''
        result = format_html_for_llm(
            html,
            "https://shop.example.com/products/awesome-product",
            "Awesome Product - Shop Example",
        )

        # Check URL and title headers
        assert "URL: https://shop.example.com/products/awesome-product" in result
        assert "Page title: Awesome Product - Shop Example" in result

        # Check structured metadata section
        assert "=== Structured metadata ===" in result
        assert "PRICE: 199.99 USD" in result
        assert "OG_PRICE: 199.99 USD" in result
        assert "og_title: OG Product Name" in result
        assert "og_description: Product description" in result
        assert "og_image: https://cdn.example.com/product.jpg" in result
        assert "schema_name: Schema Product Name" in result

        # Check HTML section
        assert "Page HTML:" in result

        # Check content preserved
        assert "Awesome Product" in result
        assert "$199.99" in result
        assert "product description visible" in result

        # Check removed elements
        assert "console.log" not in result
        assert "color: green" not in result
        assert "<svg" not in result
        assert "Enable JS" not in result
        assert "<!-- Navigation -->" not in result
        assert "<!--" not in result

    def test_empty_html_still_formats(self) -> None:
        """Empty HTML should still produce formatted output with headers."""
        result = format_html_for_llm("", "https://example.com", "Empty Page")
        assert "URL: https://example.com" in result
        assert "Page title: Empty Page" in result
        assert "Page HTML:" in result


# =============================================================================
# Edge cases and regression tests
# =============================================================================


class TestEdgeCases:
    """Edge cases and regression tests."""

    def test_unicode_content_preserved(self) -> None:
        """Unicode characters should be preserved."""
        html = "<p>Price: 1500 rubles</p>"
        result = optimize_html(html)
        assert "rubles" in result

    def test_cyrillic_content_preserved(self) -> None:
        """Cyrillic text should be preserved."""
        html = "<p>Цена: 1500 руб.</p>"
        result = optimize_html(html)
        assert "Цена" in result
        assert "руб" in result

    def test_special_chars_in_og_content(self) -> None:
        """Special characters in OG content should be extracted."""
        html = '<meta property="og:title" content="Product - Best Price! (50% off)">'
        hints = extract_structured_hints(html)
        assert hints.get("og_title") == "Product - Best Price! (50% off)"

    def test_numeric_price_in_jsonld(self) -> None:
        """Numeric price in JSON-LD should be converted to string."""
        html = '''
        <script type="application/ld+json">
        {"@type": "Product", "name": "Numeric Price", "offers": {"price": 99.99}}
        </script>
        '''
        hints = extract_structured_hints(html)
        assert hints.get("schema_price") == "99.99"

    def test_nested_script_tags_in_content(self) -> None:
        """Text mentioning 'script' should not be removed."""
        html = "<p>The script of the movie was amazing</p>"
        result = optimize_html(html)
        assert "script of the movie" in result

    def test_self_closing_svg(self) -> None:
        """Self-closing SVG tags should be handled."""
        html = '<svg/><p>content</p>'
        result = optimize_html(html)
        # Note: current regex may not handle self-closing perfectly,
        # but content should be preserved
        assert "content" in result

    def test_deeply_nested_html(self) -> None:
        """Deeply nested HTML should be processed."""
        html = "<div>" * 50 + "<p>deep content</p>" + "</div>" * 50
        result = optimize_html(html)
        assert "deep content" in result
