"""
⚠️  DEPRECATED — No longer used in the v2 pipeline.
Photoroom has been removed to cut costs.
Background is now handled by the Replicate VTON model via smart prompts.

Kept for reference only. Safe to delete.
---
Photoroom API Service (v1 — DEPRECATED)
- remove_background: removes BG and places product on white
- create_styled_background: removes BG and adds an AI-generated complementary background
"""

import os
import httpx

PHOTOROOM_API_URL = "https://sdk.photoroom.com/v1/segment"
PHOTOROOM_BG_URL = "https://sdk.photoroom.com/v1/render"


def remove_background(image_bytes: bytes) -> bytes | None:
    """
    Remove background from product image, place on pure white background.

    Args:
        image_bytes: raw image bytes

    Returns:
        bytes of the processed image with white background, or None on failure
    """
    api_key = os.environ.get("PHOTOROOM_API_KEY")
    if not api_key:
        print("PHOTOROOM_API_KEY not set — skipping BG removal")
        return None

    try:
        response = httpx.post(
            PHOTOROOM_API_URL,
            headers={"x-api-key": api_key},
            files={"image_file": ("product.jpg", image_bytes, "image/jpeg")},
            data={
                "format": "jpg",
                "bg_color": "#FFFFFF",
                "size": "auto",
                "channel": "product",
            },
            timeout=60.0,
        )
        response.raise_for_status()
        return response.content

    except Exception as e:
        print(f"Photoroom BG removal error: {e}")
        return None


def create_styled_background(image_bytes: bytes) -> bytes | None:
    """
    Remove background and add a styled AI-generated background.
    Uses Photoroom's AI Background feature.

    Args:
        image_bytes: raw image bytes

    Returns:
        bytes of the processed image with styled background, or None on failure
    """
    api_key = os.environ.get("PHOTOROOM_API_KEY")
    if not api_key:
        print("PHOTOROOM_API_KEY not set — skipping styled background")
        return None

    try:
        # First remove background
        segment_response = httpx.post(
            PHOTOROOM_API_URL,
            headers={"x-api-key": api_key},
            files={"image_file": ("product.jpg", image_bytes, "image/jpeg")},
            data={
                "format": "png",
                "size": "auto",
                "channel": "product",
            },
            timeout=60.0,
        )
        segment_response.raise_for_status()
        transparent_bytes = segment_response.content

        # Then render with AI background
        render_response = httpx.post(
            PHOTOROOM_BG_URL,
            headers={"x-api-key": api_key},
            files={"image_file": ("product.png", transparent_bytes, "image/png")},
            data={
                "template_id": "ai_background",
                "prompt": "minimalist soft pastel studio background, fashion product photography, elegant lighting",
                "format": "jpg",
                "size": "auto",
            },
            timeout=60.0,
        )
        render_response.raise_for_status()
        return render_response.content

    except Exception as e:
        print(f"Photoroom styled background error: {e}")
        # Fallback: try just the white background version
        return remove_background(image_bytes)
