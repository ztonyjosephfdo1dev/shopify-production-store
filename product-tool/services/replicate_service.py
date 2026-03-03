"""
Replicate VTON (Virtual Try-On) Service
Maps the real garment from a product photo onto an Indian model.
Uses commercial-licensed models from Replicate.
"""

import os
import io
import base64
import httpx
import replicate


# Indian model reference images (hosted on Cloud Storage or a public URL)
# These are placeholder URLs — replace with actual model photos
MODEL_IMAGES = [
    os.environ.get(
        "VTON_MODEL_IMAGE_URL",
        "https://storage.googleapis.com/pookie-style-uploads/models/indian-model-1.jpg",
    )
]


def virtual_tryon(garment_bytes: bytes) -> bytes | None:
    """
    Virtual try-on: map the real garment onto an Indian model.

    Uses Replicate's VTON models (prunaai/p-tryon or similar).
    The garment from the product photo is preserved — only the model body changes.

    Args:
        garment_bytes: raw product image bytes (garment photo)

    Returns:
        bytes of the on-model image, or None on failure
    """
    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        print("REPLICATE_API_TOKEN not set — skipping virtual try-on")
        return None

    try:
        # Convert garment bytes to data URI for Replicate
        garment_b64 = base64.b64encode(garment_bytes).decode("utf-8")
        garment_uri = f"data:image/jpeg;base64,{garment_b64}"

        model_image_url = MODEL_IMAGES[0]

        # Try prunaai/p-tryon first (cheapest: ~$0.01/run)
        try:
            output = replicate.run(
                "prunaai/p-tryon:4e0e517e6b5eb42a8cbfbaed51ac2b8c01c24488a006dc5d8e0fc8e70f95e68b",
                input={
                    "model_image": model_image_url,
                    "garment_image": garment_uri,
                    "category": "upper_body",  # or "lower_body", "full_body"
                    "num_inference_steps": 30,
                },
            )
        except Exception:
            # Fallback to omnious/vella if p-tryon fails
            print("p-tryon failed, trying omnious/vella-1.5...")
            output = replicate.run(
                "omnious/vella-1.5",
                input={
                    "model_image": model_image_url,
                    "garment_image": garment_uri,
                    "category": "tops",
                },
            )

        # Output is typically a URL or list of URLs
        if isinstance(output, list):
            result_url = str(output[0])
        elif hasattr(output, "url"):
            result_url = output.url
        else:
            result_url = str(output)

        # Download the result image
        response = httpx.get(result_url, timeout=60.0)
        response.raise_for_status()
        return response.content

    except Exception as e:
        print(f"Replicate VTON error: {e}")
        return None
