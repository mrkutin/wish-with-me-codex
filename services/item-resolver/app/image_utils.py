from __future__ import annotations

import io

from PIL import Image, ImageChops, ImageFilter


def _bbox_from_edge_projection(image: Image.Image) -> tuple[int, int, int, int] | None:
    width, height = image.size
    max_dim = 300
    scale = min(1.0, max_dim / max(width, height))
    if scale < 1.0:
        small = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.BILINEAR)
    else:
        small = image

    gray = small.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    pixels = edges.load()
    sw, sh = edges.size
    edge_threshold = 40

    row_counts = [0] * sh
    col_counts = [0] * sw
    for y in range(sh):
        for x in range(sw):
            if pixels[x, y] > edge_threshold:
                row_counts[y] += 1
                col_counts[x] += 1

    row_thresh = max(2, int(sw * 0.02))
    col_thresh = max(2, int(sh * 0.02))
    rows = [i for i, count in enumerate(row_counts) if count >= row_thresh]
    cols = [i for i, count in enumerate(col_counts) if count >= col_thresh]
    if not rows or not cols:
        return None

    x0, x1 = cols[0], cols[-1] + 1
    y0, y1 = rows[0], rows[-1] + 1

    pad = 0
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(sw, x1 + pad)
    y1 = min(sh, y1 + pad)

    if scale < 1.0:
        x0 = int(x0 / scale)
        y0 = int(y0 / scale)
        x1 = int(x1 / scale)
        y1 = int(y1 / scale)

    return (x0, y0, x1, y1)


def _bbox_from_largest_component(image: Image.Image) -> tuple[int, int, int, int] | None:
    width, height = image.size
    max_dim = 220
    scale = min(1.0, max_dim / max(width, height))
    if scale < 1.0:
        small = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.BILINEAR)
    else:
        small = image

    sw, sh = small.size
    pixels = small.load()
    bg = pixels[0, 0]
    threshold = 30

    mask = [bytearray(sw) for _ in range(sh)]
    for y in range(sh):
        row = mask[y]
        for x in range(sw):
            r, g, b = pixels[x, y]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > threshold:
                row[x] = 1

    visited = [bytearray(sw) for _ in range(sh)]
    best_area = 0
    best_bbox = None
    min_keep = max(10, int(sw * sh * 0.002))

    for y in range(sh):
        row = mask[y]
        for x in range(sw):
            if row[x] == 0 or visited[y][x]:
                continue
            stack = [(x, y)]
            visited[y][x] = 1
            min_x = max_x = x
            min_y = max_y = y
            area = 0
            while stack:
                cx, cy = stack.pop()
                area += 1
                if cx < min_x:
                    min_x = cx
                if cx > max_x:
                    max_x = cx
                if cy < min_y:
                    min_y = cy
                if cy > max_y:
                    max_y = cy
                nx = cx - 1
                if nx >= 0 and mask[cy][nx] and not visited[cy][nx]:
                    visited[cy][nx] = 1
                    stack.append((nx, cy))
                nx = cx + 1
                if nx < sw and mask[cy][nx] and not visited[cy][nx]:
                    visited[cy][nx] = 1
                    stack.append((nx, cy))
                ny = cy - 1
                if ny >= 0 and mask[ny][cx] and not visited[ny][cx]:
                    visited[ny][cx] = 1
                    stack.append((cx, ny))
                ny = cy + 1
                if ny < sh and mask[ny][cx] and not visited[ny][cx]:
                    visited[ny][cx] = 1
                    stack.append((cx, ny))

            if area >= min_keep and area > best_area:
                best_area = area
                best_bbox = (min_x, min_y, max_x + 1, max_y + 1)

    if best_bbox is None:
        return None

    x0, y0, x1, y1 = best_bbox
    pad = 0
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(sw, x1 + pad)
    y1 = min(sh, y1 + pad)

    if scale < 1.0:
        x0 = int(x0 / scale)
        y0 = int(y0 / scale)
        x1 = int(x1 / scale)
        y1 = int(y1 / scale)

    return (x0, y0, x1, y1)


def crop_screenshot_to_content(data: bytes) -> bytes:
    image = Image.open(io.BytesIO(data))
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        alpha = image.convert("RGBA")
        background = Image.new("RGBA", alpha.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, alpha).convert("RGB")
    else:
        image = image.convert("RGB")
    bbox = _bbox_from_edge_projection(image)
    if bbox is None:
        bbox = _bbox_from_largest_component(image)
    if bbox is None:
        background = Image.new(image.mode, image.size, image.getpixel((0, 0)))
        diff = ImageChops.difference(image, background)
        bbox = diff.getbbox()
    if bbox:
        image = image.crop(bbox)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=75)
    return out.getvalue()


def image_data_url(image_base64: str | None, image_mime: str | None) -> str | None:
    if not image_base64 or not image_mime:
        return None
    return f"data:{image_mime};base64,{image_base64}"
