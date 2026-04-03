"""
Image Provider — Adapter-based AI image generation (v1)

Abstract interface for generating fashion model images from garment photos.
Concrete implementations:
  - OpenAIImageProvider  (primary — gpt-image-1-mini / gpt-image-1.5)
  - FashnAIProvider      (stub — plug in later)
  - ReplicateProvider    (legacy — VTON-based, kept for testing)

Provider is selected via IMAGE_PROVIDER env var (default: "openai").

ARCHITECTURE:
  1. Text analysis (openai_service) returns a `model_prompt` describing the scene
  2. Provider takes garment photo + model_prompt → generates a single image
     containing a 2×3 grid of 6 model poses
  3. image_utils crops the grid into hero + 6-panel collage
"""

import os
import io
import base64
import time
from abc import ABC, abstractmethod


def _log(msg: str):
    print(f"[IMAGE-PROVIDER] {msg}")


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class ImageProvider(ABC):
    """Base class for AI image generation providers."""

    @abstractmethod
    def generate_pose_grid(
        self,
        garment_images: list[bytes],
        model_prompt: str,
        quality: str = "medium",
        extra_prompt: str = "",
        garment_design_details: str = "",
        uploaded_image_info: list[dict] = None,
        garment_type: str = "",
    ) -> bytes | None:
        """
        Generate a single image containing a 2×3 grid of 6 model poses.

        Args:
            garment_images: list of garment photo bytes (front, back, detail views)
            model_prompt: rich scene description from OpenAI text analysis
            quality: "low" | "medium" | "high"
            extra_prompt: optional user styling instructions
            garment_design_details: detailed inventory of text, logos, patterns from AI text analysis
            uploaded_image_info: list of dicts with 'index', 'shows', 'details' from AI text analysis

        Returns:
            JPEG/PNG bytes of the 2×3 grid image, or None on failure
        """
        ...

    def generate_tryon_grid(
        self,
        person_image: bytes,
        garment_images: list[bytes],
        garment_briefs: list[str],
        garment_categories: list[str],
        garment_design_details_list: list[str] = None,
        garment_3d_images: list[bytes | None] = None,
        tryon_mode: str = "customer_editorial",
        quality: str = "medium",
    ) -> bytes | None:
        """
        Generate a 2×3 try-on grid: the PERSON wearing the GARMENT(s).

        Args:
            person_image: customer's photo bytes (face/body reference)
            garment_images: list of garment product photo bytes (from Shopify CDN)
            garment_briefs: list of one-line garment descriptions
            garment_categories: list of "upper_body" | "lower_body" | "full_body"
            garment_design_details_list: list of detailed design descriptions per garment
            garment_3d_images: list of 3D product shot bytes (garment on invisible mannequin)
            tryon_mode: generation mode (default: customer_editorial)
            quality: "low" | "medium" | "high"

        Returns:
            JPEG/PNG bytes of the 2×3 grid image, or None on failure
        """
        _log(f"{self.__class__.__name__}.generate_tryon_grid() — not implemented")
        return None


# ---------------------------------------------------------------------------
# OpenAI Image Provider (primary)
# ---------------------------------------------------------------------------

