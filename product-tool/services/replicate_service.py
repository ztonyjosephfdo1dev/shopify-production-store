"""
Replicate Service — Virtual Try-On + Collage Grid
Cost-optimized: Only 2 API calls total.

  virtual_tryon_hero()        → 1 call → Hero front shot with smart background
  virtual_tryon_collage_grid() → 1 call → 3×2 grid (6 poses/styles in ONE image)

Background & poses auto-selected based on dress_style:
  traditional → warm/festive bg, ethnic poses
  western     → minimal/urban bg, casual poses
  fusion      → modern/artistic bg, mixed poses
  formal      → elegant/clean bg, professional poses
"""

import os
import random
import base64
import httpx
import replicate


# ---------------------------------------------------------------------------
# Indian model reference images (hosted on Cloud Storage)
# Replace with your actual URLs
# ---------------------------------------------------------------------------
MODEL_IMAGES = {
    "default": os.environ.get(
        "VTON_MODEL_IMAGE_URL",
        "https://storage.googleapis.com/pookie-style-uploads/models/indian-model-1.jpg",
    ),
}

# ---------------------------------------------------------------------------
# POSE PRESETS — Randomly selected based on dress style
# 4 poses + 2 styling variations = 6 panels per collage
# ---------------------------------------------------------------------------
POSE_PRESETS = {
    "traditional": {
        "poses": [
            "standing gracefully with hands folded at waist, slight head tilt",
            "walking pose with dupatta flowing, looking over shoulder",
            "sitting elegantly on a low stool, saree/dupatta draped beautifully",
            "three-quarter turn showing back detail and embroidery",
            "twirling pose showing full flare of the outfit",
            "candid laughing pose with hands adjusting dupatta",
        ],
        "styles": [
            "paired with gold jhumka earrings and bangles",
            "styled with a contrasting dupatta and mojari shoes",
            "accessorized with a maang tikka and statement ring",
            "layered with an embroidered jacket over the outfit",
        ],
    },
    "western": {
        "poses": [
            "confident walking pose on street, one hand in pocket",
            "leaning against a wall casually, arms crossed",
            "sitting on a high stool with legs crossed, relaxed vibe",
            "looking over shoulder showing back design",
            "full front pose with hand on hip, smiling",
            "candid mid-step walking, hair flowing",
        ],
        "styles": [
            "paired with white sneakers and a crossbody bag",
            "styled with heels and hoop earrings for a night-out look",
            "accessorized with sunglasses and a denim jacket",
            "layered with a leather belt and ankle boots",
        ],
    },
    "fusion": {
        "poses": [
            "standing with one hand on hip, modern confident pose",
            "side profile showing the fusion silhouette",
            "sitting cross-legged on floor, bohemian vibe",
            "walking pose showing the contemporary drape/cut",
            "arms stretched out showing sleeve and fit detail",
            "back pose showing unique back design or pattern",
        ],
        "styles": [
            "paired with kolhapuri chappals and oxidized jewelry",
            "styled with block heels and a clutch bag",
            "accessorized with layered necklaces and a potli bag",
            "layered with a modern shrug over the outfit",
        ],
    },
    "formal": {
        "poses": [
            "standing straight, professional and poised, hands clasped",
            "walking confidently with a structured handbag",
            "seated at a desk or chair, polished corporate look",
            "three-quarter angle showing tailored fit and structure",
            "adjusting blazer/collar, power pose",
            "full-length front view, one foot slightly forward",
        ],
        "styles": [
            "paired with pointed-toe pumps and a watch",
            "styled with pearl studs and a structured tote bag",
            "accessorized with a thin belt and minimal gold jewelry",
            "layered with a matching blazer for boardroom look",
        ],
    },
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


def _get_background(dress_style: str) -> str:
    """Pick a random background prompt based on dress style."""
    backgrounds = BACKGROUND_PRESETS.get(dress_style, BACKGROUND_PRESETS["western"])
    return random.choice(backgrounds)


def _get_poses_and_styles(dress_style: str) -> list[str]:
    """
    Pick 4 random poses + 2 random styling variations = 6 panel descriptions.
    Returns list of 6 strings for the collage grid.
    """
    preset = POSE_PRESETS.get(dress_style, POSE_PRESETS["western"])
    poses = random.sample(preset["poses"], min(4, len(preset["poses"])))
    styles = random.sample(preset["styles"], min(2, len(preset["styles"])))
    return poses + styles


def _download_image(url: str) -> bytes:
    """Download image from URL and return bytes."""
    response = httpx.get(url, timeout=120.0, follow_redirects=True)
    response.raise_for_status()
    return response.content


def _run_replicate(garment_bytes: bytes, prompt: str) -> bytes | None:
    """
    Run a single Replicate VTON/generation call.
    Tries primary model first, falls back to secondary.

    Returns image bytes or None on failure.
    """
    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        print("REPLICATE_API_TOKEN not set — skipping")
        return None

    garment_b64 = base64.b64encode(garment_bytes).decode("utf-8")
    garment_uri = f"data:image/jpeg;base64,{garment_b64}"
    model_image_url = MODEL_IMAGES["default"]

    # --- Primary: prunaai/p-tryon (~$0.01/run) ---
    try:
        output = replicate.run(
            "prunaai/p-tryon:4e0e517e6b5eb42a8cbfbaed51ac2b8c01c24488a006dc5d8e0fc8e70f95e68b",
            input={
                "model_image": model_image_url,
                "garment_image": garment_uri,
                "category": "upper_body",
                "num_inference_steps": 30,
                "style_prompt": prompt,
            },
        )
    except Exception as e:
        print(f"p-tryon failed ({e}), trying fallback...")
        # --- Fallback: omnious/vella-1.5 ---
        try:
            output = replicate.run(
                "omnious/vella-1.5",
                input={
                    "model_image": model_image_url,
                    "garment_image": garment_uri,
                    "category": "tops",
                    "prompt": prompt,
                },
            )
        except Exception as e2:
            print(f"Fallback VTON also failed: {e2}")
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


def virtual_tryon_hero(
    garment_bytes: bytes,
    dress_style: str = "western",
    extra_prompt: str = "",
) -> bytes | None:
    """
    Image 1 — Hero front-facing shot with smart background.
    Single Replicate call.

    Args:
        garment_bytes: raw garment image bytes
        dress_style: "traditional" | "western" | "fusion" | "formal"
        extra_prompt: user's custom styling instruction (appended to prompt)

    Returns:
        bytes of the hero image, or None on failure
    """
    background = _get_background(dress_style)

    prompt_parts = [
        "Full-length front-facing fashion product photo",
        "young Indian woman model wearing this exact garment",
        f"Background: {background}",
        "high resolution, sharp focus, professional fashion photography",
        "full body visible head to toe, centered in frame",
    ]

    if extra_prompt:
        prompt_parts.append(f"Additional styling: {extra_prompt}")

    prompt = ". ".join(prompt_parts)
    print(f"[Hero] dress_style={dress_style}, prompt_length={len(prompt)}")

    return _run_replicate(garment_bytes, prompt)


def virtual_tryon_collage_grid(
    garment_bytes: bytes,
    dress_style: str = "western",
    extra_prompt: str = "",
) -> bytes | None:
    """
    Image 2 — 3×2 collage grid with 6 poses/styles in ONE single API call.
    The model is prompted to generate all 6 views arranged as a grid.

    Layout (mobile-friendly 3 rows × 2 columns):
      [ Pose 1 ] [ Pose 2 ]
      [ Pose 3 ] [ Pose 4 ]
      [ Style 1] [ Style 2]

    Args:
        garment_bytes: raw garment image bytes
        dress_style: "traditional" | "western" | "fusion" | "formal"
        extra_prompt: user's custom styling instruction (appended to prompt)

    Returns:
        bytes of the collage grid image, or None on failure
    """
    background = _get_background(dress_style)
    panels = _get_poses_and_styles(dress_style)

    # Build a detailed prompt asking for a 3×2 grid
    grid_description = "\n".join(
        f"  Panel {i+1}: {desc}" for i, desc in enumerate(panels)
    )

    prompt_parts = [
        "Generate a single image arranged as a 3-row by 2-column grid",
        "showing the same young Indian woman model wearing this exact garment in 6 different views",
        f"Background for all panels: {background}",
        f"The 6 panels are:\n{grid_description}",
        "Each panel should be clearly separated with thin white borders",
        "Professional fashion photography, consistent lighting across all panels",
        "High resolution, sharp details, full body visible in each panel",
        "Mobile-friendly portrait layout (taller than wide)",
    ]

    if extra_prompt:
        prompt_parts.append(f"Additional styling note: {extra_prompt}")

    prompt = ". ".join(prompt_parts)
    print(f"[Collage] dress_style={dress_style}, panels={len(panels)}, prompt_length={len(prompt)}")

    return _run_replicate(garment_bytes, prompt)
