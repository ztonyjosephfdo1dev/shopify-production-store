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


def crop_grid_to_halves(grid_image_bytes: bytes) -> list[bytes]:
    """
    Split a 2×2 grid into 2 horizontal halves (top row + bottom row).

    Layout:
      Top half:    [ Pose 1 ] [ Pose 2 ]
      Bottom half: [ Pose 3 ] [ Pose 4 ]

    Args:
        grid_image_bytes: bytes of the 2×2 grid image

    Returns:
        list of 2 JPEG image bytes — [top_half, bottom_half]
    """
    try:
        img = Image.open(io.BytesIO(grid_image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        mid_y = h // 2

        halves = [
            img.crop((0, 0, w, mid_y)),     # Top row
            img.crop((0, mid_y, w, h)),      # Bottom row
        ]

        results = []
        for i, half in enumerate(halves):
            buf = io.BytesIO()
            half.save(buf, format="JPEG", quality=95)
            results.append(buf.getvalue())
            print(f"[crop_halves] Half {i+1}: {half.size[0]}×{half.size[1]}px")

        return results

    except Exception as e:
        print(f"[crop_halves] Error: {e}")
        return []


def crop_half_to_two(half_image_bytes: bytes) -> list[bytes]:
    """
    Split a horizontal half (2 side-by-side poses) into 2 individual images.

    Layout:
      [ Left Pose ] [ Right Pose ]

    Args:
        half_image_bytes: bytes of one half (containing 2 poses side by side)

    Returns:
        list of 2 JPEG image bytes — [left_pose, right_pose]
    """
    try:
        img = Image.open(io.BytesIO(half_image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        mid_x = w // 2

        poses = [
            img.crop((0, 0, mid_x, h)),     # Left pose
            img.crop((mid_x, 0, w, h)),      # Right pose
        ]

        results = []
        for i, pose in enumerate(poses):
            buf = io.BytesIO()
            pose.save(buf, format="JPEG", quality=92)
            results.append(buf.getvalue())
            print(f"[crop_half] Pose {i+1}: {pose.size[0]}×{pose.size[1]}px")

        return results

    except Exception as e:
        print(f"[crop_half] Error: {e}")
        return []


def crop_grid_2x2(grid_image_bytes: bytes) -> list[bytes]:
    """
    Convenience: Split a 2×2 grid into 4 individual images directly.
    Uses crop_grid_to_halves() + crop_half_to_two() internally.

    Returns:
        list of 4 JPEG image bytes
    """
    halves = crop_grid_to_halves(grid_image_bytes)
    if not halves:
        return []
    results = []
    for half in halves:
        poses = crop_half_to_two(half)
        results.extend(poses)
    return results


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
