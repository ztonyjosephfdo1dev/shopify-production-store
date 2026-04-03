"""
Replicate Service — 2-Pose VTON Pipeline (v5)

2 real VTON calls per product = 2 different model photos x 2 poses.
Zoom (upper_body / lower_body / dresses) is auto-detected from garment type.

  Pose 1: Front view          (model_1 randomly picked from GCS pool)
  Pose 2: Side + back view    (model_2 randomly picked from GCS pool)

Cost: 2 x ~$0.010 = ~$0.020 per product

LOGGING: All steps prefixed with [REPLICATE] for easy GCP log filtering.
"""

import os
import re
import random
import base64
import time
import httpx
import replicate
from google.cloud import storage as gcs
from services.image_utils import build_smart_collage


# ---------------------------------------------------------------------------
# GCS model image pool
# Add:    gsutil cp <photo.jpg> gs://pookie-style-uploads/models/
# Remove: gsutil rm gs://pookie-style-uploads/models/<filename>
# ---------------------------------------------------------------------------
GCS_BUCKET = "pookie-style-uploads"
GCS_MODELS_PREFIX = "models/"

_UNSPLASH_FALLBACKS = [
    "https://images.unsplash.com/photo-1594744803329-e58b31239f85?w=512&h=768&fit=crop",
    "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=512&h=768&fit=crop",
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=512&h=768&fit=crop",
]

# Cached per Cloud Function instance (refreshes on cold start)
_gcs_model_url_cache: list[str] | None = None


# ---------------------------------------------------------------------------
# Retry config
# ---------------------------------------------------------------------------
MAX_RETRIES = 5
RETRY_DELAY = 12       # base seconds, overridden by retry_after in 429 error
INTER_CALL_DELAY = 12  # seconds between separate Replicate API calls


