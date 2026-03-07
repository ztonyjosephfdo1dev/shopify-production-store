"""
⚠️  DEPRECATED — No longer used in the v2 pipeline.
Detail crop replaced by the 3×2 collage grid (single Replicate call).

Kept for reference only. Safe to delete.
---
Image Utility Service (v1 — DEPRECATED)
Handles local image processing (no external API needed).
- Detail/close-up crop from raw photo
"""

import io
from PIL import Image


def create_detail_crop(image_bytes: bytes, crop_ratio: float = 0.4) -> bytes | None:
    """
    Create a detail/close-up crop from the center of the image.
    Crops the center portion to show fabric/pattern detail.

    Args:
        image_bytes: raw image bytes
        crop_ratio: portion of the image to crop (0.4 = center 40%)

    Returns:
        bytes of the cropped image, or None on failure
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size

        # Calculate center crop box
        crop_w = int(width * crop_ratio)
        crop_h = int(height * crop_ratio)
        left = (width - crop_w) // 2
        top = (height - crop_h) // 2
        right = left + crop_w
        bottom = top + crop_h

        # Crop and resize to a reasonable product image size
        cropped = img.crop((left, top, right, bottom))

        # Resize to 1024x1024 for consistency
        cropped = cropped.resize((1024, 1024), Image.LANCZOS)

        # Convert to RGB if needed (handles RGBA/palette images)
        if cropped.mode != "RGB":
            cropped = cropped.convert("RGB")

        # Save to bytes
        output = io.BytesIO()
        cropped.save(output, format="JPEG", quality=90)
        return output.getvalue()

    except Exception as e:
        print(f"Detail crop error: {e}")
        return None
