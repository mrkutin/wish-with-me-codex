from __future__ import annotations

from app.html_parser import extract_images_from_html, format_images_for_llm


class TestExtractImagesFromHtml:
    def test_extracts_basic_image(self) -> None:
        html = '<html><body><img src="/image.jpg" alt="Product"></body></html>'
        images = extract_images_from_html(html, base_url="https://example.com")

        assert len(images) == 1
        assert images[0]["src"] == "https://example.com/image.jpg"
        assert images[0]["alt"] == "Product"

    def test_resolves_relative_urls(self) -> None:
        html = '<img src="/path/image.jpg"><img src="relative.jpg">'
        images = extract_images_from_html(html, base_url="https://example.com/page/")

        assert len(images) == 2
        assert images[0]["src"] == "https://example.com/path/image.jpg"
        assert images[1]["src"] == "https://example.com/page/relative.jpg"

    def test_preserves_absolute_urls(self) -> None:
        html = '<img src="https://cdn.example.com/image.jpg">'
        images = extract_images_from_html(html, base_url="https://example.com")

        assert len(images) == 1
        assert images[0]["src"] == "https://cdn.example.com/image.jpg"

    def test_filters_tiny_images(self) -> None:
        html = '<img src="icon.png" width="20" height="20"><img src="product.jpg" width="500" height="500">'
        images = extract_images_from_html(html)

        assert len(images) == 1
        assert "product.jpg" in images[0]["src"]

    def test_filters_icons_by_pattern(self) -> None:
        html = """
        <img src="logo.png">
        <img src="badge.gif">
        <img src="product.jpg">
        <img src="tracking-pixel.gif">
        """
        images = extract_images_from_html(html)

        assert len(images) == 1
        assert "product.jpg" in images[0]["src"]

    def test_filters_by_class_name(self) -> None:
        html = '<img src="a.jpg" class="icon"><img src="b.jpg" class="product-image">'
        images = extract_images_from_html(html)

        assert len(images) == 1
        assert "b.jpg" in images[0]["src"]

    def test_extracts_image_attributes(self) -> None:
        html = '<img src="test.jpg" alt="Test" title="Title" class="product" width="300" height="400">'
        images = extract_images_from_html(html)

        assert len(images) == 1
        img = images[0]
        assert img["alt"] == "Test"
        assert img["title"] == "Title"
        assert img["class"] == "product"
        assert img["width"] == "300"
        assert img["height"] == "400"

    def test_extracts_data_attributes(self) -> None:
        html = '<img src="test.jpg" data-full="full.jpg" data-thumb="thumb.jpg">'
        images = extract_images_from_html(html)

        assert len(images) == 1
        assert "data" in images[0]
        assert images[0]["data"]["data-full"] == "full.jpg"
        assert images[0]["data"]["data-thumb"] == "thumb.jpg"

    def test_handles_missing_src(self) -> None:
        html = '<img alt="No source">'
        images = extract_images_from_html(html)

        assert len(images) == 0

    def test_handles_malformed_html(self) -> None:
        html = "<img src='test.jpg' <broken>"
        images = extract_images_from_html(html)

        # Should not crash, may or may not extract depending on parser
        assert isinstance(images, list)

    def test_filters_data_uris(self) -> None:
        html = '<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="><img src="product.jpg">'
        images = extract_images_from_html(html, base_url="https://example.com")

        # Data URI should be filtered out
        assert len(images) == 1
        assert "product.jpg" in images[0]["src"]

    def test_filters_single_dimension_tiny_images(self) -> None:
        html = '<img src="icon1.png" width="10"><img src="icon2.png" height="20"><img src="product.jpg" width="500">'
        images = extract_images_from_html(html)

        # Icons with only one tiny dimension should be filtered
        assert len(images) == 1
        assert "product.jpg" in images[0]["src"]

    def test_pattern_matching_with_word_boundaries(self) -> None:
        # "icon" substring in "silicone" should NOT be filtered
        html = '<img src="silicone-product.jpg" alt="Silicone case"><img src="icon.png" alt="Icon">'
        images = extract_images_from_html(html)

        # Only the actual icon should be filtered, not silicone
        assert len(images) == 1
        assert "silicone" in images[0]["src"].lower()

    def test_skips_malformed_urls(self) -> None:
        # Test with a URL that will fail the netloc check after resolution
        html = '<img src="file:///etc/passwd"><img src="valid.jpg">'
        images = extract_images_from_html(html, base_url="https://example.com")

        # file:// URL should be skipped (no netloc), only valid.jpg remains
        assert len(images) == 1
        assert "valid.jpg" in images[0]["src"]


class TestFormatImagesForLlm:
    def test_formats_single_image(self) -> None:
        images = [{"src": "https://example.com/image.jpg", "alt": "Product"}]
        result = format_images_for_llm(images)

        assert "1. https://example.com/image.jpg" in result
        assert 'alt="Product"' in result

    def test_formats_multiple_images(self) -> None:
        images = [
            {"src": "https://example.com/img1.jpg", "alt": "First"},
            {"src": "https://example.com/img2.jpg", "title": "Second"},
        ]
        result = format_images_for_llm(images)

        assert "1. https://example.com/img1.jpg" in result
        assert "2. https://example.com/img2.jpg" in result
        assert 'alt="First"' in result
        assert 'title="Second"' in result

    def test_limits_number_of_images(self) -> None:
        images = [{"src": f"https://example.com/img{i}.jpg"} for i in range(30)]
        result = format_images_for_llm(images, max_images=5)

        lines = result.strip().split("\n")
        assert len(lines) == 5
        assert "1. https://example.com/img0.jpg" in result
        assert "5. https://example.com/img4.jpg" in result
        assert "https://example.com/img10.jpg" not in result

    def test_handles_empty_list(self) -> None:
        result = format_images_for_llm([])
        assert result == "No images found."

    def test_includes_all_attributes(self) -> None:
        images = [
            {
                "src": "https://example.com/test.jpg",
                "alt": "Alt text",
                "title": "Title text",
                "class": "product-img",
            }
        ]
        result = format_images_for_llm(images)

        assert "https://example.com/test.jpg" in result
        assert 'alt="Alt text"' in result
        assert 'title="Title text"' in result
        assert 'class="product-img"' in result

    def test_omits_missing_attributes(self) -> None:
        images = [{"src": "https://example.com/test.jpg"}]
        result = format_images_for_llm(images)

        assert "https://example.com/test.jpg" in result
        assert "alt=" not in result
        assert "title=" not in result
        assert "class=" not in result

    def test_escapes_html_entities(self) -> None:
        images = [
            {
                "src": "https://example.com/test.jpg",
                "alt": 'Test <script>alert("xss")</script>',
                "title": "Title & special chars",
                "class": 'product-img" onclick="evil()',
            }
        ]
        result = format_images_for_llm(images)

        # HTML entities should be escaped
        assert "&lt;script&gt;" in result
        assert "alert(&quot;xss&quot;)" in result
        assert "&amp;" in result
        assert "<script>" not in result
        assert 'onclick="evil()' not in result
