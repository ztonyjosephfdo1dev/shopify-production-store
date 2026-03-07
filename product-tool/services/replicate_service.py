"""
Replicate Service — 4-Pose Grid + Crop + Upscale Pipeline (v4)

Cost-optimized: 1 VTON call + 4 upscale calls = $0.014/product

Pipeline:
  1. generate_4pose_grid()   → 1 call  → 2×2 grid image (4 poses)     $0.01
  2. crop_grid_to_poses()    → local   → 4 individual 512×512 crops    $0.00
  3. upscale_image()         → 4 calls → 4 upscaled 2048×2048 images   $0.004
                                                                  ────────
                                                            Total: $0.014

Background & poses auto-selected based on dress_style:
  traditional → warm/festive bg, ethnic poses
  western     → minimal/urban bg, casual poses
  fusion      → modern/artistic bg, mixed poses
  formal      → elegant/clean bg, professional poses
"""

import os
import io
import random
import base64
import time
import httpx
import replicate
from PIL import Image


# ---------------------------------------------------------------------------
# Indian model reference image
# ---------------------------------------------------------------------------
MODEL_IMAGES = {
    "default": os.environ.get(
        "VTON_MODEL_IMAGE_URL",
        "https://storage.googleapis.com/pookie-style-uploads/models/indian-model-1.jpg",
    ),
}

# ---------------------------------------------------------------------------
# POSE PRESETS — 4 poses per dress style for the 2×2 grid
# ---------------------------------------------------------------------------
POSE_PRESETS = {
    "traditional": [
        "standing gracefully with hands folded at waist, slight head tilt, full front view",
        "walking pose with dupatta flowing, looking over shoulder, three-quarter angle",
        "three-quarter turn showing back detail and embroidery, elegant posture",
        "twirling pose showing full flare of the outfit, joyful expression",
    ],
    "western": [
        "confident walking pose on street, one hand in pocket, full front view",
        "leaning against a wall casually, arms crossed, three-quarter angle",
        "looking over shoulder showing back design, stylish pose",
        "full front pose with hand on hip, smiling confidently",
    ],
    "fusion": [
        "standing with one hand on hip, modern confident pose, full front view",
        "side profile showing the fusion silhouette, elegant posture",
        "walking pose showing the contemporary drape and cut, three-quarter angle",
        "back pose showing unique back design or pattern, looking over shoulder",
    ],
    "formal": [
        "standing straight, professional and poised, hands clasped, full front view",
        "walking confidently with a structured handbag, three-quarter angle",
        "three-quarter angle showing tailored fit and structure, power pose",
        "full-length front view, one foot slightly forward, polished look",
    ],
}

