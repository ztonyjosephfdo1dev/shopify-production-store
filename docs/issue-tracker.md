# Issue Tracker — Pookie Style Product Tool

## RESOLVED

### 1. Try-on button not working
- **Date:** March 2026
- **Symptom:** "Try It On" button popup didn't open
- **Root cause:** Unescaped apostrophes in JavaScript string literals in Liquid template
- **Fix:** Escaped apostrophes in pookie-product-creator.liquid
- **Status:** ✅ FIXED & DEPLOYED

### 2. 6-panel grid not generating (tryon)
- **Date:** March 2026
- **Symptom:** tryon_grid generation failed silently
- **Root cause:** 7 config issues — model order, thinking mode, bare images, resolution, output size, divider color, prompt
- **Fix:** 7 config fixes to generate_tryon_grid() in image_provider.py
- **Status:** ✅ FIXED & DEPLOYED

### 3. Full outfit misclassified as upper/lower
- **Date:** March 2026
- **Symptom:** Compound garment types like "shirt dress" matched _UPPER set (substring "shirt" hit), hero showed wrong framing
- **Root cause:** _UPPER checked before _FULL in _build_dynamic_panels(); substring match order wrong
- **Fix:** Added _FULL set, checked FIRST before _UPPER/_LOWER
- **Status:** ✅ FIXED & DEPLOYED

### 4. Top hero showing bottom half of body
- **Date:** March 2026
- **Symptom:** For upper-body garments (tops, shirts), hero panel showed full body instead of waist-up crop
- **Root cause:** Hero prompt too weak — said "framed HEAD TO WAIST" but AI ignored it
- **Fix:** Strengthened to explicit "WAIST-UP HALF-BODY SHOT... DO NOT show legs, knees, or feet"
- **Status:** ✅ FIXED & DEPLOYED

### 5. Only 4 images cropped instead of 6
- **Date:** March 2026
- **Symptom:** crop_pose_grid() returned 4 panels for some grids
- **Root cause:** _detect_grid_dimensions() returned 2×2 when aspect ratio ≥ 0.85 AND divider scan failed (threshold 220 too strict)
- **Fix:** Removed auto-detection entirely. Hardcoded cols=2, rows=3 in crop_pose_grid(), build_collage_from_grid(), _assemble_collage_2x3(). We always request 2×3 from AI.
- **Status:** ✅ FIXED & DEPLOYED

### 6. Full outfit failing + raw reference background leaking into generated images
- **Date:** March 28, 2026
- **Symptom:** Product generation sometimes failed for full outfits; generated panels used the raw phone/hanger background from reference photos instead of clean studio backgrounds
- **Root cause:** Unauthorized prompt changes added on March 27 — _DETAIL_ANCHOR ("exactly as in the reference photos"), FINAL VERIFICATION ("look at reference photos ONE MORE TIME"), and Panel 4 zoom hint. These caused AI to over-copy reference images including backgrounds.
- **Fix:** Reverted all 6 unauthorized changes. Restored original prompt (which was working correctly).
- **Status:** ✅ FIXED & DEPLOYED

### 7. Full outfit generates 2×2 grid (4 panels) — cropped as garbage 6 panels
- **Date:** March 28, 2026
- **Symptom:** Full outfit products (gowns, dresses) sometimes got AI-generated grid with only 4 panels (2×2 layout). Hardcoded 2×3 crop sliced them into 6 garbled panels with partial body parts.
- **Root cause:** AI sometimes generates 2×2 grids for long garments. The hardcoded `crop_pose_grid(cols=2, rows=3)` forced a 2×3 math split on a 2×2 image → panels 3,4 were garbage (split across real panel boundaries).
- **Fix (3 changes):**
  1. `image_utils.py` — Added `_count_real_dividers()` function. `crop_pose_grid()` now auto-detects 2×2 vs 2×3 by counting actual horizontal divider lines (2 dividers = 3 rows, 1 divider = 2 rows). Falls back to aspect ratio if no dividers found.
  2. `image_utils.py` — `build_collage_from_grid()` now handles both 4 and 6 panels. Added `_assemble_collage_2x2()`.
  3. `image_provider.py` — Gemini provider now checks returned grid. If 2×2 detected, retries ONCE with stronger "MUST be 3 ROWS" instruction. If retry also 2×2, accepts the 4 panels gracefully.
  4. `main.py` — Collage label is dynamic based on panel count.
- **Status:** ✅ FIXED & DEPLOYED

## OPEN

### 8. Same pose across all 6 panels + missing 3D garment reference
- **Date:** March 28, 2026
- **Symptom:** All 6 virtual try-on panels showed the exact same image (same pose, same crop) — no pose diversity. Also, the 3D mannequin image (cleanest garment reference) was not being sent to Gemini, causing garment fidelity issues.
- **Root cause (2 issues):**
  1. **Identity-lock regression**: Previous fix for identity drift called `generate_tryon_single()` once, then built a 6-panel collage locally by cropping/color-grading that single image. This preserved identity but killed pose diversity entirely.
  2. **3D image dropped**: `_parse_tryon_request()` hardcoded `garment_3d_images.append(None)` — the 3D mannequin photo (`product.images[5]`) was available in frontend data but never sent to the backend.
- **Fix (4 changes):**
  1. `pookie-vton-room.liquid` — Added `product_image_3d` to garment payload so the 3D mannequin URL is sent to the backend.
  2. `main.py` — `_parse_tryon_request()` now fetches the 3D image from CDN when `product_image_3d` URL is provided (graceful fallback if fetch fails).
  3. `image_provider.py` — Removed identity-lock early-return in `generate_tryon_grid()`. Now feeds BOTH the 3D garment image (primary garment reference) AND the customer photo into a single Gemini call that generates all 6 diverse editorial poses. Prompt instructs: 3D shot = garment fidelity source, customer = identity source.
  4. `image_provider.py` — Cleaned bottom-focus styling logic from `generate_tryon_single()` accessory instructions.
- **Status:** ✅ FIXED & DEPLOYED
