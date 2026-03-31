"""
Image Utility Service (v6.1)
Local image processing — no external API calls.

Functions:
  crop_pose_grid()         — Split a 2×3 AI-generated grid into 6 individual images
  build_collage_from_grid() — Hero (panel 1) + 6-panel collage from AI grid
  compress_for_shopify()   — Smart JPEG compression without visible quality loss
  build_smart_collage()    — Legacy: 6-panel collage from 2 VTON images (garment-aware crops)
  resize_for_shopify()     — Resize to Shopify-optimal dimensions

Legacy (kept for backward compat):
  crop_grid_2x2(), crop_grid_3x2(), crop_grid_to_halves(), crop_half_to_two()
"""

import io
from PIL import Image


# ===================================================================
# IMAGE COMPRESSION — Smart quality reduction for Shopify uploads
# ===================================================================

def compress_for_shopify(
    img_bytes: bytes,
    max_size_kb: int = 800,
    min_quality: int = 55,
    max_dimension: int = 2048,
) -> bytes:
    """
    Compress an image for Shopify upload without visible quality loss.

    Strategy:
      1. Resize if larger than max_dimension on any side (preserves aspect ratio)
      2. Convert to JPEG with progressive quality reduction
      3. Stops at first quality level that fits under max_size_kb
      4. Never goes below min_quality to preserve details

    Args:
        img_bytes:     Raw image bytes (JPEG, PNG, WebP)
        max_size_kb:   Target max file size in KB (default: 800KB)
        min_quality:   Minimum JPEG quality (default: 55, preserves details)
        max_dimension: Max width/height in pixels (default: 2048)

    Returns:
        Compressed JPEG bytes (always returns something, even if over target)
    """
    img = Image.open(io.BytesIO(img_bytes))

    # Convert RGBA/P to RGB for JPEG
    if img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Step 1: Resize if too large (preserving aspect ratio)
    w, h = img.size
    if w > max_dimension or h > max_dimension:
        ratio = min(max_dimension / w, max_dimension / h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        print(f"[compress] Resized from {w}x{h} → {new_w}x{new_h}")

    # Step 2: Progressive quality reduction
    target_bytes = max_size_kb * 1024

    # Start high and reduce
    for quality in range(92, min_quality - 1, -3):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        size = buf.tell()
        if size <= target_bytes:
            print(f"[compress] Quality={quality}, size={size // 1024}KB (target: {max_size_kb}KB) ✓")
            return buf.getvalue()

    # If still over target at min_quality, return it anyway (don't destroy quality)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=min_quality, optimize=True)
    final_size = buf.tell()
    print(f"[compress] Min quality={min_quality}, size={final_size // 1024}KB (target was {max_size_kb}KB)")
    return buf.getvalue()


# ===================================================================
# SIMPLE MATHEMATICAL GRID CROP (for tryon — no divider detection)
# ===================================================================

def math_crop_grid(grid_image_bytes: bytes, cols: int = 2, rows: int = 3) -> list[bytes]:
    """
    Split a grid image into panels using pure math: width÷cols, height÷rows.
    No divider scanning, no brightness detection — just divide and crop.
    Always returns exactly cols×rows panels.

    This is used for tryon grids where we ask Gemini to generate panels
    edge-to-edge with NO divider lines, making mathematical splitting
    the most reliable approach.

    Args:
        grid_image_bytes: Raw image bytes of the grid
        cols: Number of columns (default 2)
        rows: Number of rows (default 3)

    Returns:
        list of JPEG bytes for each panel (reading order: left→right, top→bottom)
    """
    try:
        img = Image.open(io.BytesIO(grid_image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        cell_w = w // cols
        cell_h = h // rows

        print(f"[math-crop] Image: {w}×{h}px → {cols}×{rows} grid, cell: {cell_w}×{cell_h}px")

        # Trim a few pixels from each edge to remove any border artifacts
        trim = max(2, min(cell_w, cell_h) // 100)

        panels = []
        for r in range(rows):
            for c in range(cols):
                x1 = c * cell_w + trim
                y1 = r * cell_h + trim
                x2 = (c + 1) * cell_w - trim
                y2 = (r + 1) * cell_h - trim

                cell = img.crop((x1, y1, x2, y2))
                buf = io.BytesIO()
                cell.save(buf, format="JPEG", quality=92)
                panels.append(buf.getvalue())

                idx = r * cols + c + 1
                print(f"[math-crop] Panel {idx}: ({x1},{y1})→({x2},{y2}) = {cell.size[0]}×{cell.size[1]}px")

        return panels

    except Exception as e:
        import traceback
        print(f"[math-crop] Error: {e}")
        traceback.print_exc()
        return []


# ===================================================================
# AI GRID PROCESSING — Crop 2×2 or 2×3 grid from OpenAI into panels
# ===================================================================

HERO_PANEL_INDEX = 0  # First panel = front view = hero

# Collage assembly settings
COLLAGE_PANEL_W = 480
COLLAGE_PANEL_H = 640
COLLAGE_GAP = 8
COLLAGE_BG = (245, 245, 245)

# Divider detection thresholds
_BRIGHTNESS_THRESHOLD = 220  # Pixel avg above this = "white/light" (divider candidate)
_MIN_DIVIDER_FRACTION = 0.50  # At least 50% of a scan line must be bright to be a divider


def _find_divider_positions(img: Image.Image, axis: str, expected_cuts: int) -> list[int]:
    """
    Scan the image for white/light divider lines along the given axis.
    Returns a sorted list of pixel positions where dividers are detected.

    axis="vertical"   → scan each X column to find vertical dividers  (splits columns)
    axis="horizontal" → scan each Y row    to find horizontal dividers (splits rows)
    """
    import numpy as np
    arr = np.array(img)  # shape: (H, W, 3)
    h, w = arr.shape[:2]

    if axis == "vertical":
        # For each x-column, compute mean brightness across all rows
        brightness = arr.mean(axis=(0, 2))  # shape: (W,)
        length = w
        img_size = w
    else:
        # For each y-row, compute mean brightness across all columns
        brightness = arr.mean(axis=(1, 2))  # shape: (H,)
        length = h
        img_size = h

    # Find runs of bright pixels (potential divider bands)
    is_bright = brightness > _BRIGHTNESS_THRESHOLD

    # Group consecutive bright pixels into bands
    bands = []
    start = None
    for i in range(length):
        if is_bright[i]:
            if start is None:
                start = i
        else:
            if start is not None:
                bands.append((start, i - 1))
                start = None
    if start is not None:
        bands.append((start, length - 1))

    # Filter out bands at the very edges (border padding, not real dividers)
    margin = img_size * 0.08  # ignore first/last 8%
    interior_bands = [
        (s, e) for s, e in bands
        if s > margin and e < (img_size - margin)
    ]

    print(f"[grid-crop] {axis} divider scan: {len(interior_bands)} candidate bands from {len(bands)} total")

    if len(interior_bands) >= expected_cuts:
        # Sort by band width (wider = more confident), take the expected number
        interior_bands.sort(key=lambda b: b[1] - b[0], reverse=True)
        centers = sorted([(s + e) // 2 for s, e in interior_bands[:expected_cuts]])
        print(f"[grid-crop] {axis} dividers at: {centers}")
        return centers

    # Fallback: evenly-spaced mathematical split
    step = img_size / (expected_cuts + 1)
    centers = [int(step * (i + 1)) for i in range(expected_cuts)]
    print(f"[grid-crop] {axis} dividers: using mathematical fallback at {centers}")
    return centers


def _detect_grid_dimensions(img: Image.Image) -> tuple[int, int]:
    """
    Auto-detect whether the grid is 2×2 or 2×3.
    Strategy: use aspect ratio as the PRIMARY signal (reliable since we
    always request 1024×1536 for 2×3 grids), with divider scanning as
    secondary confirmation.

    - Aspect < 0.85  → 2×3 (image is taller than wide, e.g. 1024×1536 = 0.667)
    - Aspect >= 0.85 → check dividers, default to 2×2 (square-ish image)
    """
    import numpy as np
    w, h = img.size
    aspect = w / h if h > 0 else 1.0

    print(f"[grid-crop] Image: {w}×{h}px, aspect ratio: {aspect:.3f}")

    # PRIMARY SIGNAL: aspect ratio
    # A 2×3 grid of roughly square panels → aspect ≈ 0.667 (2/3)
    # A 2×2 grid of roughly square panels → aspect ≈ 1.0
    if aspect < 0.85:
        print(f"[grid-crop] → detected 2×3 grid (aspect {aspect:.3f} < 0.85 — taller image)")
        return 2, 3

    # For square-ish images, scan horizontal dividers as tiebreaker
    arr = np.array(img)
    brightness = arr.mean(axis=(1, 2))  # per-row mean brightness
    is_bright = brightness > _BRIGHTNESS_THRESHOLD

    # Group into bands
    bands = []
    start = None
    for i in range(len(brightness)):
        if is_bright[i]:
            if start is None:
                start = i
        else:
            if start is not None:
                bands.append((start, i - 1))
                start = None
    if start is not None:
        bands.append((start, len(brightness) - 1))

    # Filter edges
    margin = h * 0.08
    interior = [(s, e) for s, e in bands if s > margin and e < (h - margin)]

    real_h_dividers = len(interior)
    print(f"[grid-crop] Square-ish image, horizontal dividers found: {real_h_dividers}")

    if real_h_dividers >= 2:
        print(f"[grid-crop] → detected 2×3 grid (found {real_h_dividers} horizontal dividers in square image)")
        return 2, 3
    else:
        print(f"[grid-crop] → detected 2×2 grid (aspect {aspect:.3f} ≥ 0.85 + only {real_h_dividers} divider(s))")
        return 2, 2


def _count_real_dividers(img: Image.Image, axis: str) -> int:
    """
    Count how many REAL divider lines exist along the given axis.
    A real divider = a band of bright pixels (avg > threshold) spanning
    most of the image width/height, located in the interior (not edges).

    Returns: number of real interior divider bands found.
    """
    import numpy as np
    arr = np.array(img)
    h, w = arr.shape[:2]

    if axis == "horizontal":
        brightness = arr.mean(axis=(1, 2))  # per-row brightness
        img_size = h
    else:
        brightness = arr.mean(axis=(0, 2))  # per-column brightness
        img_size = w

    is_bright = brightness > _BRIGHTNESS_THRESHOLD
    margin = img_size * 0.08

    # Group consecutive bright pixels into bands
    bands = []
    start = None
    for i in range(len(brightness)):
        if is_bright[i]:
            if start is None:
                start = i
        else:
            if start is not None:
                bands.append((start, i - 1))
                start = None
    if start is not None:
        bands.append((start, len(brightness) - 1))

    # Keep only interior bands (not edge padding)
    interior = [(s, e) for s, e in bands if s > margin and e < (img_size - margin)]
    return len(interior)


def crop_pose_grid(grid_image_bytes: bytes) -> list[bytes]:
    """
    Split an AI-generated grid image into individual pose panels.

    Always splits as 2×3 (6 panels) — we always request a 2×3 grid from AI.

    Returns:
        list of JPEG image bytes (reading order: L→R, T→B).
        6 items, or [] on error.
    """
    try:
        img = Image.open(io.BytesIO(grid_image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        cols, rows = 2, 3  # Always 2×3 — we ALWAYS request 6 panels
        print(f"[grid-crop] Input: {w}×{h}px, forced {cols}×{rows} grid (6 panels)")

        # Find divider positions using brightness scanning
        v_dividers = _find_divider_positions(img, "vertical", expected_cuts=cols - 1)
        h_dividers = _find_divider_positions(img, "horizontal", expected_cuts=rows - 1)

        # Build column/row boundaries: [0, ..dividers.., w/h]
        col_edges = [0] + v_dividers + [w]
        row_edges = [0] + h_dividers + [h]

        # Inset to skip the actual divider pixels on each side
        inset = max(3, min(w, h) // 200)  # 3-5px

        panels = []
        for r in range(rows):
            for c in range(cols):
                x1 = col_edges[c] + (inset if c > 0 else 0)
                y1 = row_edges[r] + (inset if r > 0 else 0)
                x2 = col_edges[c + 1] - (inset if c < cols - 1 else 0)
                y2 = row_edges[r + 1] - (inset if r < rows - 1 else 0)

                cell = img.crop((x1, y1, x2, y2))
                buf = io.BytesIO()
                cell.save(buf, format="JPEG", quality=92)
                panels.append(buf.getvalue())
                idx = r * cols + c + 1
                print(f"[grid-crop] Panel {idx}: ({x1},{y1})→({x2},{y2}) = {cell.size[0]}×{cell.size[1]}px")

        expected = cols * rows
        assert len(panels) == expected, (
            f"[grid-crop] BUG: expected {expected} panels, got {len(panels)}"
        )
        return panels

    except Exception as e:
        import traceback
        print(f"[grid-crop] Error: {e}")
        traceback.print_exc()
        return []


def build_collage_from_grid(grid_image_bytes: bytes) -> dict:
    """
    Process an AI-generated grid into hero image + collage.

    Always expects a 2×3 (6 panels) grid.
    Falls back to raw grid if cropping fails entirely.

    Returns:
        dict with:
          "hero":    JPEG bytes of the front-view panel (Shopify Photo 1)
          "collage": JPEG bytes of the collage (Shopify last photo)
          "panels":  list of individual JPEG bytes (6)
    """
    panels = crop_pose_grid(grid_image_bytes)

    if len(panels) != 6:
        print(f"[collage] CRITICAL: expected 6 panels, got {len(panels)} — falling back to raw grid")
        return {
            "hero": grid_image_bytes,
            "collage": grid_image_bytes,
            "panels": [],
        }

    # Hero = first panel (front view)
    hero = panels[HERO_PANEL_INDEX]
    print(f"[collage] Hero: panel {HERO_PANEL_INDEX + 1} ({len(hero)} bytes), total panels={len(panels)}")

    # Build collage — always 2×3
    collage = _assemble_collage_2x3(panels)

    return {
        "hero": hero,
        "collage": collage,
        "panels": panels,
    }


def _assemble_collage(panel_bytes_list: list[bytes], cols: int, rows: int) -> bytes:
    """
    Assemble panel images into a collage grid with the given layout.
    Each panel is resized to COLLAGE_PANEL_W × COLLAGE_PANEL_H.
    """
    total_w = cols * COLLAGE_PANEL_W + (cols - 1) * COLLAGE_GAP
    total_h = rows * COLLAGE_PANEL_H + (rows - 1) * COLLAGE_GAP
    canvas = Image.new("RGB", (total_w, total_h), COLLAGE_BG)
    print(f"[collage] Layout: {cols}×{rows} ({len(panel_bytes_list)} panels), canvas: {total_w}×{total_h}px")

    for idx, panel_bytes in enumerate(panel_bytes_list[:cols * rows]):
        row = idx // cols
        col = idx % cols
        x = col * (COLLAGE_PANEL_W + COLLAGE_GAP)
        y = row * (COLLAGE_PANEL_H + COLLAGE_GAP)

        try:
            panel_img = Image.open(io.BytesIO(panel_bytes))
            if panel_img.mode != "RGB":
                panel_img = panel_img.convert("RGB")
            panel_img = _resize_cover(panel_img, COLLAGE_PANEL_W, COLLAGE_PANEL_H)
            canvas.paste(panel_img, (x, y))
        except Exception as e:
            print(f"[collage] Panel {idx+1} error: {e}")

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=92)
    result = buf.getvalue()
    print(f"[collage] Assembled: {total_w}×{total_h}px ({len(result)} bytes)")
    return result


def _assemble_collage_2x3(panel_bytes_list: list[bytes]) -> bytes:
    """Assemble 6 panels into a 2×3 collage."""
    return _assemble_collage(panel_bytes_list, cols=2, rows=3)


def _assemble_collage_2x2(panel_bytes_list: list[bytes]) -> bytes:
    """Assemble 4 panels into a 2×2 collage."""
    return _assemble_collage(panel_bytes_list, cols=2, rows=2)


def build_3d_front_back(panels: list[bytes]) -> bytes | None:
    """
    Return the 3D front+back panel (Panel 6, index 5).
    Panel 6 already contains FRONT + BACK side-by-side in a single panel.
    Returns JPEG bytes, or None if panels are missing.
    """
    if len(panels) < 6:
        print(f"[3d-composite] Not enough panels ({len(panels)}), need 6")
        return None
    return panels[5]


def _resize_cover(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize image to cover target dimensions, center-cropping any excess."""
    w, h = img.size
    target_ratio = target_w / target_h
    img_ratio = w / h if h > 0 else 1

    if img_ratio > target_ratio:
        # Image is wider — scale by height, crop width
        new_h = target_h
        new_w = int(new_h * img_ratio)
    else:
        # Image is taller — scale by width, crop height
        new_w = target_w
        new_h = int(new_w / img_ratio) if img_ratio > 0 else target_h

    resized = img.resize((max(new_w, 1), max(new_h, 1)), Image.LANCZOS)
    cx = (resized.width - target_w) // 2
    cy = (resized.height - target_h) // 2
    return resized.crop((cx, cy, cx + target_w, cy + target_h))

# ---------------------------------------------------------------------------
# Crop maps: 6 tuples of (source, left%, top%, right%, bottom%)
#   source: "front" or "side"
#   percentages: crop region of the source image (0–100)
#
# Each garment type maps to a list of 6 crop definitions.
# Panels 1–2 are always full images (front + side) for context.
# Panels 3–6 are zoom crops that highlight key garment details.
# ---------------------------------------------------------------------------

_CROP_MAPS: dict[str, list[tuple[str, int, int, int, int]]] = {

    # ---- UPPER BODY ----
    "upper_body_default": [
        ("front", 0, 0, 100, 100),     # P1: Full front
        ("side",  0, 0, 100, 100),     # P2: Full side/back
        ("front", 5, 5, 95, 55),       # P3: Shoulders-to-waist fit
        ("side",  5, 5, 95, 55),       # P4: Back view upper half
        ("front", 10, 8, 90, 38),      # P5: Neckline close-up
        ("front", 5, 25, 95, 55),      # P6: Hem & fit detail
    ],

    # ---- CROP TOP — midriff is the selling point ----
    "crop_top": [
        ("front", 0, 0, 100, 100),     # P1: Full body — midriff visible
        ("side",  0, 0, 100, 100),     # P2: Side/back
        ("front", 5, 8, 95, 50),       # P3: Crop zone — cut line visible
        ("side",  5, 8, 95, 50),       # P4: Back crop line
        ("front", 10, 8, 90, 32),      # P5: Neckline + sleeves
        ("front", 10, 28, 90, 52),     # P6: Crop line detail
    ],

    # ---- KURTI — neckline embroidery + length ----
    "kurti": [
        ("front", 0, 0, 100, 100),     # P1: Full front
        ("side",  0, 0, 100, 100),     # P2: Side drape
        ("front", 10, 8, 90, 35),      # P3: Neckline/yoke embroidery
        ("front", 5, 10, 95, 55),      # P4: Chest-to-waist fit
        ("front", 5, 55, 95, 95),      # P5: Hem & length border
        ("side",  5, 10, 95, 60),      # P6: Back design
    ],

    # ---- LOWER BODY — waistband + drape + hem ----
    "lower_body": [
        ("front", 0, 0, 100, 100),     # P1: Full body proportion
        ("side",  0, 0, 100, 100),     # P2: Side silhouette
        ("front", 5, 35, 95, 95),      # P3: Full bottom zoom
        ("side",  5, 35, 95, 95),      # P4: Side drape / fit
        ("front", 10, 35, 90, 55),     # P5: Waistband close-up
        ("front", 5, 70, 95, 98),      # P6: Hem detail
    ],

    # ---- DRESS — bodice + skirt ----
    "dress": [
        ("front", 0, 0, 100, 100),     # P1: Complete silhouette
        ("side",  0, 0, 100, 100),     # P2: Side drape & back
        ("front", 5, 5, 95, 45),       # P3: Bodice — neckline + waist
        ("side",  5, 5, 95, 50),       # P4: Back detail — zip, cut-out
        ("front", 5, 45, 95, 95),      # P5: Skirt — flare, pleats
        ("front", 10, 70, 90, 98),     # P6: Hem close-up
    ],

    # ---- GOWN — dramatic details ----
    "gown": [
        ("front", 0, 0, 100, 100),     # P1: Majestic full-length
        ("side",  0, 0, 100, 100),     # P2: Side/back dramatic
        ("front", 5, 5, 95, 40),       # P3: Bodice / embellishment
        ("side",  5, 5, 95, 45),       # P4: Back design — lace-up
        ("front", 0, 50, 100, 100),    # P5: Skirt volume
        ("front", 10, 8, 90, 35),      # P6: Neckline — sweetheart etc
    ],

    # ---- SAREE — blouse + pleats + pallu ----
    "saree": [
        ("front", 0, 0, 100, 100),     # P1: Full drape
        ("side",  0, 0, 100, 100),     # P2: Pallu drape from behind
        ("front", 5, 5, 95, 38),       # P3: Blouse + pallu
        ("side",  5, 5, 95, 45),       # P4: Pallu back drape
        ("front", 5, 32, 95, 62),      # P5: Pleats — tucked section
        ("front", 0, 60, 100, 100),    # P6: Border & fall
    ],

    # ---- COORD SET — show top + bottom separately ----
    "coord_set": [
        ("front", 0, 0, 100, 100),     # P1: Full set together
        ("side",  0, 0, 100, 100),     # P2: Side view complete set
        ("front", 5, 5, 95, 50),       # P3: Top piece only
        ("front", 5, 40, 95, 98),      # P4: Bottom piece only
        ("front", 10, 8, 90, 35),      # P5: Top detail — neckline
        ("side",  5, 35, 95, 95),      # P6: Bottom from behind
    ],

    # ---- LEHENGA — choli + skirt + back ----
    "lehenga": [
        ("front", 0, 0, 100, 100),     # P1: Full ensemble
        ("side",  0, 0, 100, 100),     # P2: Side — skirt flare
        ("front", 5, 5, 95, 40),       # P3: Choli — embroidery
        ("front", 0, 40, 100, 100),    # P4: Lehenga skirt
        ("front", 10, 8, 90, 32),      # P5: Choli neckline
        ("side",  5, 5, 95, 50),       # P6: Back design — dori
    ],

    # ---- ANARKALI / SHARARA — flare drama ----
    "anarkali": [
        ("front", 0, 0, 100, 100),     # P1: Full flare
        ("side",  0, 0, 100, 100),     # P2: Side silhouette
        ("front", 5, 5, 95, 40),       # P3: Bodice embroidery
        ("side",  5, 5, 95, 45),       # P4: Back detail
        ("front", 0, 50, 100, 100),    # P5: Flare / skirt volume
        ("front", 10, 8, 90, 32),      # P6: Neckline
    ],
}

# Garment type string → crop map key resolver
_GARMENT_TO_CROP_KEY: dict[str, str] = {
    # Upper body
    "top": "upper_body_default", "t-shirt": "upper_body_default",
    "shirt": "upper_body_default", "blouse": "upper_body_default",
    "casual-top": "upper_body_default", "korean-top": "upper_body_default",
    "jacket": "upper_body_default", "sweatshirt": "upper_body_default",
    "hoodie": "upper_body_default", "polo": "upper_body_default",
    # Crop top
    "crop top": "crop_top", "crop-top": "crop_top",
    "fancy-crop-top": "crop_top",
    # Kurti
    "kurti": "kurti", "kurti-set": "kurti",
    # Lower body
    "bottom": "lower_body", "palazzo": "lower_body", "skirt": "lower_body",
    "jeans": "lower_body", "trousers": "lower_body", "pants": "lower_body",
    "shorts": "lower_body", "leggings": "lower_body",
    # Dress
    "dress": "dress", "single-piece": "dress", "bodycon": "dress",
    "maxi": "dress", "casual-maxi": "dress", "jumpsuit": "dress",
    # Gown
    "gown": "gown",
    # Saree
    "saree": "saree",
    # Coord set
    "cord-set": "coord_set", "coord set": "coord_set", "co-ord": "coord_set",
    # Lehenga
    "lehenga": "lehenga",
    # Anarkali / Sharara
    "anarkali": "anarkali", "sharara": "anarkali",
    # Indo-western
    "indo-western": "dress",
    # Suits
    "suits": "kurti",
}


def _resolve_crop_key(garment_type: str) -> str:
    """Resolve garment type string to crop map key. Fuzzy match with fallback."""
    if not garment_type:
        return "upper_body_default"
    key = garment_type.lower().strip()
    # Exact match
    if key in _GARMENT_TO_CROP_KEY:
        return _GARMENT_TO_CROP_KEY[key]
    # Fuzzy: check if any known key is a substring
    for garment, crop_key in _GARMENT_TO_CROP_KEY.items():
        if garment in key or key in garment:
            return crop_key
    print(f"[collage] Unknown garment type '{garment_type}' → defaulting to upper_body_default")
    return "upper_body_default"


def _crop_panel(img: Image.Image, left_pct: int, top_pct: int,
                right_pct: int, bottom_pct: int) -> Image.Image:
    """
    Crop a percentage-based region from an image and scale to panel size.
    Uses high-quality LANCZOS resampling for sharp zoom-in effect.
    """
    w, h = img.size
    box = (
        int(w * left_pct / 100),
        int(h * top_pct / 100),
        int(w * right_pct / 100),
        int(h * bottom_pct / 100),
    )
    cropped = img.crop(box)
    # Scale to fill panel — cover mode (maintain aspect, center crop to exact size)
    cr_w, cr_h = cropped.size
    panel_ratio = COLLAGE_PANEL_W / COLLAGE_PANEL_H
    crop_ratio = cr_w / cr_h if cr_h > 0 else 1
    if crop_ratio > panel_ratio:
        new_h = COLLAGE_PANEL_H
        new_w = int(new_h * crop_ratio)
    else:
        new_w = COLLAGE_PANEL_W
        new_h = int(new_w / crop_ratio) if crop_ratio > 0 else COLLAGE_PANEL_H
    resized = cropped.resize((max(new_w, 1), max(new_h, 1)), Image.LANCZOS)
    # Center crop to exact panel dimensions
    cx = (resized.width - COLLAGE_PANEL_W) // 2
    cy = (resized.height - COLLAGE_PANEL_H) // 2
    return resized.crop((cx, cy, cx + COLLAGE_PANEL_W, cy + COLLAGE_PANEL_H))


def build_smart_collage(
    front_image_bytes: bytes,
    side_image_bytes: bytes,
    garment_type: str = "",
) -> bytes:
    """
    Build a 6-panel fashion collage from 2 VTON images with garment-aware zoom crops.

    Each garment type has a specific crop map optimized for what buyers inspect:
    - Crop tops: midriff exposure, crop line
    - Sarees: blouse, pleats, pallu/border
    - Coord sets: top + bottom shown separately
    - Lehenga: choli + skirt individually
    - etc.

    Layout: 2 columns × 3 rows, 480×640px per panel, 8px gap.
    Total: 968×1936px collage.

    Args:
        front_image_bytes: VTON front view image bytes
        side_image_bytes: VTON side/back view image bytes
        garment_type: detected garment type string (e.g., "crop top", "saree")

    Returns:
        JPEG bytes of the 6-panel collage
    """
    crop_key = _resolve_crop_key(garment_type)
    crop_map = _CROP_MAPS.get(crop_key, _CROP_MAPS["upper_body_default"])
    print(f"[collage] garment='{garment_type}' → crop_key='{crop_key}' ({len(crop_map)} panels)")

    # Load source images
    sources: dict[str, Image.Image] = {}
    try:
        front = Image.open(io.BytesIO(front_image_bytes))
        if front.mode != "RGB":
            front = front.convert("RGB")
        sources["front"] = front
        print(f"[collage] Front image: {front.size[0]}×{front.size[1]}px")
    except Exception as e:
        print(f"[collage] Front image load failed: {e}")
        return front_image_bytes  # Return raw front as fallback

    try:
        side = Image.open(io.BytesIO(side_image_bytes))
        if side.mode != "RGB":
            side = side.convert("RGB")
        sources["side"] = side
        print(f"[collage] Side image: {side.size[0]}×{side.size[1]}px")
    except Exception as e:
        print(f"[collage] Side image load failed: {e} — using front as fallback for side")
        sources["side"] = sources["front"]

    # Build collage canvas
    cols, rows = 2, 3
    total_w = cols * COLLAGE_PANEL_W + (cols - 1) * COLLAGE_GAP
    total_h = rows * COLLAGE_PANEL_H + (rows - 1) * COLLAGE_GAP
    collage = Image.new("RGB", (total_w, total_h), COLLAGE_BG)

    for idx, (source_key, l, t, r, b) in enumerate(crop_map):
        row = idx // cols
        col = idx % cols
        x = col * (COLLAGE_PANEL_W + COLLAGE_GAP)
        y = row * (COLLAGE_PANEL_H + COLLAGE_GAP)

        src_img = sources.get(source_key, sources["front"])
        try:
            panel = _crop_panel(src_img, l, t, r, b)
            collage.paste(panel, (x, y))
            print(f"[collage] Panel {idx+1}: {source_key} crop({l},{t},{r},{b}) → ({x},{y})")
        except Exception as e:
            print(f"[collage] Panel {idx+1} error: {e} — blank")

    buf = io.BytesIO()
    collage.save(buf, format="JPEG", quality=92)
    result = buf.getvalue()
    print(f"[collage] Done: {total_w}×{total_h}px ({len(result)} bytes)")
    return result


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