class OpenAIImageProvider(ImageProvider):
    """
    Generate fashion model grid using OpenAI GPT Image API.
    Uses the Responses API with image_generation tool for reference image support.

    Models: gpt-image-1-mini (default, cost-efficient) or gpt-image-1.5 (best quality)
    """

    # Default pose descriptions for the 6-panel grid (2×3)
    # Panel 1: Hero — garment-focused framing (top=waist-up, bottom=hip-to-toe, full=head-to-toe)
    # Panel 2: Model back view
    # Panel 3: Model 3/4 angle
    # Panel 4: Close-up of product piece ON the model
    # Panel 5: Walking / movement pose
    # Panel 6: 3D garment FRONT + BACK floating (invisible mannequin — NOT visible)
    _DEFAULT_POSES = [
        ("hero",    "HERO — Model wearing the garment, framed to emphasize the product piece"),
        ("back",    "Back full-body view, showing the back design/print/pattern and fit"),
        ("side",    "3/4 angle view from the right, showing silhouette and garment drape"),
        ("detail",  "Close-up of the product piece ON the model — fabric, print, neckline detail"),
        ("walking", "Walking or movement pose — showing garment flow and drape in motion"),
        ("3d",      "3D PRODUCT SHOT — garment FRONT + BACK floating in mid-air (invisible mannequin, NOT visible), white background, NO model"),
    ]

    @staticmethod
    def _build_dynamic_panels(uploaded_image_info: list[dict], garment_type: str = "") -> list[str]:
        """
        Build 6 panel descriptions dynamically based on garment type + uploads.

        LAYOUT (v3 — garment-focused):
          Panel 1: Hero — camera framing adapts to garment type
          Panel 2: Model back view
          Panel 3: Model 3/4 angle
          Panel 4: Close-up of product piece ON the model
          Panel 5: Walking / movement pose
          Panel 6: 3D garment FRONT + BACK floating (invisible mannequin — LOCKED, no model)
        """
        gt = garment_type.lower().strip() if garment_type else ""

        # ---- Garment-type classification sets ----
        # IMPORTANT: _FULL is checked FIRST so compound types like
        # "shirt dress", "cape dress", "blazer set" are correctly
        # classified as full-outfit instead of upper/lower.
        _FULL = {"dress", "gown", "saree", "sari", "lehenga", "lehnga",
                 "anarkali", "jumpsuit", "romper", "cord-set", "co-ord",
                 "co-ord set", "coord-set", "salwar-suit", "salwar suit",
                 "sharara", "gharara", "kaftan", "maxi", "midi", "bodycon",
                 "dungaree", "overalls", "one-piece", "single-piece",
                 "kurti set", "kurti-set", "kurta set", "kurta-set",
                 "churidar", "churidar set", "pant suit", "pantsuit",
                 "coord set", "plazo set", "palazzo set"}
        _UPPER = {"top", "crop-top", "blouse", "shirt", "kurti", "tunic", "hoodie",
                  "sweater", "jacket", "blazer", "tee", "t-shirt", "polo", "tank-top",
                  "camisole", "cardigan", "shrug", "vest", "corset", "bustier", "cape",
                  "kurta"}
        _LOWER = {"palazzo", "skirt", "pants", "trousers", "jeans", "leggings",
                  "shorts", "culottes", "dhoti-pants", "joggers", "capri", "plazo"}

        def _matches(gt_str: str, keyword_set: set) -> bool:
            """Check if garment type matches any keyword — exact match or substring."""
            if gt_str in keyword_set:
                return True
            return any(kw in gt_str for kw in keyword_set)

        # ---- Panel 1 (Hero): framing depends on garment type ----
        # Check FULL first → then UPPER → then LOWER → else default to FULL
        if _matches(gt, _FULL):
            hero_desc = ("HERO — Model wearing the garment, full body HEAD TO TOE. "
                         "The complete outfit fills the frame. "
                         "Front-facing, confident pose, showing the full garment clearly. "
                         "Soft studio lighting, clean background.")
            detail_desc = ("CLOSE-UP of the outfit on the model — showing fabric texture, "
                           "embroidery, print/logo, embellishments, and craftsmanship "
                           "details up close on the model.")
            threed_desc = ("PROFESSIONAL GHOST MANNEQUIN PHOTOGRAPHY (hollow-man technique) — "
                           "the COMPLETE OUTFIT retains its natural 3D worn shape and volume, "
                           "but the body inside has been COMPLETELY DIGITALLY REMOVED. "
                           "The garment appears HOLLOW and EMPTY inside — you can see into the neckline/collar opening. "
                           "There is NO body, NO skin, NO mannequin form, NO human shape — "
                           "ONLY the empty garment shell holding its shape as if the wearer vanished. "
                           "Split into TWO HALVES inside this single panel: "
                           "LEFT HALF = FRONT VIEW, RIGHT HALF = BACK VIEW (rotated 180°). "
                           "Both halves on clean white background. "
                           "Full garment visible neckline to hem in BOTH halves, perfectly lit, premium e-commerce photography.")
        elif _matches(gt, _UPPER):
            hero_desc = ("HERO — WAIST-UP HALF-BODY SHOT of model wearing the garment. "
                         "Camera frames from HEAD TO WAIST ONLY — crop the image at the waist/hip line. "
                         "DO NOT show legs, knees, or feet. The bottom edge of the frame is at the waist. "
                         "The TOP garment fills 70-80% of the visible area. "
                         "Show neckline, sleeves, print, and fit prominently. "
                         "This is a CLOSE-UP HALF-BODY portrait, NOT a full-body shot. "
                         "Front-facing, confident pose, soft studio lighting.")
            detail_desc = ("CLOSE-UP of the TOP on the model — camera zooms into the upper body. "
                           "Show neckline, collar, sleeve detail, fabric texture, print/logo up close. "
                           "Camera focuses ONLY on the top garment piece.")
            threed_desc = ("PROFESSIONAL GHOST MANNEQUIN PHOTOGRAPHY (hollow-man technique) — "
                           "ONLY the TOP garment retains its natural 3D worn shape and volume, "
                           "but the body inside has been COMPLETELY DIGITALLY REMOVED. "
                           "The garment appears HOLLOW and EMPTY inside — you can see into the neckline/collar opening. "
                           "There is NO body, NO skin, NO mannequin form, NO human shape — "
                           "ONLY the empty garment shell holding its shape as if the wearer vanished. "
                           "Split into TWO HALVES inside this single panel: "
                           "LEFT HALF = FRONT VIEW, RIGHT HALF = BACK VIEW (rotated 180°). "
                           "Both halves on clean white background. NO bottom wear. "
                           "Just the top piece in both halves, perfectly lit, premium e-commerce photography.")
        elif _matches(gt, _LOWER):
            hero_desc = ("HERO — WAIST-DOWN HALF-BODY SHOT of model wearing the garment. "
                         "Camera frames from HIP TO TOE ONLY — crop the image at the hip/waist line. "
                         "DO NOT prominently show face or upper body. The top edge of the frame is at the hip. "
                         "The BOTTOM garment fills 70-80% of the visible area. "
                         "Show waistband, drape, pattern, and silhouette prominently. "
                         "This is a LOWER-BODY focused shot, NOT a full-body shot. "
                         "Confident standing pose, soft studio lighting.")
            detail_desc = ("CLOSE-UP of the BOTTOM on the model — camera zooms into the lower body. "
                           "Show waistband, fabric drape, pattern detail, hem, fit silhouette. "
                           "Camera focuses ONLY on the bottom garment piece.")
            threed_desc = ("PROFESSIONAL GHOST MANNEQUIN PHOTOGRAPHY (hollow-man technique) — "
                           "ONLY the BOTTOM garment retains its natural 3D worn shape and volume, "
                           "but the body inside has been COMPLETELY DIGITALLY REMOVED. "
                           "The garment appears HOLLOW and EMPTY inside — you can see into the waistband opening. "
                           "There is NO body, NO skin, NO mannequin form, NO human shape — "
                           "ONLY the empty garment shell holding its shape as if the wearer vanished. "
                           "Split into TWO HALVES inside this single panel: "
                           "LEFT HALF = FRONT VIEW, RIGHT HALF = BACK VIEW (rotated 180°). "
                           "Both halves on clean white background. NO top wear. "
                           "Just the bottom piece in both halves, perfectly lit, premium e-commerce photography.")
        else:
            # Unknown type → default to full-body (safest)
            hero_desc = ("HERO — Model wearing the garment, full body HEAD TO TOE. "
                         "The complete outfit fills the frame. "
                         "Front-facing, confident pose, showing the full garment clearly. "
                         "Soft studio lighting, clean background.")
            detail_desc = ("CLOSE-UP of the outfit on the model — showing fabric texture, "
                           "embroidery, print/logo, embellishments, and craftsmanship "
                           "details up close on the model.")
            threed_desc = ("PROFESSIONAL GHOST MANNEQUIN PHOTOGRAPHY (hollow-man technique) — "
                           "the COMPLETE OUTFIT retains its natural 3D worn shape and volume, "
                           "but the body inside has been COMPLETELY DIGITALLY REMOVED. "
                           "The garment appears HOLLOW and EMPTY inside — you can see into the neckline/collar opening. "
                           "There is NO body, NO skin, NO mannequin form, NO human shape — "
                           "ONLY the empty garment shell holding its shape as if the wearer vanished. "
                           "Split into TWO HALVES inside this single panel: "
                           "LEFT HALF = FRONT VIEW, RIGHT HALF = BACK VIEW (rotated 180°). "
                           "Both halves on clean white background. "
                           "Full garment visible neckline to hem in BOTH halves, perfectly lit, premium e-commerce photography.")

        # ---- Build 6 panels ----
        panels = [
            hero_desc,
            "Back full-body view — showing the back design/print/pattern and fit of the garment",
            "3/4 angle view from the right — showing the silhouette, sleeve detail, and garment drape",
            detail_desc,
            "Walking or movement pose — showing garment flow, drape, and silhouette in motion",  # Panel 5: walking
            threed_desc,       # Panel 6: LOCKED — 3D product FRONT + BACK
        ]

        # ---- Assign uploaded image references to panels 0-4 ----
        # Panel 5 (index 5) is LOCKED for the 3D garment shot
        _SLOT_MAP = {
            "front":       0,  # Panel 1 (hero)
            "back":        1,  # Panel 2
            "side":        2,  # Panel 3
            "detail":      3,  # Panel 4
            "dupatta":     3,  # Panel 4 area
            "accessory":   3,  # Panel 4 area
            "full-outfit": 4,  # Panel 5 area
            "other":       4,  # Panel 5 area
        }

        used_slots = {5}  # Panel 6 is LOCKED (3D front + back)

        if not uploaded_image_info:
            return panels

        for img_info in uploaded_image_info:
            shows = img_info.get("shows", "other").lower().strip()
            details = img_info.get("details", "")
            idx = int(img_info.get("index", 0))

            preferred_slot = _SLOT_MAP.get(shows, 3)

            slot = preferred_slot
            while slot in used_slots and slot < 5:
                slot += 1
            if slot >= 5 or slot in used_slots:
                for s in range(5):
                    if s not in used_slots:
                        slot = s
                        break
            if slot >= 5 or slot in used_slots:
                continue

            used_slots.add(slot)

            if shows == "front":
                panels[slot] = f"Front view — REPRODUCE IMAGE {idx} (FRONT) EXACTLY. {details}. Full garment visible head to toe."
            elif shows == "back":
                panels[slot] = f"Back full-body view — REPRODUCE IMAGE {idx} (BACK) EXACTLY. {details}. Show the back of the garment as in the reference."
            elif shows == "side":
                panels[slot] = f"Side/3-quarter view — REPRODUCE the angle from IMAGE {idx} (SIDE). {details}."
            elif shows == "detail":
                panels[slot] = f"Close-up detail — REPRODUCE details from IMAGE {idx} (DETAIL). {details}. Fabric texture, print quality up close."
            elif shows == "dupatta":
                panels[slot] = f"Dupatta/drape styling — wearing/draping from IMAGE {idx}. {details}."
            elif shows == "accessory":
                panels[slot] = f"Styled with accessory from IMAGE {idx}. {details}."
            elif shows == "full-outfit":
                panels[slot] = f"Full styled outfit — REPRODUCE the complete look from IMAGE {idx}. {details}."
            else:
                panels[slot] = f"Pose showing details from IMAGE {idx}. {details}."

        return panels

    def generate_pose_grid(
        self,
        garment_images: list[bytes],
        model_prompt: str,
        quality: str = "medium",
        extra_prompt: str = "",
        garment_design_details: str = "",
        uploaded_image_info: list[dict] = None,
        garment_type: str = "",
    ) -> bytes | None:
        """
        Generate 6-pose grid via OpenAI.
        Panels 1-2: 3D product shots (garment only)
        Panel 3: Product focus (top/bottom/full based on garment_type)
        Panels 4-6: Model wearing the garment
        """
        from openai import OpenAI
        import traceback as _tb

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            _log("ERROR: OPENAI_API_KEY environment variable is not set!")
            return None

        client = OpenAI(api_key=api_key)
        quality = quality.lower() if quality else "low"
        if quality not in ("low", "medium", "high"):
            quality = "low"

        num_images = len(garment_images)
        _log(f"Quality: {quality} | API key ends with: ...{api_key[-4:]} | Reference images: {num_images}")

        # Build garment references as base64
        garment_b64_list = [base64.b64encode(img).decode("utf-8") for img in garment_images]

        # Build image labels from AI detection (or fallback)
        img_labels = []  # list of (shows, details) per image
        if uploaded_image_info and len(uploaded_image_info) >= num_images:
            for info in uploaded_image_info[:num_images]:
                img_labels.append((info.get("shows", "unknown"), info.get("details", "")))
        else:
            # Fallback: assume front, back, detail order
            fallback = ["front", "back", "detail"]
            for i in range(num_images):
                img_labels.append((fallback[i] if i < len(fallback) else "other", ""))

        _log(f"Image labels: {[lbl[0] for lbl in img_labels]}")

        # Build image context with specific labels per image
        if num_images == 1:
            show_type = img_labels[0][0].upper()
            image_context = f"You are given 1 REFERENCE PHOTO of the garment (IMAGE 1 = {show_type} view)."
        else:
            views_desc = []
            for i, (shows, details) in enumerate(img_labels):
                desc = f"IMAGE {i+1} = {shows.upper()} view"
                if details:
                    desc += f" ({details})"
                views_desc.append(desc)
            views_str = "; ".join(views_desc)
            image_context = f"""You are given {num_images} REFERENCE PHOTOS of the SAME garment/outfit:
{views_str}

STUDY EACH reference photo individually. Each image shows a SPECIFIC angle or component.
NOTE: The reference may be a COMPOSITE image with labeled sections (FRONT, BACK, etc.) side by side — treat each labeled section as a separate reference.
For each panel that has a matching reference image, REPRODUCE that reference EXACTLY. For panels without a direct reference, use ALL provided references to maintain garment consistency."""

        # Build DYNAMIC 6-panel descriptions based on what was uploaded
        panel_descriptions = self._build_dynamic_panels(uploaded_image_info or [], garment_type=garment_type)
        pose_list = "\n".join(
            f"  Panel {i+1} (Row {i//2 + 1}, {'Left' if i%2==0 else 'Right'}): {desc}"
            for i, desc in enumerate(panel_descriptions)
        )

        # Build design checklist section
        design_checklist = ""
        if garment_design_details:
            design_checklist = f"""

🔍 DESIGN REPRODUCTION CHECKLIST (from AI analysis of reference photos):
The following elements were identified on the garment. You MUST reproduce EVERY item on this list:
{garment_design_details}

⚠️ VERIFY: Before finalizing the image, cross-check EACH element above against the reference photo(s). If any text, logo, stripe, or graphic is missing or wrong — fix it. The checklist above is your blueprint."""

        full_prompt = f"""{image_context} The reference photo(s) may be low-resolution, poorly lit, taken on a phone, on a hanger, hand-held, or on a flat surface — that is normal. Your job is to STUDY the garment carefully from ALL provided reference images and generate a HIGH-QUALITY fashion lookbook image.

Generate a single image containing a 2-column × 3-row grid (6 panels total) of a young Indian woman model wearing THIS EXACT GARMENT.

IMPORTANT PANEL LAYOUT:
- Panels 1-5: MODEL wearing the garment in various poses and camera framings (see panel descriptions below for each).
- Panel 6 (Row 3, Right): 3D PRODUCT SHOT — FRONT + BACK of garment FLOATING IN MID-AIR (invisible mannequin — mannequin must NOT be visible). LEFT HALF = FRONT VIEW, RIGHT HALF = BACK VIEW. NO model/person, NO visible mannequin body. Clean white background, premium e-commerce product photography.

⚠️ GARMENT FIDELITY — THIS IS THE ABSOLUTE #1 PRIORITY:
- The reference photos are LOW QUALITY but the garment details are real. Study ALL of them carefully:
  • If MULTIPLE reference images are provided, they show DIFFERENT ANGLES of the SAME garment (front, back, detail). Use ALL angles to reconstruct the complete garment faithfully.
  • The BACK VIEW reference (if provided) must be accurately reproduced in the back-facing panel (Panel 2). Match the back design, print, pattern, closure, and detailing EXACTLY as shown in the back reference photo.

📝 TEXT REPRODUCTION RULES:
  • Read EVERY word, letter, and number printed on the garment from the reference photos
  • Reproduce text with EXACT spelling — letter by letter (e.g., if it says "LeopolD" with capital L and D, write exactly "LeopolD", not "Leopold" or "LEOPOLD")
  • Match the EXACT font style (gothic/old-english, serif, sans-serif, script, block letters)
  • Match text SIZE, POSITION, and COLOR exactly as shown in the reference
  • If there are multiple text elements, place each one in the exact same position relative to the garment

🎨 LOGO & GRAPHIC REPRODUCTION RULES:
  • Reproduce EVERY logo, icon, emblem, badge, crest, and graphic element visible in the reference
  • Match the EXACT shape, size, color, and position of each element
  • Include ALL small details: stars, clovers, circles, numbers on sleeves, decorative elements below/above text
  • If an element has internal detail (e.g., a circular badge with a star inside), reproduce that internal detail too

📐 PATTERN & STRIPE REPRODUCTION RULES:
  • Match the EXACT stripe pattern: count, width, spacing, colors, direction (vertical/horizontal/diagonal)
  • Stripes must run the full length as shown in the reference — don't shorten or move them
  • Pattern colors must match exactly — if stripes are dark burgundy on red, don't make them black on red

👕 GARMENT STRUCTURE RULES:
  • Match the EXACT collar type and color (e.g., white polo collar vs. crew neck)
  • Match sleeve type, length, and any details on sleeves (numbers, stripes, patches)
  • Match garment length/crop, fit (loose/fitted), and hemline exactly
  • Match the EXACT color/shade — don't brighten, darken, or shift hues

🚫 DO NOT:
- "Reimagine", "enhance", "simplify", or "interpret" ANY design element
- Skip small logos or icons because they seem unimportant
- Change font styles, make text more "readable", or "clean up" graphics
- Add design elements that don't exist in the reference
- Merge or combine separate design elements
{design_checklist}

MODEL & STYLING CONTEXT:
{model_prompt}

6-PANEL LAYOUT (2 columns × 3 rows):
{pose_list}

GRID STRUCTURE RULES:
- The output image must contain EXACTLY 6 equal panels: 2 columns × 3 rows
- NEVER generate 4 panels or a 2×2 grid — it MUST be 2 columns × 3 ROWS = 6 panels
- Row 1: Panel 1 (left) + Panel 2 (right)
- Row 2: Panel 3 (left) + Panel 4 (right)
- Row 3: Panel 5 (left) + Panel 6 (right)
- Panels separated by straight, clean WHITE divider lines (4-6 pixels wide)
- 1 vertical divider down the center + 2 horizontal dividers splitting into 3 rows
- ALL panels must be EQUAL SIZE — each panel is exactly 1/6th of the total image
- Panels 1-4: SAME model in all 4 panels (same face, hair, skin tone, body)
- Panel 5: SAME model, walking/movement pose
- Panel 6: 3D product shot — FRONT + BACK of garment FLOATING (invisible mannequin — NOT visible), NO person
- Model FULLY VISIBLE in each model panel — no cropping at edges

PHOTOGRAPHY RULES:
- Professional HIGH-QUALITY editorial fashion photography
- Natural, warm lighting — the output should look like a premium lookbook
- Clean, simple backgrounds (not distracting)
- NO text, watermarks, labels, or panel numbers anywhere on the image
- Despite the low-quality reference input, the OUTPUT must be crisp, sharp, and professional"""

        if extra_prompt:
            full_prompt += f"\n\nADDITIONAL STYLING NOTES: {extra_prompt}"

        _log(f"Prompt length: {len(full_prompt)} chars")

        # Store image info for use in sub-methods
        self._uploaded_image_info = uploaded_image_info

        # ----------------------------------------------------------------
        # ATTEMPT A: OpenAI Responses API (gpt-4.1-mini + image_generation tool)
        # ----------------------------------------------------------------
        _log("--- Attempting: Responses API (gpt-4.1-mini + image_generation tool) ---")
        result = self._try_responses_api(client, garment_b64_list, full_prompt, quality)
        if result:
            return result

        # ----------------------------------------------------------------
        # ATTEMPT B: images.edit() with gpt-image-1 (composite reference)
        # ----------------------------------------------------------------
        _log("--- Responses API failed. Trying images.edit() ---")
        result = self._try_images_edit(client, garment_images, full_prompt, quality)
        if result:
            return result

        # ----------------------------------------------------------------
        # ATTEMPT C: images.generate() — no reference image but still works
        # ----------------------------------------------------------------
        _log("--- images.edit() failed. Trying images.generate() ---")
        result = self._try_images_generate(client, full_prompt, quality)
        if result:
            return result

        _log("ALL image generation methods failed — returning None")
        return None

    # Models to try in order for Responses API (cascade)
    _RESPONSES_MODELS = ["gpt-4.1-mini", "gpt-4o-mini", "gpt-4o"]

    def _try_responses_api(self, client, garment_b64_list: list[str], full_prompt: str, quality: str) -> bytes | None:
        """Try image generation via Responses API with model cascade. Sends ALL reference images."""
        import traceback as _tb

        uploaded_image_info = getattr(self, '_uploaded_image_info', None) or []

        # Check that Responses API is available in this SDK version
        if not hasattr(client, "responses"):
            _log("Responses API not available in this SDK version — skipping")
            return None

        # Build content array with ALL reference images, each preceded by its label
        content_items = []
        for idx, b64 in enumerate(garment_b64_list):
            # Get label from uploaded_image_info if available
            if uploaded_image_info and idx < len(uploaded_image_info):
                shows = uploaded_image_info[idx].get("shows", "unknown").upper()
                details = uploaded_image_info[idx].get("details", "")
                label = f"{shows} view"
                # Add text label before each image so the AI knows what it's looking at
                content_items.append({
                    "type": "input_text",
                    "text": f"[IMAGE {idx+1} — {shows} VIEW: {details}]",
                })
            else:
                fallback_labels = ["FRONT", "BACK", "DETAIL"]
                label = f"{fallback_labels[idx] if idx < len(fallback_labels) else 'REFERENCE'} view"
            content_items.append({
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{b64}",
            })
            _log(f"  Added reference image {idx+1}/{len(garment_b64_list)}: {label}")
        # Add text prompt last
        content_items.append({
            "type": "input_text",
            "text": full_prompt,
        })

        for model_name in self._RESPONSES_MODELS:
            try:
                _log(f"Responses API — trying model: {model_name}...")

                response = client.responses.create(
                    model=model_name,
                    input=[
                        {
                            "role": "user",
                            "content": content_items,
                        }
                    ],
                    tools=[
                        {
                            "type": "image_generation",
                            "quality": quality,
                            "size": "1024x1536",
                        }
                    ],
                )

                image_data = [
                    output.result
                    for output in response.output
                    if output.type == "image_generation_call"
                ]

                if image_data and image_data[0]:
                    img_bytes = base64.b64decode(image_data[0])
                    _log(f"Responses API SUCCESS — model={model_name}, {len(img_bytes):,} bytes, quality={quality}")
                    return img_bytes

                _log(f"Responses API ({model_name}): No image_generation_call in output. Types: {[o.type for o in response.output]}")

            except Exception as e:
                _log(f"Responses API ({model_name}) FAILED")
                _log(f"  Exception type: {type(e).__name__}")
                _log(f"  Exception message: {e}")

                err_str = str(e).lower()
                # If it's a permission/verification error, skip to next model immediately
                if "verified" in err_str or "permission" in err_str or "403" in err_str:
                    _log(f"  Org not verified for {model_name} — trying next model...")
                    continue
                if "rate_limit" in err_str or "429" in err_str:
                    _log("  Rate limited — waiting 15s...")
                    time.sleep(15)
                    continue
                # For other errors, log traceback and try next model
                _log(f"  Full traceback:\n{_tb.format_exc()}")
                continue

        _log("Responses API: all models exhausted")
        return None

    def _build_composite_reference(self, garment_images: list[bytes]) -> bytes:
        """
        Stitch multiple garment photos into a single side-by-side composite image
        with AI-detected labels. This lets images.edit() (which only accepts 1 image)
        see ALL reference views.
        """
        from PIL import Image, ImageDraw, ImageFont

        uploaded_image_info = getattr(self, '_uploaded_image_info', None) or []

        imgs = []
        for raw in garment_images:
            img = Image.open(io.BytesIO(raw))
            if img.mode != "RGB":
                img = img.convert("RGB")
            imgs.append(img)

        if len(imgs) == 1:
            buf = io.BytesIO()
            imgs[0].save(buf, format="PNG")
            return buf.getvalue()

        # Normalize all to same height
        target_h = max(img.size[1] for img in imgs)
        resized = []
        for img in imgs:
            w, h = img.size
            if h != target_h:
                ratio = target_h / h
                img = img.resize((int(w * ratio), target_h), Image.LANCZOS)
            resized.append(img)

        # Stitch side by side with 20px gap + labels
        gap = 20
        label_h = 40
        total_w = sum(img.size[0] for img in resized) + gap * (len(resized) - 1)
        total_h = target_h + label_h
        canvas = Image.new("RGB", (total_w, total_h), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        # Use AI-detected labels when available
        fallback_labels = ["FRONT", "BACK", "DETAIL"]
        x_offset = 0
        for idx, img in enumerate(resized):
            canvas.paste(img, (x_offset, label_h))
            if idx < len(uploaded_image_info):
                label = f"IMAGE {idx+1}: {uploaded_image_info[idx].get('shows', 'unknown').upper()}"
            else:
                label = fallback_labels[idx] if idx < len(fallback_labels) else f"VIEW {idx+1}"
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
            except Exception:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), label, font=font)
            tw = bbox[2] - bbox[0]
            tx = x_offset + (img.size[0] - tw) // 2
            draw.text((tx, 8), label, fill=(0, 0, 0), font=font)
            x_offset += img.size[0] + gap

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        _log(f"Composite reference: {len(resized)} images → {total_w}×{total_h}px, labels: {[uploaded_image_info[i].get('shows', '?') if i < len(uploaded_image_info) else '?' for i in range(len(resized))]}")
        return buf.getvalue()

    def _try_images_edit(self, client, garment_images: list[bytes], full_prompt: str, quality: str) -> bytes | None:
        """Try image generation via client.images.edit() — stable fallback. Composites multiple images."""
        import traceback as _tb

        # Build composite reference if multiple images
        composite_bytes = self._build_composite_reference(garment_images)

        # images.edit() does NOT support 'quality' or 'response_format' params
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                _log(f"images.edit() attempt {attempt}/{max_retries}...")
                garment_io = io.BytesIO(composite_bytes)
                garment_io.name = "garment.png"

                response = client.images.edit(
                    model="gpt-image-1",
                    image=garment_io,
                    prompt=full_prompt,
                    n=1,
                    size="1024x1536",
                )

                if response.data and len(response.data) > 0:
                    item = response.data[0]
                    if hasattr(item, "b64_json") and item.b64_json:
                        img_bytes = base64.b64decode(item.b64_json)
                        _log(f"images.edit() SUCCESS — {len(img_bytes):,} bytes")
                        return img_bytes
                    elif hasattr(item, "url") and item.url:
                        import httpx
                        _log(f"images.edit() returned URL — downloading...")
                        resp = httpx.get(item.url, timeout=60)
                        resp.raise_for_status()
                        img_bytes = resp.content
                        _log(f"images.edit() URL download SUCCESS — {len(img_bytes):,} bytes")
                        return img_bytes

                _log(f"images.edit() attempt {attempt}: No image data in response")

            except Exception as e:
                _log(f"images.edit() attempt {attempt} FAILED")
                _log(f"  Exception type: {type(e).__name__}")
                _log(f"  Exception message: {e}")
                _log(f"  Full traceback:\n{_tb.format_exc()}")

                err_str = str(e).lower()
                if "rate_limit" in err_str or "429" in err_str:
                    if attempt < max_retries:
                        _log("  Rate limited — waiting 15s...")
                        time.sleep(15)
                elif attempt < max_retries:
                    time.sleep(3)

        return None

    def _try_images_generate(self, client, full_prompt: str, quality: str) -> bytes | None:
        """Last resort: images.generate() — no reference image but supports quality."""
        import traceback as _tb

        try:
            _log(f"images.generate() — quality={quality}...")

            response = client.images.generate(
                model="gpt-image-1",
                prompt=full_prompt,
                n=1,
                size="1024x1536",
                quality=quality,
            )

            if response.data and len(response.data) > 0:
                item = response.data[0]
                if hasattr(item, "b64_json") and item.b64_json:
                    img_bytes = base64.b64decode(item.b64_json)
                    _log(f"images.generate() SUCCESS — {len(img_bytes):,} bytes, quality={quality}")
                    return img_bytes
                elif hasattr(item, "url") and item.url:
                    import httpx
                    _log("images.generate() returned URL — downloading...")
                    resp = httpx.get(item.url, timeout=60)
                    resp.raise_for_status()
                    img_bytes = resp.content
                    _log(f"images.generate() URL download SUCCESS — {len(img_bytes):,} bytes")
                    return img_bytes

            _log("images.generate(): No image data in response")

        except Exception as e:
            _log(f"images.generate() FAILED")
            _log(f"  Exception type: {type(e).__name__}")
            _log(f"  Exception message: {e}")
            _log(f"  Full traceback:\n{_tb.format_exc()}")

        return None