# ---------------------------------------------------------------------------
# BACKGROUND PRESETS — Auto-selected based on dress style
# ---------------------------------------------------------------------------
BACKGROUND_PRESETS = {
    "traditional": [
        "warm golden palace interior with arched doorways and marigold flowers",
        "festive Indian courtyard with hanging diyas and warm sunset light",
        "ornate Rajasthani haveli corridor with jharokha windows, soft warm lighting",
        "temple garden with jasmine vines and terracotta tiles, golden hour",
    ],
    "western": [
        "clean minimalist urban street with soft natural daylight",
        "modern cafe exterior with exposed brick and plants",
        "bright white studio with soft shadow, clean fashion photography look",
        "city sidewalk with blurred bokeh lights, golden hour",
    ],
    "fusion": [
        "contemporary art gallery with abstract paintings on white walls",
        "modern rooftop garden with a mix of plants and city skyline",
        "boutique hotel lobby with modern Indian art and warm lighting",
        "colorful painted wall with geometric patterns, vibrant and trendy",
    ],
    "formal": [
        "elegant office lobby with marble floors and soft daylight",
        "minimalist gray studio backdrop with professional lighting",
        "modern corporate interior with glass walls and warm tones",
        "luxury hotel corridor with neutral tones and clean lines",
    ],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
RETRY_DELAY = 15  # seconds


def _get_background(dress_style: str) -> str:
    """Pick a random background prompt based on dress style."""
    backgrounds = BACKGROUND_PRESETS.get(dress_style, BACKGROUND_PRESETS["western"])
    return random.choice(backgrounds)


def _get_4_poses(dress_style: str) -> list[str]:
    """Get 4 pose descriptions for the 2×2 grid."""
    poses = POSE_PRESETS.get(dress_style, POSE_PRESETS["western"])
    return random.sample(poses, min(4, len(poses)))


def _download_image(url: str) -> bytes:
    """Download image from URL and return bytes."""
    response = httpx.get(url, timeout=120.0, follow_redirects=True)
    response.raise_for_status()
    return response.content


def _try_replicate(model_id: str, input_params: dict, label: str) -> object | None:
    """Try a Replicate model with retry on 429 rate limit."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return replicate.run(model_id, input=input_params)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "throttled" in err_str.lower():
                if attempt < MAX_RETRIES:
                    wait = RETRY_DELAY * attempt
                    print(f"[{label}] 429 rate limit, retry {attempt}/{MAX_RETRIES} after {wait}s...")
                    time.sleep(wait)
                    continue
            print(f"[{label}] Failed (attempt {attempt}): {e}")
            return None
    return None


def _run_vton(garment_bytes: bytes, prompt: str) -> bytes | None:
    """
    Run VTON with primary + fallback model.
    Returns image bytes or None.
    """
    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        print("REPLICATE_API_TOKEN not set — skipping")
        return None

    garment_b64 = base64.b64encode(garment_bytes).decode("utf-8")
    garment_uri = f"data:image/jpeg;base64,{garment_b64}"
    model_image_url = MODEL_IMAGES["default"]

    # Primary: prunaai/p-tryon (latest)
    output = _try_replicate(
        "prunaai/p-tryon",
        {
            "model_image": model_image_url,
            "garment_image": garment_uri,
            "category": "upper_body",
            "num_inference_steps": 30,
            "style_prompt": prompt,
        },
        "p-tryon",
    )

    # Fallback: omnious/vella-1.5
    if output is None:
        print("[VTON] Primary failed, trying fallback omnious/vella-1.5...")
        time.sleep(RETRY_DELAY)
        output = _try_replicate(
            "omnious/vella-1.5",
            {
                "model_image": model_image_url,
                "garment_image": garment_uri,
                "category": "tops",
                "prompt": prompt,
            },
            "vella-1.5",
        )

    if output is None:
        print("[VTON] All models failed.")
        return None

    # Extract URL from output
    if isinstance(output, list):
        result_url = str(output[0])
    elif hasattr(output, "url"):
        result_url = output.url
    else:
        result_url = str(output)

    return _download_image(result_url)


# ===========================================================================
# PUBLIC API — Called from main.py
# ===========================================================================


def generate_4pose_grid(
    garment_bytes: bytes,
    dress_style: str = "western",
    extra_prompt: str = "",
) -> bytes | None:
    """
    Generate a single 2×2 grid image with 4 poses (1 Replicate call).

    The model wears the garment in 4 different poses arranged as:
      [ Pose 1 ] [ Pose 2 ]
      [ Pose 3 ] [ Pose 4 ]

    Args:
        garment_bytes: raw garment image bytes
        dress_style: "traditional" | "western" | "fusion" | "formal"
        extra_prompt: user's custom styling instruction

    Returns:
        bytes of the 2×2 grid image, or None on failure
    """
    background = _get_background(dress_style)
    poses = _get_4_poses(dress_style)

    grid_desc = "\n".join(f"  Panel {i+1}: {p}" for i, p in enumerate(poses))

    prompt_parts = [
        "Generate a single image arranged as a 2-row by 2-column grid (2×2 layout)",
        "showing the same young Indian woman model wearing this exact garment in 4 different poses",
        f"Background for all panels: {background}",
        f"The 4 panels are:\n{grid_desc}",
        "Each panel must be clearly separated with thin white borders",
        "Professional fashion e-commerce photography, consistent lighting across all panels",
        "High resolution, sharp details, full body visible in each panel",
        "Each panel should be square and equal sized",
    ]

    if extra_prompt:
        prompt_parts.append(f"Additional styling note: {extra_prompt}")

    prompt = ". ".join(prompt_parts)
    print(f"[4-Pose Grid] dress_style={dress_style}, prompt_length={len(prompt)}")

    return _run_vton(garment_bytes, prompt)


def crop_grid_to_poses(grid_image_bytes: bytes) -> list[bytes]:
    """
    Crop a 2×2 grid image into 4 individual square images.

    Splits evenly into quadrants:
      [ TL ] [ TR ]
      [ BL ] [ BR ]

    Args:
        grid_image_bytes: bytes of the 2×2 grid image

    Returns:
        list of 4 image bytes (JPEG), one per pose
    """
    try:
        img = Image.open(io.BytesIO(grid_image_bytes))

        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        mid_x = w // 2
        mid_y = h // 2

        # Crop quadrants: top-left, top-right, bottom-left, bottom-right
        crops = [
            img.crop((0, 0, mid_x, mid_y)),          # Pose 1 (top-left)
            img.crop((mid_x, 0, w, mid_y)),           # Pose 2 (top-right)
            img.crop((0, mid_y, mid_x, h)),            # Pose 3 (bottom-left)
            img.crop((mid_x, mid_y, w, h)),            # Pose 4 (bottom-right)
        ]

        results = []
        for i, crop in enumerate(crops):
            buf = io.BytesIO()
            crop.save(buf, format="JPEG", quality=92)
            crop_bytes = buf.getvalue()
            print(f"[Crop] Pose {i+1}: {crop.size[0]}×{crop.size[1]}px, {len(crop_bytes)} bytes")
            results.append(crop_bytes)

        return results

    except Exception as e:
        print(f"[Crop] Error splitting grid: {e}")
        return []


def upscale_image(image_bytes: bytes, label: str = "image") -> bytes | None:
    """
    Upscale a single image 4x using Real-ESRGAN on Replicate.

    Input:  ~512×512px (cropped pose)
    Output: ~2048×2048px (upscaled, sharp)
    Cost:   ~$0.001 per call

    Args:
        image_bytes: raw image bytes to upscale
        label: label for logging

    Returns:
        upscaled image bytes, or original bytes on failure (graceful degradation)
    """
    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        print(f"[Upscale] No API token — returning original for {label}")
        return image_bytes

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{b64}"

    output = _try_replicate(
        "nightmareai/real-esrgan:f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa",
        {
            "image": data_uri,
            "scale": 4,
            "face_enhance": True,
        },
        f"esrgan-{label}",
    )

    if output is None:
        # Graceful degradation: return original instead of failing
        print(f"[Upscale] Failed for {label} — returning original")
        return image_bytes

    # Output is a URL
    if isinstance(output, list):
        result_url = str(output[0])
    elif hasattr(output, "url"):
        result_url = output.url
    else:
        result_url = str(output)

    try:
        upscaled_bytes = _download_image(result_url)
        # Verify upscale worked
        upscaled_img = Image.open(io.BytesIO(upscaled_bytes))
        print(f"[Upscale] {label}: {upscaled_img.size[0]}×{upscaled_img.size[1]}px, {len(upscaled_bytes)} bytes")
        return upscaled_bytes
    except Exception as e:
        print(f"[Upscale] Download/verify failed for {label}: {e}")
        return image_bytes


def generate_and_process_poses(
    garment_bytes: bytes,
    dress_style: str = "western",
    extra_prompt: str = "",
) -> list[dict]:
    """
    Full pipeline: Generate 4-pose grid → Crop → Upscale → Return 4 images.

    This is the main entry point called from main.py.

    Args:
        garment_bytes: raw garment image bytes
        dress_style: "traditional" | "western" | "fusion" | "formal"
        extra_prompt: user's custom styling instruction

    Returns:
        list of dicts with keys: label, bytes, filename
        Empty list if generation fails entirely.
    """
    pose_labels = ["Front View", "Three-Quarter View", "Back Detail", "Dynamic Pose"]

    # ===== Step 1: Generate 2×2 grid (1 Replicate call — $0.01) =====
    print("[Pipeline] Step 1: Generating 4-pose grid...")
    grid_bytes = generate_4pose_grid(garment_bytes, dress_style, extra_prompt)

    if grid_bytes is None:
        print("[Pipeline] Grid generation failed — no images.")
        return []

    # ===== Step 2: Crop into 4 individual poses (local, free) =====
    print("[Pipeline] Step 2: Cropping grid into 4 poses...")
    pose_crops = crop_grid_to_poses(grid_bytes)

    if not pose_crops:
        print("[Pipeline] Cropping failed — returning grid as single image.")
        return [{
            "label": "4-Pose Grid",
            "bytes": grid_bytes,
            "filename": "poses-grid.jpg",
        }]

    # ===== Step 3: Upscale each pose 4x (4 Replicate calls — $0.004) =====
    print(f"[Pipeline] Step 3: Upscaling {len(pose_crops)} poses...")
    results = []

    for i, crop_bytes in enumerate(pose_crops):
        label = pose_labels[i] if i < len(pose_labels) else f"Pose {i+1}"

        upscaled = upscale_image(crop_bytes, label=f"pose-{i+1}")

        results.append({
            "label": label,
            "bytes": upscaled,
            "filename": f"pose-{i+1}-{label.lower().replace(' ', '-')}.jpg",
        })

        # Small delay between upscale calls to avoid rate limits
        if i < len(pose_crops) - 1:
            time.sleep(2)

    print(f"[Pipeline] Complete: {len(results)} images ready.")
    return results
