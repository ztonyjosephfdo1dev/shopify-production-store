"""
Image Utility Service (v4)
Local image processing helpers — no external API calls.

Functions:
  crop_grid_2x2()     — Split a 2×2 grid into 4 images
  crop_grid_3x2()     — Split a 3×2 grid into 6 images (future use)
  resize_for_shopify() — Resize to Shopify-optimal dimensions
"""

import io
from PIL import Image


def crop_grid_2x2(grid_image_bytes: bytes) -> list[bytes]:
    """
    Split a 2×2 grid image into 4 individual square images.

    Layout:
      [ TL ] [ TR ]
      [ BL ] [ BR ]

    Args:
        grid_image_bytes: bytes of the 2×2 grid image

    Returns:
        list of 4 JPEG image bytes, one per quadrant
    """
    try:
        img = Image.open(io.BytesIO(grid_image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        mid_x = w // 2
        mid_y = h // 2

        boxes = [
            (0, 0, mid_x, mid_y),          # Top-left
            (mid_x, 0, w, mid_y),           # Top-right
            (0, mid_y, mid_x, h),           # Bottom-left
            (mid_x, mid_y, w, h),           # Bottom-right
        ]

        results = []
        for i, box in enumerate(boxes):
            crop = img.crop(box)
            buf = io.BytesIO()
            crop.save(buf, format="JPEG", quality=92)
            results.append(buf.getvalue())
            print(f"[crop_2x2] Panel {i+1}: {crop.size[0]}×{crop.size[1]}px")

        return results

    except Exception as e:
        print(f"[crop_2x2] Error: {e}")
        return []


def crop_grid_3x2(grid_image_bytes: bytes) -> list[bytes]:
    """
    Split a 3×2 grid image into 6 individual images.

    Layout:
      [ 1 ] [ 2 ]
      [ 3 ] [ 4 ]
      [ 5 ] [ 6 ]

    Args:
        grid_image_bytes: bytes of the 3×2 grid image

    Returns:
        list of 6 JPEG image bytes
    """
    try:
        img = Image.open(io.BytesIO(grid_image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        col_w = w // 2
        row_h = h // 3

        results = []
        for row in range(3):
            for col in range(2):
                box = (
                    col * col_w,
                    row * row_h,
                    (col + 1) * col_w,
                    (row + 1) * row_h,
                )
                crop = img.crop(box)
                buf = io.BytesIO()
                crop.save(buf, format="JPEG", quality=92)
                results.append(buf.getvalue())
                idx = row * 2 + col + 1
                print(f"[crop_3x2] Panel {idx}: {crop.size[0]}×{crop.size[1]}px")

        return results

    except Exception as e:
        print(f"[crop_3x2] Error: {e}")
        return []


def resize_for_shopify(image_bytes: bytes, max_dim: int = 2048) -> bytes:
    """
    Resize image to fit within max_dim while maintaining aspect ratio.
    Shopify recommends 2048×2048 max for product images.

    Args:
        image_bytes: raw image bytes
        max_dim: maximum width or height

    Returns:
        resized JPEG image bytes
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        if w <= max_dim and h <= max_dim:
            return image_bytes  # Already within limits

        # Scale down preserving aspect ratio
        ratio = min(max_dim / w, max_dim / h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)

        resized = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=90)
        print(f"[resize] {w}×{h} → {new_w}×{new_h}")
        return buf.getvalue()

    except Exception as e:
        print(f"[resize] Error: {e}")
        return image_bytes