# ---------------------------------------------------------------------------
# Google Gemini Image Provider (Nano Banana)
# ---------------------------------------------------------------------------

class GeminiImageProvider(ImageProvider):
    """
    Generate fashion model grid using Google Gemini API (Nano Banana).

    Models (cascade):
      - gemini-2.5-flash-image     (cost-efficient, fast, native multimodal)
      - gemini-3.1-flash-image-preview  (better fidelity + 2K/4K, higher cost)

    Key advantages for fashion:
      - Native multimodal: same brain processes images + text → deeper understanding
      - Up to 14 reference images with high-fidelity preservation
      - Better pattern/fabric/design reproduction than OpenAI image gen
      - Single API call, no fallback chains needed
      - Strong Indian fashion understanding (Google's training data)
    """

    _MODELS = ["gemini-2.5-flash-image", "gemini-3.1-flash-image-preview"]

    def generate_pose_grid(
        self,
        garment_images: list[bytes],
        model_prompt: str,
        quality: str = "medium",
        extra_prompt: str = "",
        garment_design_details: str = "",
        uploaded_image_info: list[dict] = None,
        garment_type: str = "",
    ) -> bytes | None:
        from google import genai
        from google.genai import types
        from PIL import Image
        import traceback as _tb

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            _log("ERROR: GEMINI_API_KEY environment variable is not set!")
            return None

        client = genai.Client(api_key=api_key)
        num_images = len(garment_images)
        quality = (quality or "low").lower()
        if quality not in ("low", "medium", "high"):
            quality = "low"

        _log(f"Gemini provider: {num_images} reference images, quality={quality}")

        # ---- Resize garment images to max 1024px long edge before sending ----
        # Prevents OOM: 3024x4032px images at 512MB memory will crash the container
        MAX_LONG_EDGE = 1024
        pil_images = []
        for i, raw in enumerate(garment_images):
            img = Image.open(io.BytesIO(raw))
            if img.mode != "RGB":
                img = img.convert("RGB")
            w, h = img.size
            long_edge = max(w, h)
            if long_edge > MAX_LONG_EDGE:
                scale = MAX_LONG_EDGE / long_edge
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
                _log(f"  Resized image {i+1}: {w}x{h} → {img.size[0]}x{img.size[1]}px")
            pil_images.append(img)

        # ---- Build image labels from AI detection (or fallback) ----
        img_labels = []
        if uploaded_image_info and len(uploaded_image_info) >= num_images:
            for info in uploaded_image_info[:num_images]:
                img_labels.append((info.get("shows", "unknown"), info.get("details", "")))
        else:
            fallback = ["front", "back", "detail"]
            for i in range(num_images):
                img_labels.append((fallback[i] if i < len(fallback) else "other", ""))
        _log(f"Image labels: {[lbl[0] for lbl in img_labels]}")

        # ---- Build image context ----
        for i, img in enumerate(pil_images):
            show_type = img_labels[i][0] if i < len(img_labels) else "unknown"
            _log(f"  Reference {i+1}: {show_type} view, {img.size[0]}x{img.size[1]}px")
        if num_images == 1:
            image_context = f"You are given 1 REFERENCE PHOTO of the garment (IMAGE 1 = {img_labels[0][0].upper()} view)."
        else:
            views_desc = [f"IMAGE {i+1} = {s.upper()} view" + (f" ({d})" if d else "") for i, (s, d) in enumerate(img_labels)]
            image_context = f"""You are given {num_images} REFERENCE PHOTOS of the SAME garment/outfit:
{'; '.join(views_desc)}
STUDY EACH reference photo carefully. Each shows a SPECIFIC angle or component.
For panels with a matching reference, REPRODUCE that reference EXACTLY.
For panels without a direct reference, use ALL references for consistency."""

        # ---- Build dynamic 6-panel descriptions ----
        panel_descriptions = OpenAIImageProvider._build_dynamic_panels(uploaded_image_info or [], garment_type=garment_type)
        pose_list = "\n".join(
            f"  Panel {i+1} (Row {i//2 + 1}, {'Left' if i%2==0 else 'Right'}): {desc}"
            for i, desc in enumerate(panel_descriptions)
        )

        # ---- Design reproduction checklist ----
        design_checklist = ""
        if garment_design_details:
            design_checklist = f"""\n\n🔍 DESIGN REPRODUCTION CHECKLIST (from AI analysis of reference photos):
{garment_design_details}\n⚠️ VERIFY: Cross-check EACH element above against the reference photos. Every text, logo, stripe, graphic MUST match exactly."""

        # ---- Build full prompt ----
        full_prompt = f"""{image_context} The reference photos may be low-quality, phone photos, on hangers, hand-held, or flat-lay — that is normal. STUDY the garment from ALL references and generate HIGH-QUALITY fashion lookbook output.

Generate a single image containing a 2-column × 3-row grid (6 panels total) of a young Indian woman model wearing THIS EXACT GARMENT.

IMPORTANT PANEL LAYOUT:
- Panels 1-5: MODEL wearing the garment in various poses and camera framings (see panel descriptions below for each).
- Panel 6 (Row 3, Right): 3D PRODUCT SHOT — FRONT + BACK of garment FLOATING IN MID-AIR (invisible mannequin — mannequin must NOT be visible). LEFT HALF = FRONT VIEW, RIGHT HALF = BACK VIEW. NO model/person, NO visible mannequin body. Clean white background, premium e-commerce product photography.

⚠️ GARMENT FIDELITY — THIS IS THE ABSOLUTE #1 PRIORITY:
- The garment in EVERY panel must be a PIXEL-PERFECT reproduction of the reference photos
- Study ALL reference angles to capture every design element from every angle
- If BACK view reference is provided, Panel 2 MUST match it exactly
- If MULTIPLE references are provided, they show DIFFERENT ANGLES of the SAME garment

📝 TEXT REPRODUCTION RULES:
  • Read EVERY word, letter, and number printed on the garment from the reference photos
  • Reproduce text with EXACT spelling — letter by letter
  • Match the EXACT font style (gothic/old-english, serif, sans-serif, script, block letters)
  • Match text SIZE, POSITION, and COLOR exactly as shown in the reference

🎨 LOGO & GRAPHIC REPRODUCTION RULES:
  • Reproduce EVERY logo, icon, emblem, badge, crest, and graphic element visible in the reference
  • Match the EXACT shape, size, color, and position of each element
  • Include ALL small details: stars, clovers, circles, numbers on sleeves, decorative elements

📐 PATTERN & STRIPE REPRODUCTION RULES:
  • Match the EXACT stripe/print pattern: count, width, spacing, colors, direction
  • Pattern colors must match exactly — don't shift hues, brighten, or darken
  • Lace patterns, embroidery, weave texture must be reproduced faithfully

👕 GARMENT STRUCTURE RULES:
  • Match the EXACT collar type, neckline shape, and sleeve type/length
  • Match garment length/crop, fit (loose/fitted/sheer), and hemline exactly
  • Match the EXACT color/shade — don't brighten, darken, or shift hues
  • For sheer/transparent fabrics, maintain the exact level of transparency

🚫 DO NOT:
- "Reimagine", "enhance", "simplify", or "interpret" ANY design element
- Skip small logos or icons because they seem unimportant
- Change font styles, make text more "readable", or "clean up" graphics
- Add design elements that don't exist in the reference
{design_checklist}

MODEL & STYLING CONTEXT:
{model_prompt}

6-PANEL LAYOUT (2 columns × 3 rows):
{pose_list}

GRID STRUCTURE RULES:
- Output image: EXACTLY 6 equal panels, 2 columns × 3 rows
- NEVER generate 4 panels or a 2×2 grid — it MUST be 2 columns × 3 ROWS = 6 panels
- Row 1: Panel 1 (left) + Panel 2 (right)
- Row 2: Panel 3 (left) + Panel 4 (right)
- Row 3: Panel 5 (left) + Panel 6 (right)
- Clean WHITE divider lines (4-6px wide) separating panels
- 1 vertical divider + 2 horizontal dividers
- ALL panels EQUAL SIZE — each panel is exactly 1/6th of the total image
- Panels 1-4: SAME model in all 4 panels (same face, hair, skin tone, body)
- Panel 5: SAME model, walking/movement pose
- Panel 6: 3D product shot — FRONT + BACK of garment FLOATING (invisible mannequin — NOT visible), NO person
- Model FULLY VISIBLE in each model panel — no cropping at edges

PHOTOGRAPHY RULES:
- Professional HIGH-QUALITY editorial fashion photography
- Natural, warm lighting — premium lookbook quality
- Clean, simple backgrounds (not distracting)
- NO text, watermarks, labels, or panel numbers on the image
- Output must be crisp, sharp, and professional regardless of input quality"""

        if extra_prompt:
            full_prompt += f"\n\nADDITIONAL STYLING NOTES: {extra_prompt}"

        _log(f"Prompt length: {len(full_prompt)} chars")

        # ---- Quality → resolution mapping ----
        quality_to_size = {"low": "512px", "medium": "1K", "high": "2K"}
        image_size = quality_to_size.get(quality, "1K")

        # ---- Build contents: interleave [label + image] + final prompt ----
        contents = []
        for i, pil_img in enumerate(pil_images):
            shows = img_labels[i][0].upper() if i < len(img_labels) else "REFERENCE"
            details = img_labels[i][1] if i < len(img_labels) else ""
            contents.append(f"[IMAGE {i+1} — {shows} VIEW: {details}]")
            contents.append(pil_img)
        contents.append(full_prompt)

        # ---- Helper: check if returned image is 2×2 instead of 2×3 ----
        def _is_2x2_grid(img_bytes: bytes) -> bool:
            """Quick check: count horizontal dividers. If only 1, it's 2×2."""
            try:
                from services.image_utils import _count_real_dividers
                check_img = Image.open(io.BytesIO(img_bytes))
                if check_img.mode != "RGB":
                    check_img = check_img.convert("RGB")
                h_divs = _count_real_dividers(check_img, "horizontal")
                _log(f"Grid check: {h_divs} horizontal dividers → {'2×2' if h_divs < 2 else '2×3'}")
                return h_divs < 2
            except Exception:
                return False

        # ---- Try each model in cascade ----
        for model_name in self._MODELS:
            try:
                _log(f"Gemini: trying {model_name} (size={image_size})...")

                # image_size only supported on Gemini 3.x models
                img_cfg_kwargs = {"aspect_ratio": "2:3"}
                if "3" in model_name:
                    img_cfg_kwargs["image_size"] = image_size

                config = types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    image_config=types.ImageConfig(**img_cfg_kwargs),
                )

                # Allow up to 3 attempts per model (retry if 2×2 detected)
                for attempt in range(3):
                    attempt_contents = contents
                    if attempt > 0:
                        _log(f"Gemini ({model_name}): RETRY #{attempt} — got 2×2 grid, re-emphasizing 3 ROWS")
                        retry_suffix = (f"\n\n⚠️ CRITICAL (attempt {attempt+1}): Your previous output had only 4 panels (2×2). "
                                        "You MUST generate EXACTLY 6 panels arranged in 2 columns × 3 ROWS. "
                                        "Row 1: Panel 1 + Panel 2. Row 2: Panel 3 + Panel 4. Row 3: Panel 5 + Panel 6. "
                                        "That is 3 ROWS of 2 panels each = 6 panels total. "
                                        "Do NOT generate a 2×2 grid. NEVER only 4 panels.")
                        attempt_contents = contents[:-1] + [contents[-1] + retry_suffix]

                    response = client.models.generate_content(
                        model=model_name,
                        contents=attempt_contents,
                        config=config,
                    )

                    # Extract image from response (skip thinking/thought images)
                    img_bytes = None
                    for part in response.parts:
                        if hasattr(part, "thought") and part.thought:
                            continue
                        if part.inline_data is not None:
                            mime = getattr(part.inline_data, "mime_type", "") or ""
                            if not mime.startswith("image/"):
                                continue
                            img_bytes = part.inline_data.data
                            if isinstance(img_bytes, str):
                                img_bytes = base64.b64decode(img_bytes)
                            break

                    if img_bytes is None:
                        _log(f"Gemini ({model_name}): no image in response (attempt {attempt+1})")
                        break

                    _log(f"Gemini ({model_name}): got {len(img_bytes):,} bytes (attempt {attempt+1})")

                    # Check if it's 2×2 — retry with stronger prompt
                    if attempt < 2 and _is_2x2_grid(img_bytes):
                        continue  # retry with stronger prompt

                    # Either it's 2×3, or it's retry attempt — accept whatever we got
                    _log(f"Gemini SUCCESS — model={model_name}, {len(img_bytes):,} bytes")
                    return img_bytes

                # If we exhausted retries for this model, the last img_bytes is still usable
                if img_bytes is not None:
                    _log(f"Gemini ({model_name}): accepting 2×2 grid after retry failed")
                    return img_bytes

            except Exception as e:
                _log(f"Gemini ({model_name}) FAILED: {type(e).__name__}: {e}")
                _log(f"  Traceback:\n{_tb.format_exc()}")
                err_str = str(e).lower()
                if "rate_limit" in err_str or "429" in err_str:
                    _log("  Rate limited — waiting 15s...")
                    time.sleep(15)
                continue

        _log("Gemini: all models exhausted — returning None (OpenAI fallback disabled)")
        return None

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # TRYON — Progressive 2-Phase Approach (COST: 2 × $0 = $0)
    # ------------------------------------------------------------------
    # Phase 1 (fast): generate_tryon_single()
    #   - Single inpainting edit: preserve real face/body/pose
    #   - Change ONLY the clothing + enhance background/styling/accessories
    #   - Returns 1 image (bytes) shown immediately → ~10-15s
    #
    # Phase 2 (background): generate_tryon_grid()
    #   - Fictional model grid (similar appearance, NOT face-cloned)
    #   - Full product-grid-style styling (accessories, bottom wear, editorial)
    #   - Returns grid bytes → crop_pose_grid → 5-6 panels appended to slideshow
    #
    # Per COST_RULES.md: 2 parallel calls, both Gemini free tier, $0 total.
    # ------------------------------------------------------------------

    _TRYON_MODELS = ["gemini-3.1-flash-image-preview", "gemini-2.5-flash-image"]

    # ==========  PHASE 1: Real-face inpainting edit  ==========

    def generate_tryon_single(
        self,
        person_image: bytes,
        garment_images: list[bytes],
        garment_briefs: list[str],
        garment_categories: list[str],
        garment_3d_images: list[bytes | None] = None,
        quality: str = "medium",
    ) -> bytes | None:
        """
        Single-image inpainting: change ONLY the clothing on the customer's
        real photo while preserving face, hair, body, and pose exactly.
        Also enhances background to editorial quality and adds complementary
        accessories (shoes, jewelry, bag) based on garment category.

        Returns: bytes (single JPEG image) or None on failure.
        """
        from google import genai
        from google.genai import types
        from PIL import Image
        import traceback as _tb

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            _log("ERROR: GEMINI_API_KEY not set")
            return None

        client = genai.Client(api_key=api_key)
        quality = (quality or "medium").lower()
        if quality not in ("low", "medium", "high"):
            quality = "medium"

        _log(f"Tryon FAST (inpainting): {len(garment_images)} garment(s), quality={quality}")

        # ---- Resize images ----
        def _resize(raw: bytes, max_edge: int = 1024) -> Image.Image:
            img = Image.open(io.BytesIO(raw))
            if img.mode != "RGB":
                img = img.convert("RGB")
            w, h = img.size
            if max(w, h) > max_edge:
                s = max_edge / max(w, h)
                img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
            return img

        person_pil = _resize(person_image, 1024)
        garment_pils = [_resize(g, 768) for g in garment_images]

        # Resize 3D garment images (clean garment references) if available
        garment_3d_pils = []
        if garment_3d_images:
            for g3d in garment_3d_images:
                if g3d is not None:
                    garment_3d_pils.append(_resize(g3d, 768))
                else:
                    garment_3d_pils.append(None)
        has_3d = any(g is not None for g in garment_3d_pils)

        # ---- Build outfit description with slots ----
        outfit_parts = []
        # Track categories for layering detection
        cat_counts = {}
        for i, brief in enumerate(garment_briefs):
            cat = garment_categories[i] if i < len(garment_categories) else "garment"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        upper_idx = 0  # track layering order within same category
        for i, brief in enumerate(garment_briefs):
            cat = garment_categories[i] if i < len(garment_categories) else "garment"
            slot = {"upper_body": "on upper body", "lower_body": "on lower body",
                    "full_body": "as complete outfit"}.get(cat, "")
            # Add layering context when multiple garments share a category
            if cat_counts.get(cat, 0) > 1 and cat in ("upper_body", "full_body"):
                # First garment = base layer, subsequent = outer layer
                layer_items = [j for j in range(i+1) if (garment_categories[j] if j < len(garment_categories) else "") == cat]
                if len(layer_items) <= 1:
                    slot += " — base layer"
                else:
                    slot += " — outer layer, worn OVER the previous"
            # Handle full_body + upper_body combo (jacket over dress)
            if cat == "upper_body" and "full_body" in cat_counts:
                slot = "layered OVER the full outfit"
            outfit_parts.append(f"- {brief} ({slot})" if slot else f"- {brief}")
        outfit_desc = "\n".join(outfit_parts)

        # ---- Build complementary accessories based on garment categories ----
        cats = set(garment_categories)
        accessory_instructions = ""
        if "full_body" in cats and "upper_body" in cats:
            # Full outfit + top layering (e.g., dress + jacket)
            accessory_instructions = """COMPLETE THE LOOK with:
- The top/jacket MUST be worn visibly OVER the full outfit — both garments fully visible
- Matching footwear appropriate to the combined outfit style
- Minimal accessories — the outfit combination is the star
- The layered top should look naturally styled over the base outfit"""
        elif "full_body" in cats:
            accessory_instructions = """COMPLETE THE LOOK with:
- Matching footwear (heels, block heels, or ethnic juttis depending on outfit style)
- A small elegant bag or clutch that complements the outfit
- Dainty earrings or studs that match the outfit's vibe
- Keep accessories subtle — the garment is the star"""
        elif "upper_body" in cats and "lower_body" in cats:
            # Top + bottom combo (possibly with layered tops)
            multi_tops = sum(1 for c in garment_categories if c == "upper_body") > 1
            if multi_tops:
                accessory_instructions = """COMPLETE THE LOOK with:
- ALL tops MUST be visible — layer them naturally (inner shirt/base visible, outer jacket/cardigan on top)
- Matching footwear and minimal accessories
- The layered look should feel intentional and styled"""
            else:
                accessory_instructions = """COMPLETE THE LOOK with matching footwear and minimal accessories."""
        elif "upper_body" in cats and "lower_body" not in cats:
            accessory_instructions = """COMPLETE THE LOOK with:
- Stylish complementary bottom wear that suits the top's aesthetic
- Matching footwear (heels, sneakers, or ethnic shoes based on style)
- Dainty jewelry (layered necklace, small earrings)
- The bottom wear + accessories should enhance but not overpower the garment"""
        elif "lower_body" in cats and "upper_body" not in cats:
            accessory_instructions = """COMPLETE THE LOOK with:
- A complementary top that matches the bottom's style
- Matching footwear and minimal accessories"""
        else:
            accessory_instructions = """COMPLETE THE LOOK with matching footwear and minimal accessories."""

        # ---- Build inpainting prompt ----
        prompt = f"""Using the provided photo of this person, change ONLY their clothing to the garment(s) shown in the product photo(s).

CLOTHING TO APPLY:
{outfit_desc}

ABSOLUTE PRESERVATION RULES (do NOT change ANY of these):
- The person's EXACT face — every single feature: eyes, nose, mouth, jawline, skin tone, expression, facial hair
- Hair — exact color, style, length, texture, parting
- Body — exact shape, proportions, skin color, pose, hand position
- The person's exact pose and body angle — do NOT repose them

GARMENT APPLICATION:
- Study the product photo(s) carefully for exact: color, pattern, print, logo, text, fit, silhouette, fabric texture
- Dress the garment naturally onto this person's body, respecting their pose
- The garment must look like the ACTUAL product, not a reimagined version

{accessory_instructions}

BACKGROUND & LIGHTING UPGRADE:
- Replace the background with a clean, professional fashion editorial setting
- Use warm, flattering studio lighting or soft natural light
- Settings: clean studio, sunlit café patio, boutique interior, or urban street — pick what suits the outfit
- The overall image should look like a premium fashion lookbook photo
- Keep the person as the clear focal point

OUTPUT: Generate a SINGLE high-quality fashion editorial photo of this person.
- Full body visible, head to toe
- Professional fashion photography quality
- NO text, NO watermarks"""

        _log(f"Tryon FAST prompt: {len(prompt)} chars")

        # ---- Quality → resolution ----
        quality_to_size = {"low": "1K", "medium": "2K", "high": "2K"}
        image_size = quality_to_size.get(quality, "2K")

        # ---- Contents: person photo FIRST (image to edit), then garments, then prompt ----
        contents = [person_pil]
        for i, g_pil in enumerate(garment_pils):
            brief = garment_briefs[i] if i < len(garment_briefs) else "Fashion garment"
            cat = garment_categories[i] if i < len(garment_categories) else "garment"

            if has_3d and i < len(garment_3d_pils) and garment_3d_pils[i] is not None:
                # Use clean garment reference (no AI model face)
                contents.append(f"[GARMENT {i+1} — REAL GARMENT PHOTO: {brief} — Actual garment with NO model. Wear this {cat.replace('_', ' ')}]")
                contents.append(garment_3d_pils[i])
                _log(f"Garment {i+1}: using CLEAN garment photo (3D) — face swap prevention")
            else:
                # Crop top 25% of hero to reduce face contamination
                try:
                    w, h = g_pil.size
                    crop_top = int(h * 0.25)
                    cropped = g_pil.crop((0, crop_top, w, h))
                    contents.append(f"[GARMENT {i+1} — PRODUCT PHOTO (cropped): {brief} — IGNORE any person, study ONLY the garment. Wear this {cat.replace('_', ' ')}]")
                    contents.append(cropped)
                    _log(f"Garment {i+1}: using CROPPED product photo (top 25% removed)")
                except Exception:
                    contents.append(g_pil)
                    _log(f"Garment {i+1}: using full product photo (crop failed)")
        contents.append(prompt)

        # ---- Try each model ----
        for model_name in self._TRYON_MODELS:
            try:
                _log(f"Tryon FAST: trying {model_name} (size={image_size})...")

                img_cfg_kwargs = {"aspect_ratio": "3:4"}
                cfg_kwargs = {
                    "response_modalities": ["TEXT", "IMAGE"],
                    "image_config": types.ImageConfig(**img_cfg_kwargs),
                }

                if "3" in model_name:
                    img_cfg_kwargs["image_size"] = image_size
                    cfg_kwargs["image_config"] = types.ImageConfig(**img_cfg_kwargs)
                    cfg_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_level="High",
                    )

                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(**cfg_kwargs),
                )

                for part in response.parts:
                    if hasattr(part, "thought") and part.thought:
                        continue
                    if part.inline_data is not None:
                        mime = getattr(part.inline_data, "mime_type", "") or ""
                        if not mime.startswith("image/"):
                            continue
                        img_bytes = part.inline_data.data
                        if isinstance(img_bytes, str):
                            img_bytes = base64.b64decode(img_bytes)
                        _log(f"Tryon FAST SUCCESS — model={model_name}, {len(img_bytes):,} bytes")
                        return img_bytes

                _log(f"Tryon FAST ({model_name}): no images in response")

            except Exception as e:
                _log(f"Tryon FAST ({model_name}) FAILED: {type(e).__name__}: {e}")
                _log(f"  Traceback:\n{_tb.format_exc()}")
                err_str = str(e).lower()
                if "rate_limit" in err_str or "429" in err_str:
                    _log("  Rate limited — waiting 15s...")
                    time.sleep(15)
                continue

        _log("Tryon FAST: all models exhausted — returning None")
        return None

    # ==========  PHASE 2: Single grid call → mathematical crop  ==========

    def generate_tryon_grid(
        self,
        person_image: bytes,
        garment_images: list[bytes],
        garment_briefs: list[str],
        garment_categories: list[str],
        garment_design_details_list: list[str] = None,
        garment_3d_images: list[bytes | None] = None,
                tryon_mode: str = "customer_editorial",
        quality: str = "medium",
    ) -> bytes | None:
        """
                Generate a 2×3 customer-editorial try-on grid in a single Gemini call.
                This flow is intentionally customer-first:
                    - No 3D/mannequin panel
                    - No upper/lower framing specialization
                    - All 6 panels feature the uploaded customer with flattering editorial poses

        Returns: bytes (single grid image) or None on failure.
        """
        from google import genai
        from google.genai import types
        from PIL import Image
        import traceback as _tb

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            _log("ERROR: GEMINI_API_KEY not set")
            return None

        client = genai.Client(api_key=api_key)
        quality = (quality or "medium").lower()
        if quality not in ("low", "medium", "high"):
            quality = "medium"
        if not tryon_mode:
            tryon_mode = "customer_editorial"

        _log(f"Tryon GRID: {len(garment_images)} garment(s), quality={quality}, mode={tryon_mode}")

        # ---- Resize images ----
        def _resize(raw: bytes, max_edge: int = 1024) -> Image.Image:
            img = Image.open(io.BytesIO(raw))
            if img.mode != "RGB":
                img = img.convert("RGB")
            w, h = img.size
            if max(w, h) > max_edge:
                s = max_edge / max(w, h)
                img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
            return img

        person_pil = _resize(person_image, 1024)
        garment_pils = [_resize(g, 768) for g in garment_images]

        # Resize 3D mannequin images (clean garment references) if available
        garment_3d_pils = []
        if garment_3d_images:
            for g3d in garment_3d_images:
                if g3d is not None:
                    garment_3d_pils.append(_resize(g3d, 768))
                else:
                    garment_3d_pils.append(None)
        has_3d = any(g is not None for g in garment_3d_pils)

        # Dedicated customer-editorial 6 panel composition.
        panel_descriptions = [
            "Hero portrait, front-facing confidence shot, waist-up, premium beauty lighting.",
            "Soft 3/4 portrait angle, natural hand pose, face and upper body clearly visible.",
            "Lifestyle standing shot, full body, warm candid mood, premium campaign feel.",
            "Detail close-up with face visible, highlight garment texture/neckline/sleeve details.",
            "Movement shot, elegant walking pose, balanced framing, flattering silhouette.",
            "Signature editorial frame, confident final pose, high-fashion campaign quality.",
        ]
        pose_list = "\n".join(
            f"  Panel {i+1} (Row {i//2 + 1}, {'Left' if i%2==0 else 'Right'}): {desc}"
            for i, desc in enumerate(panel_descriptions)
        )

        # ---- Build outfit description ----
        outfit_parts = []
        cat_counts = {}
        for i, brief in enumerate(garment_briefs):
            cat = garment_categories[i] if i < len(garment_categories) else "garment"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        for i, brief in enumerate(garment_briefs):
            cat = garment_categories[i] if i < len(garment_categories) else "garment"
            slot = {"upper_body": "on upper body", "lower_body": "on lower body",
                    "full_body": "as complete outfit"}.get(cat, "")
            # Layering context for multiple garments in same category
            if cat_counts.get(cat, 0) > 1 and cat in ("upper_body", "full_body"):
                layer_items = [j for j in range(i+1) if (garment_categories[j] if j < len(garment_categories) else "") == cat]
                if len(layer_items) <= 1:
                    slot += " — base layer"
                else:
                    slot += " — outer layer, worn OVER the previous"
            if cat == "upper_body" and "full_body" in cat_counts:
                slot = "layered OVER the full outfit"
            outfit_parts.append(f"- {brief} ({slot})" if slot else f"- {brief}")
        outfit_desc = "\n".join(outfit_parts)

        # ---- Layering instruction (added when multiple garments overlap) ----
        layering_note = ""
        if len(garment_briefs) > 1:
            has_layering = cat_counts.get("upper_body", 0) > 1 or ("full_body" in cat_counts and "upper_body" in cat_counts)
            if has_layering:
                layering_note = """
🧥 LAYERING RULES:
- When multiple garments target the same body area, LAYER them naturally
- Inner/base garments go underneath, outer garments (jackets, cardigans) go on top
- ALL garments MUST be clearly visible in the final result — no garment should be hidden
- The layered look should feel intentional and fashion-forward"""

        # ---- Build design details section ----
        design_checklist = ""
        if garment_design_details_list:
            details_parts = []
            for i, details in enumerate(garment_design_details_list):
                if details and details.strip():
                    details_parts.append(f"Garment {i+1} details:\n{details}")
            if details_parts:
                design_checklist = f"""

🔍 DESIGN REPRODUCTION CHECKLIST (from product analysis):
{chr(10).join(details_parts)}

⚠️ VERIFY: Before finalizing, cross-check EACH element above against the garment photo(s).
Every text, logo, stripe, graphic, embroidery detail MUST match exactly."""

        # ---- Customer-first styling ----
        styling = """STYLING RULES:
- Keep the uploaded customer as the visual hero in every panel.
- Accessories should be minimal and tasteful (one focal accessory at most).
- Preserve natural skin texture and realistic beauty-retouch quality.
- Keep garment faithful while prioritizing flattering presentation for the customer.
- Avoid distracting backgrounds; use premium editorial environments only."""

        # ---- Build image context description ----
        img_refs = []
        ref_idx = 1
        for i in range(len(garment_pils)):
            if has_3d and i < len(garment_3d_pils) and garment_3d_pils[i] is not None:
                img_refs.append(f"IMAGE {ref_idx} = GARMENT {i+1} — real garment photo (the actual garment with NO model/person — this is your ONLY garment reference)")
            else:
                img_refs.append(f"IMAGE {ref_idx} = GARMENT {i+1} — product photo (cropped to garment area; IGNORE any person, study ONLY the garment)")
            ref_idx += 1
        img_refs.append(f"IMAGE {ref_idx} = CUSTOMER PHOTO (the real person — YOUR MODEL for all 6 panels)")

        if has_3d:
            image_context = f"""You are given {ref_idx} REFERENCE PHOTOS:
{chr(10).join(img_refs)}

⚠️ CRITICAL: The garment photo shows the ACTUAL garment with NO person in it.
There is NO other model to copy — the CUSTOMER PHOTO (last image) is the ONLY person.
Study the garment photo for exact garment details. Study the customer photo for exact identity.
The CUSTOMER is the ONLY face/body in your output."""
        else:
            image_context = f"""You are given {ref_idx} REFERENCE PHOTOS:
{chr(10).join(img_refs)}

⚠️ CRITICAL: The garment product photo may show a DIFFERENT person wearing the garment.
That person is NOT the customer. COMPLETELY IGNORE their face, body, skin tone, and features.
Study ONLY the garment (color, pattern, shape, details) from the product photo.
The CUSTOMER PHOTO (last image) is the ONLY person to appear in your output.
Do NOT blend, mix, or be influenced by the person in the garment photo."""

        # ---- Build prompt (proven generate_pose_grid structure + identity preservation) ----
        prompt = f"""{image_context}

Generate a single image containing a 2-column × 3-row grid (6 panels total).
The CUSTOMER from the photo above is the model — she is wearing THIS EXACT GARMENT:

GARMENT TO WEAR:
{outfit_desc}
{layering_note}
{styling}

IMPORTANT PANEL LAYOUT:
- All 6 panels must feature the same uploaded customer wearing the garment.
- There is NO 3D garment-only panel in this mode.

🧑 COMPLETE IDENTITY PRESERVATION — ABSOLUTE #1 PRIORITY:
You are PHOTOGRAPHING this REAL PERSON. She is NOT being replaced, NOT being morphed, NOT being approximated.
Every single aspect of her identity MUST be preserved EXACTLY across all 6 panels:
- FACE: Exact same eyes (shape, color, size, spacing), nose (bridge, tip, width), mouth (lip shape, fullness), jawline, chin shape, cheekbones, forehead, eyebrows, facial structure, skin texture, complexion, expression style
- HAIR: Exact same color, style, length, texture, parting, volume, fringe/bangs, highlights
- BODY: Exact same body shape, proportions, height, build (slim/curvy/athletic), shoulder width, waist-to-hip ratio, arm length, leg length
- SKIN: Exact same skin tone, color, undertone across face AND body — no brightening, no darkening, no shifting
- AGE: Same apparent age — do NOT make her look younger or older
- ETHNICITY: Preserve exactly — do NOT shift ethnic features
- Think of this as: this EXACT person walked into your studio, put on this outfit, and you photographed her 6 times
- If you cannot see her full body in the uploaded photo, INFER her proportions naturally from what IS visible and keep them consistent

⚠️ GARMENT FIDELITY — #2 PRIORITY:
Study the garment product photo(s) carefully for all design details.
The garment in EVERY panel must be a PIXEL-PERFECT reproduction of the reference photos.

📝 TEXT REPRODUCTION RULES:
  • Read EVERY word, letter, and number printed on the garment
  • Reproduce text with EXACT spelling — letter by letter
  • Match the EXACT font style, SIZE, POSITION, and COLOR

🎨 LOGO & GRAPHIC REPRODUCTION RULES:
  • Reproduce EVERY logo, icon, emblem, badge, crest, and graphic element
  • Match the EXACT shape, size, color, and position
  • Include ALL small details: stars, numbers on sleeves, decorative elements

📐 PATTERN & STRIPE REPRODUCTION RULES:
  • Match the EXACT pattern: count, width, spacing, colors, direction
  • Pattern colors must match exactly — don't shift, brighten, or darken hues
  • Lace, embroidery, weave texture must be reproduced faithfully

👕 GARMENT STRUCTURE RULES:
  • Match the EXACT collar type, neckline shape, sleeve type/length
  • Match garment length/crop, fit (loose/fitted), and hemline
  • Match the EXACT color/shade — don't brighten, darken, or change
{design_checklist}

🚫 DO NOT:
- Generate a different person who "looks similar" — it MUST be HER
- Change ANY facial feature, body proportion, skin tone, or hair
- Swap, morph, or paste the face onto a different body
- Make her slimmer, taller, or more "conventionally attractive"
- "Reimagine", "enhance", or "interpret" ANY garment design element
- Add design elements not in the garment photo
- Change text spelling, font, or positioning on the garment

6-PANEL LAYOUT (2 columns × 3 rows):
{pose_list}

GRID STRUCTURE RULES:
- Output image: EXACTLY 6 equal panels, 2 columns × 3 rows
- NEVER generate 4 panels or a 2×2 grid — it MUST be 2 columns × 3 ROWS = 6 panels
- Row 1: Panel 1 (left) + Panel 2 (right)
- Row 2: Panel 3 (left) + Panel 4 (right)
- Row 3: Panel 5 (left) + Panel 6 (right)
- Clean WHITE divider lines (4-6px wide) separating panels
- 1 vertical divider + 2 horizontal dividers
- ALL panels EQUAL SIZE — each is exactly 1/6th of the total image
- SAME person (from customer photo) in ALL 6 panels — her exact identity
- Model FULLY VISIBLE in each model panel — no cropping at edges

PHOTOGRAPHY RULES:
- Professional HIGH-QUALITY editorial fashion photography
- Natural, warm lighting — premium lookbook quality
- Clean, simple backgrounds — vary slightly between panels (studio, café, outdoor)
- NO text, watermarks, labels, or panel numbers on the image
- Output must be crisp, sharp, and professional regardless of input quality"""

        _log(f"Tryon GRID prompt: {len(prompt)} chars")

        # ---- Quality → resolution ----
        quality_to_size = {"low": "512px", "medium": "1K", "high": "2K"}
        image_size = quality_to_size.get(quality, "1K")

        # ---- Build contents: garment refs → customer photo → prompt ----
        # CRITICAL: When a clean garment reference (real garment photo / 3D shot) is
        # available, use ONLY that as the garment reference. Do NOT send the hero
        # product photo because it contains an AI-generated model whose face will
        # contaminate Gemini's output (face swap bug).
        contents = []
        garment_ref_count = 0
        for i, g_pil in enumerate(garment_pils):
            brief = garment_briefs[i] if i < len(garment_briefs) else "Fashion garment"
            cat = garment_categories[i] if i < len(garment_categories) else "garment"

            if has_3d and i < len(garment_3d_pils) and garment_3d_pils[i] is not None:
                # Use ONLY the clean garment reference — no hero image (avoids face swap)
                contents.append(f"[GARMENT {i+1} — REAL GARMENT PHOTO: {brief} — This is the ACTUAL garment photographed without any model. Use this as your SOLE garment reference for exact color, shape, pattern, silhouette, fabric, and all design details. Dress the CUSTOMER in this exact garment. Wear this {cat.replace('_', ' ')}]")
                contents.append(garment_3d_pils[i])
                garment_ref_count += 1
                _log(f"Garment {i+1}: using CLEAN garment photo only (no hero) — face swap prevention")
            else:
                # No clean ref available — use the hero product photo (has AI model face)
                # Crop the top 30% to reduce face contamination
                try:
                    w, h = g_pil.size
                    crop_top = int(h * 0.25)  # Remove top 25% where the face is
                    cropped = g_pil.crop((0, crop_top, w, h))
                    contents.append(f"[GARMENT {i+1} — PRODUCT PHOTO (cropped to garment area): {brief} — Study ONLY the garment details from this photo. The person in this photo is NOT the customer. IGNORE any face or body you see — focus ONLY on the garment: color, pattern, fabric, design. Wear this {cat.replace('_', ' ')}]")
                    contents.append(cropped)
                    garment_ref_count += 1
                    _log(f"Garment {i+1}: using CROPPED product photo (top 25% removed to hide AI model face)")
                except Exception:
                    contents.append(f"[GARMENT {i+1} — PRODUCT PHOTO: {brief} — Study ONLY the garment. The person wearing it is NOT the customer. IGNORE their face. Wear this {cat.replace('_', ' ')}]")
                    contents.append(g_pil)
                    garment_ref_count += 1
                    _log(f"Garment {i+1}: using full product photo (crop failed)")

        contents.append("[CUSTOMER PHOTO — This is the REAL PERSON to photograph. She is the ONLY person in this generation. Preserve her COMPLETE identity: face, body shape, proportions, skin tone, hair, height, build — EVERYTHING must be exactly her. Do NOT copy anyone else's appearance. The person in the garment photo(s) above is NOT this person — IGNORE that person entirely.]")
        contents.append(person_pil)
        contents.append(prompt)

        _log(f"Contents: {garment_ref_count} garment ref(s), 3D_available={has_3d}, customer=1, prompt=1")

        # ---- Try each model ----
        for model_name in self._TRYON_MODELS:
            try:
                _log(f"Tryon GRID: trying {model_name} (size={image_size})...")

                img_cfg_kwargs = {"aspect_ratio": "2:3"}
                cfg_kwargs = {
                    "response_modalities": ["TEXT", "IMAGE"],
                    "image_config": types.ImageConfig(**img_cfg_kwargs),
                }

                if "3" in model_name:
                    img_cfg_kwargs["image_size"] = image_size
                    cfg_kwargs["image_config"] = types.ImageConfig(**img_cfg_kwargs)
                    cfg_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_level="High",
                    )

                # Allow up to 2 attempts per model (retry if 2×2 grid detected)
                for attempt in range(2):
                    attempt_contents = contents
                    if attempt == 1:
                        _log(f"Tryon GRID ({model_name}): RETRY — got 2×2 grid, re-emphasizing 3 ROWS")
                        retry_suffix = ("\n\n⚠️ CRITICAL: Your previous output had only 4 panels (2×2). "
                                        "You MUST generate EXACTLY 6 panels in a 2-column × 3-ROW grid. "
                                        "There must be 3 ROWS of 2 panels each = 6 panels total. "
                                        "Do NOT generate a 2×2 grid.")
                        attempt_contents = contents[:-1] + [contents[-1] + retry_suffix]

                    response = client.models.generate_content(
                        model=model_name,
                        contents=attempt_contents,
                        config=types.GenerateContentConfig(**cfg_kwargs),
                    )

                    img_bytes = None
                    for part in response.parts:
                        if hasattr(part, "thought") and part.thought:
                            continue
                        if part.inline_data is not None:
                            mime = getattr(part.inline_data, "mime_type", "") or ""
                            if not mime.startswith("image/"):
                                continue
                            img_bytes = part.inline_data.data
                            if isinstance(img_bytes, str):
                                img_bytes = base64.b64decode(img_bytes)
                            break

                    if img_bytes is None:
                        _log(f"Tryon GRID ({model_name}): no image in response (attempt {attempt+1})")
                        break

                    _log(f"Tryon GRID ({model_name}): got {len(img_bytes):,} bytes (attempt {attempt+1})")

                    # Check if 2×2 instead of 2×3 — retry once if so
                    if attempt == 0:
                        try:
                            check_img = Image.open(io.BytesIO(img_bytes))
                            w, h = check_img.size
                            ratio = h / w if w > 0 else 1.5
                            if ratio < 1.25:
                                _log(f"Tryon GRID: aspect ratio {ratio:.2f} suggests 2×2 — retrying")
                                continue
                        except Exception:
                            pass

                    _log(f"Tryon GRID SUCCESS — model={model_name}, {len(img_bytes):,} bytes")
                    return img_bytes

                if img_bytes is not None:
                    _log(f"Tryon GRID ({model_name}): accepting grid after retry")
                    return img_bytes

            except Exception as e:
                _log(f"Tryon GRID ({model_name}) FAILED: {type(e).__name__}: {e}")
                _log(f"  Traceback:\n{_tb.format_exc()}")
                err_str = str(e).lower()
                if "rate_limit" in err_str or "429" in err_str:
                    _log("  Rate limited — waiting 15s...")
                    time.sleep(15)
                continue

        _log("Tryon GRID: all models exhausted — returning None")
        return None

    def _build_identity_locked_editorial_grid(self, base_tryon_bytes: bytes) -> bytes | None:
        """
        Build a 2×3 editorial collage locally from ONE identity-preserved try-on image.
        Since every panel derives from the same base image, face/body identity remains stable.
        """
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
        import traceback as _tb

        try:
            src = Image.open(io.BytesIO(base_tryon_bytes)).convert("RGB")
            panel_w, panel_h = 768, 1024

            def _fit(img: Image.Image, w: int, h: int) -> Image.Image:
                return ImageOps.fit(img, (w, h), method=Image.LANCZOS, centering=(0.5, 0.45))

            def _crop_focus(img: Image.Image, x0: float, y0: float, x1: float, y1: float) -> Image.Image:
                w, h = img.size
                box = (
                    int(max(0, min(w - 1, x0 * w))),
                    int(max(0, min(h - 1, y0 * h))),
                    int(max(1, min(w, x1 * w))),
                    int(max(1, min(h, y1 * h))),
                )
                if box[2] <= box[0] or box[3] <= box[1]:
                    return img.copy()
                return img.crop(box)

            # Panel 1: clean editorial hero
            p1 = _fit(src, panel_w, panel_h)

            # Panel 2: soft portrait crop (face + upper body)
            p2 = _fit(_crop_focus(src, 0.12, 0.02, 0.88, 0.78), panel_w, panel_h)
            p2 = ImageEnhance.Brightness(p2).enhance(1.03)
            p2 = ImageEnhance.Contrast(p2).enhance(1.04)

            # Panel 3: warm lifestyle tone
            p3 = _fit(src, panel_w, panel_h)
            p3 = ImageEnhance.Color(p3).enhance(1.06)
            p3 = ImageEnhance.Brightness(p3).enhance(1.04)

            # Panel 4: garment detail + face visibility crop
            p4 = _fit(_crop_focus(src, 0.08, 0.10, 0.92, 0.90), panel_w, panel_h)
            p4 = ImageEnhance.Sharpness(p4).enhance(1.10)

            # Panel 5: movement-feel style (subtle dynamic contrast)
            p5 = _fit(src, panel_w, panel_h)
            p5 = ImageEnhance.Contrast(p5).enhance(1.08)
            p5 = p5.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=2))

            # Panel 6: signature campaign look (clean cinematic grade)
            p6 = _fit(src, panel_w, panel_h)
            p6 = ImageEnhance.Color(p6).enhance(0.94)
            p6 = ImageEnhance.Contrast(p6).enhance(1.10)
            p6 = ImageEnhance.Brightness(p6).enhance(1.02)

            panels = [p1, p2, p3, p4, p5, p6]

            divider = 6
            canvas_w = (panel_w * 2) + divider
            canvas_h = (panel_h * 3) + (divider * 2)
            canvas = Image.new("RGB", (canvas_w, canvas_h), "white")

            positions = [
                (0, 0),
                (panel_w + divider, 0),
                (0, panel_h + divider),
                (panel_w + divider, panel_h + divider),
                (0, (panel_h * 2) + (divider * 2)),
                (panel_w + divider, (panel_h * 2) + (divider * 2)),
            ]
            for img, (x, y) in zip(panels, positions):
                canvas.paste(img, (x, y))

            out = io.BytesIO()
            canvas.save(out, format="JPEG", quality=92, optimize=True)
            return out.getvalue()

        except Exception as e:
            _log(f"Identity-lock grid build failed: {type(e).__name__}: {e}")
            _log(f"  Traceback:\n{_tb.format_exc()}")
            return None