# ---------------------------------------------------------------------------
# Garment type -> VTON category (controls zoom area in output image)
# top / kurti / shirt  -> upper_body  (waist-up crop)
# bottom / skirt / etc -> lower_body  (hip-down crop)
# dress / gown / saree -> dresses     (full body)
# ---------------------------------------------------------------------------
_GARMENT_CATEGORY_MAP = {
    "top": "upper_body",
    "kurti": "upper_body",
    "shirt": "upper_body",
    "blouse": "upper_body",
    "crop-top": "upper_body",
    "crop top": "upper_body",
    "t-shirt": "upper_body",
    "jacket": "upper_body",
    "sweatshirt": "upper_body",
    "hoodie": "upper_body",
    "bottom": "lower_body",
    "palazzo": "lower_body",
    "skirt": "lower_body",
    "jeans": "lower_body",
    "trousers": "lower_body",
    "pants": "lower_body",
    "shorts": "lower_body",
    "leggings": "lower_body",
    "dress": "dresses",
    "gown": "dresses",
    "saree": "dresses",
    "cord-set": "dresses",
    "coord set": "dresses",
    "coord_set": "dresses",
    "co-ord": "dresses",
    "kurti-set": "dresses",
    "kurti set": "dresses",
    "kurthi-set": "dresses",
    "suits": "dresses",
    "jumpsuit": "dresses",
    "anarkali": "dresses",
    "lehenga": "dresses",
    "sharara": "dresses",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _log(msg: str):
    """Print with [REPLICATE] prefix for easy GCP log filtering."""
    print(f"[REPLICATE] {msg}")


def _get_vton_category(detected_garment_type: str) -> str:
    """Map detected garment type string to VTON category param."""
    if not detected_garment_type:
        return "upper_body"
    key = detected_garment_type.lower().strip()
    if key in _GARMENT_CATEGORY_MAP:
        return _GARMENT_CATEGORY_MAP[key]
    for garment, category in _GARMENT_CATEGORY_MAP.items():
        if garment in key or key in garment:
            return category
    _log(f"[CATEGORY] Unknown garment type '{detected_garment_type}' -> defaulting to upper_body")
    return "upper_body"


def _list_gcs_model_images() -> list[str]:
    """
    List all images in gs://pookie-style-uploads/models/ and return their public URLs.
    Result is cached per Cloud Function instance so GCS is only queried once per cold start.
    """
    global _gcs_model_url_cache
    if _gcs_model_url_cache is not None:
        return _gcs_model_url_cache

    try:
        client = gcs.Client()
        bucket = client.bucket(GCS_BUCKET)
        blobs = list(bucket.list_blobs(prefix=GCS_MODELS_PREFIX))
        urls = []
        for blob in blobs:
            if blob.name == GCS_MODELS_PREFIX:
                continue
            if not blob.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            urls.append(f"https://storage.googleapis.com/{GCS_BUCKET}/{blob.name}")

        _log(f"[MODEL-IMG] GCS pool: {len(urls)} images")
        _gcs_model_url_cache = urls
        return urls

    except Exception as e:
        _log(f"[MODEL-IMG] GCS listing failed: {e} — using Unsplash fallbacks")
        _gcs_model_url_cache = []
        return []


def _pick_model_images(n: int) -> list[str]:
    """
    Pick n random model image URLs from GCS pool.
    Uses random.choices (with replacement) so it works even if pool has < n images.
    Falls back to Unsplash if GCS is empty.
    """
    pool = _list_gcs_model_images() or _UNSPLASH_FALLBACKS
    chosen = random.choices(pool, k=n)
    _log(f"[MODEL-IMG] Selected: {', '.join(url.split('/')[-1] for url in chosen)}")
    return chosen


def _download_image(url: str) -> bytes:
    _log(f"[DOWNLOAD] {url[:80]}...")
    response = httpx.get(url, timeout=120.0, follow_redirects=True)
    response.raise_for_status()
    _log(f"[DOWNLOAD] {len(response.content)} bytes")
    return response.content


def _parse_retry_after(err_str: str) -> int:
    """Extract retry_after seconds from a 429 error string. Adds 3s buffer."""
    match = re.search(r"retry_after[^:]*:\s*(\d+)", err_str)
    if match:
        return int(match.group(1)) + 3
    match = re.search(r"resets in ~(\d+)s", err_str)
    if match:
        return int(match.group(1)) + 3
    return RETRY_DELAY


def _try_replicate(model_id: str, input_params: dict, label: str):
    """Run a Replicate model with retries on rate limit. Returns output or None."""
    _log(f"[API-CALL] {label}: model={model_id.split(':')[0]}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _log(f"[API-CALL] {label}: Attempt {attempt}/{MAX_RETRIES}...")
            output = replicate.run(model_id, input=input_params)
            _log(f"[API-CALL] {label}: SUCCESS")
            return output
        except Exception as e:
            err_str = str(e)

            if "429" in err_str or "throttled" in err_str.lower():
                error_type = "RATE_LIMIT_429_NEED_$5_CREDIT" if "less than $5.0" in err_str else "RATE_LIMIT_429"
            elif "422" in err_str:
                error_type = "VALIDATION_ERROR_422"
            elif "401" in err_str or "403" in err_str:
                error_type = "AUTH_ERROR"
            elif "404" in err_str:
                error_type = "NOT_FOUND_404"
            else:
                error_type = "SERVER_ERROR"

            _log(f"[API-CALL] {label}: Attempt {attempt} FAILED — {error_type}")
            _log(f"[API-CALL] {label}: {err_str[:300]}")

            # Hard errors — no point retrying
            if error_type in ("VALIDATION_ERROR_422", "AUTH_ERROR", "NOT_FOUND_404"):
                return None

            if attempt < MAX_RETRIES:
                wait = _parse_retry_after(err_str)
                _log(f"[API-CALL] {label}: Waiting {wait}s before retry...")
                time.sleep(wait)

    _log(f"[API-CALL] {label}: All {MAX_RETRIES} attempts exhausted")
    return None


def _run_vton_single(
    model_url: str,
    garment_bytes: bytes,
    category: str,
    pose_label: str,
    garment_brief: str = "",
    accessories_note: str = "",
    extra_prompt: str = "",
) -> bytes | None:
    """
    Single VTON call: one model photo + garment -> one output image.
    Tries primary model (idm-vton with garment_des) then fallback (p-tryon).
    """
    _log(f"[VTON] [{pose_label}] model={model_url.split('/')[-1]}, category={category}")

    garment_b64 = base64.b64encode(garment_bytes).decode("utf-8")
    garment_uri = f"data:image/jpeg;base64,{garment_b64}"

    # Build rich garment description for idm-vton (critical for fidelity)
    garment_des = garment_brief or "garment"
    if accessories_note:
        garment_des += f". {accessories_note}"
    if extra_prompt:
        garment_des += f". {extra_prompt}"
    _log(f"[VTON] [{pose_label}] garment_des={garment_des[:120]}")

    # Primary: cuuupid/idm-vton (has garment_des for exact garment fidelity)
    output = _try_replicate(
        "cuuupid/idm-vton:0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985",
        {
            "human_img": model_url,
            "garm_img": garment_uri,
            "garment_des": garment_des,
            "category": category,
            "crop": True,
            "steps": 30,
        },
        f"idm-vton [{pose_label}]",
    )

    # Fallback: prunaai/p-tryon (cheaper but no garment description param)
    if output is None:
        _log(f"[VTON] [{pose_label}] Primary failed — waiting {INTER_CALL_DELAY}s, trying fallback...")
        time.sleep(INTER_CALL_DELAY)
        output = _try_replicate(
            "prunaai/p-tryon",
            {
                "model_image": model_url,
                "clothing_images": [garment_uri],
                "category": category,
                "num_inference_steps": 30,
            },
            f"p-tryon [{pose_label}]",
        )

    if output is None:
        _log(f"[VTON] [{pose_label}] All models failed")
        return None

    # Extract result URL from output
    if isinstance(output, list):
        result_url = str(output[0])
    elif hasattr(output, "url"):
        result_url = output.url
    else:
        result_url = str(output)

    try:
        img_bytes = _download_image(result_url)
        _log(f"[VTON] [{pose_label}] Done — {len(img_bytes)} bytes")
        return img_bytes
    except Exception as e:
        _log(f"[VTON] [{pose_label}] Download failed: {e}")
        return None


# ---------------------------------------------------------------------------
# PUBLIC API — Called from main.py
# ---------------------------------------------------------------------------

def generate_and_process_poses(
    garment_bytes: bytes,
    dress_style: str = "western",
    extra_prompt: str = "",
    detected_garment_type: str = "",
    garment_brief: str = "",
    accessories_note: str = "",
) -> list[dict]:
    """
    Generate 2 VTON images + build smart 6-panel collage.

    Output (2 images for Shopify):
      Image 1 — Hero: Full model front view (primary product photo)
      Image 2 — Collage: 6-panel garment-aware zoom crops

    The collage is built locally via PIL ($0.00) from the 2 VTON outputs.
    Crop panels are selected based on garment type (crop top, saree, etc.)
    to highlight exactly what buyers inspect for that garment.

    Cost: 2 × ~$0.024 = ~$0.048 per product (collage is free)

    Returns:
        list of dicts: [{label, bytes, filename}, ...]
        Empty list if all calls fail.
    """
    if not os.environ.get("REPLICATE_API_TOKEN"):
        _log("[PIPELINE] ERROR: REPLICATE_API_TOKEN not set!")
        return []

    category = _get_vton_category(detected_garment_type)
    _log(f"[PIPELINE] garment='{detected_garment_type}' -> category={category}, style={dress_style}")
    if garment_brief:
        _log(f"[PIPELINE] garment_brief: {garment_brief[:100]}")

    # Auto-generate accessories_note from dress_style if not provided by OpenAI
    if not accessories_note:
        if dress_style in ("western", "formal"):
            accessories_note = "Western styling, minimal accessories, simple chain only, no bindi, no Indian jewelry, no Indian earrings"
        elif dress_style == "traditional":
            accessories_note = "Traditional Indian styling, ethnic jewelry, jhumkas, bangles appropriate"
        elif dress_style == "fusion":
            accessories_note = "Modern fusion styling, mix of minimal western and subtle ethnic accessories"

    # Pick TWO different model images for pose variety
    model_urls = _pick_model_images(2)
    if len(model_urls) < 2:
        model_urls = model_urls * 2  # duplicate if pool too small

    poses = [
        ("Front View",       "front-view",     model_urls[0]),
        ("Side & Back View", "side-back-view",  model_urls[1]),
    ]

    results = []
    for i, (label, slug, model_url) in enumerate(poses):
        if i > 0:
            _log(f"[PIPELINE] Waiting {INTER_CALL_DELAY}s between calls...")
            time.sleep(INTER_CALL_DELAY)

        _log(f"[PIPELINE] Generating pose {i+1}/2: {label}")
        img_bytes = _run_vton_single(
            model_url, garment_bytes, category, label,
            garment_brief=garment_brief,
            accessories_note=accessories_note,
            extra_prompt=extra_prompt,
        )

        if img_bytes:
            results.append({
                "label": label,
                "bytes": img_bytes,
                "filename": f"pose-{i+1}-{slug}.jpg",
            })
        else:
            _log(f"[PIPELINE] Pose {i+1} ({label}) failed — skipping")

    _log(f"[PIPELINE] VTON complete: {len(results)}/2 images generated")

    if not results:
        return []

    # ===== Build final output: Hero + Smart Collage =====
    front_bytes = results[0]["bytes"]
    side_bytes = results[1]["bytes"] if len(results) > 1 else front_bytes

    final_images = [
        {
            "label": "Model View",
            "bytes": front_bytes,
            "filename": "hero-front-view.jpg",
        },
    ]

    # Build 6-panel collage from smart crops (free — local PIL)
    _log(f"[PIPELINE] Building 6-panel collage for garment='{detected_garment_type}'...")
    try:
        collage_bytes = build_smart_collage(
            front_image_bytes=front_bytes,
            side_image_bytes=side_bytes,
            garment_type=detected_garment_type,
        )
        final_images.append({
            "label": "Detail Views",
            "bytes": collage_bytes,
            "filename": "collage-detail-views.jpg",
        })
        _log(f"[PIPELINE] Collage built: {len(collage_bytes)} bytes")
    except Exception as e:
        _log(f"[PIPELINE] Collage build failed: {e} — adding raw side view")
        if len(results) > 1:
            final_images.append(results[1])

    _log(f"[PIPELINE] Final output: {len(final_images)} images (hero + collage)")
    return final_images