# ---------------------------------------------------------------------------
# FASHN.ai Provider (stub — plug in later)
# ---------------------------------------------------------------------------

class FashnAIProvider(ImageProvider):
    """
    Stub for FASHN.ai Product-to-Model API.
    Endpoint: POST https://api.fashn.ai/v1/run
    Cost: $0.075/image on-demand
    To activate: set IMAGE_PROVIDER=fashn and FASHN_API_KEY in .env.yaml
    """

    def generate_pose_grid(
        self,
        garment_images: list[bytes],
        model_prompt: str,
        quality: str = "medium",
        extra_prompt: str = "",
        garment_design_details: str = "",
        uploaded_image_info: list[dict] = None,
    ) -> bytes | None:
        _log("FASHN.ai provider not yet implemented — returning None")
        # TODO: Implement FASHN.ai Product-to-Model API
        # Uses: garment_bytes as product_image, model_prompt as prompt
        # Returns: single model image (not a grid — would need 6 calls or different approach)
        return None


# ---------------------------------------------------------------------------
# Legacy Replicate VTON Provider (testing/comparison only)
# ---------------------------------------------------------------------------

class ReplicateVTONProvider(ImageProvider):
    """
    Legacy wrapper around existing replicate_service.py for comparison testing.
    WARNING: idm-vton is CC BY-NC-SA 4.0 (non-commercial). Testing only.
    """

    def generate_pose_grid(
        self,
        garment_images: list[bytes],
        model_prompt: str,
        quality: str = "medium",
        extra_prompt: str = "",
        garment_design_details: str = "",
        uploaded_image_info: list[dict] = None,
    ) -> bytes | None:
        _log("Replicate VTON provider — legacy mode, not a grid generator")
        # The old Replicate pipeline doesn't generate grids — return None
        # to let main.py fall back to the old flow if needed
        return None


# ---------------------------------------------------------------------------
# Factory — select provider from env var
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "openai": OpenAIImageProvider,
    "gemini": GeminiImageProvider,
    "fashn": FashnAIProvider,
    "replicate": ReplicateVTONProvider,
}


def get_image_provider() -> ImageProvider:
    """
    Create and return the configured image provider.
    Reads IMAGE_PROVIDER env var (default: "openai").
    """
    name = os.environ.get("IMAGE_PROVIDER", "openai").lower().strip()
    cls = _PROVIDERS.get(name)
    if cls is None:
        _log(f"Unknown provider '{name}' — falling back to OpenAI")
        cls = OpenAIImageProvider
    _log(f"Using provider: {cls.__name__}")
    return cls()
