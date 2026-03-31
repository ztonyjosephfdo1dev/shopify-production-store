"""
Pookie Style — AI Product Creation Tool (v6)
Google Cloud Function Entry Point

Two-step flow:
  Step 1 (preview):  Receives images + details -> runs AI pipeline -> returns preview JSON
  Step 2 (confirm):  Receives confirmed preview data -> creates Shopify product

Image Pipeline (cost-optimized — ~$0.016/product, 2 API calls total):
  1 OpenAI text call  → name, description, tags, SEO, dress_style, model_prompt   $0.0003
  1 OpenAI image call → 6-pose grid (2×3) → hero + collage via PIL crop           $0.015
"""

import functions_framework
import json
import os
import base64
import traceback
from services.openai_service import analyze_and_generate_text
from services.image_provider import get_image_provider
from services.image_utils import build_collage_from_grid, compress_for_shopify, build_3d_front_back
from services.shopify_service import (
    upload_image_to_shopify,
    create_product,
    assign_to_collections,
    get_collection_id_by_handle,
    set_product_metafields,
)
from services.image_utils import crop_pose_grid


# ---- Collection mapping tables (reusable) ----

CATEGORY_TO_COLLECTION = {
    "kurti": ["kurti"], "kurti-set": ["kurti-set", "kurthi-set"],
    "suits": ["suits"], "indo-western": ["indo-western"],
    "top-wear": ["top-wear", "tops"], "tops": ["tops", "top-wear"],
    "casual-top": ["casual-top", "tops"], "korean-top": ["korean-top", "tops"],
    "shirt": ["shirt", "tops"], "blouse": ["blouse", "tops"],
    "bodycon": ["bodycon"], "fancy-crop-top": ["fancy-crop-top", "tops", "top-wear"],
    "single-piece": ["single-piece"], "gown": ["gown", "gown-1"],
    "maxi": ["maxi"], "casual-maxi": ["casual-maxi", "maxi"],
    "cord-set": ["cord-set"], "bottom": ["bottom", "bottom-1"],
    "plazo": ["plazo", "bottom"], "skirt": ["skirt", "bottom"],
    "inners": ["inners", "panties"],
    "skin-care": ["skin-care"], "face-wash": ["face-wash", "skin-care"],
    "body-lotion": ["body-lotion", "skin-care"],
}

GARMENT_TO_COLLECTION = {
    "crop top": ["fancy-crop-top", "tops"], "crop-top": ["fancy-crop-top", "tops"],
    "top": ["tops", "top-wear"], "t-shirt": ["tops", "casual-top"],
    "kurti": ["kurti"], "dress": ["single-piece"], "gown": ["gown"],
    "maxi": ["maxi"], "palazzo": ["plazo"], "skirt": ["skirt"],
    "blouse": ["blouse", "tops"], "shirt": ["shirt", "tops"],
    "bodycon": ["bodycon"], "cord-set": ["cord-set"],
    "korean top": ["korean-top", "tops"], "polo": ["tops", "top-wear"],
}


def _cors_headers():
    return {"Access-Control-Allow-Origin": "*"}


def _cors_preflight():
    return (
        "",
        204,
        {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        },
    )


def _error(msg, status=400):
    return (json.dumps({"success": False, "error": msg}), status, _cors_headers())


def _resolve_collections(category: str, suggested: list, garment_type: str) -> list:
    """Resolve collection handles with multiple fallback layers."""
    if category and category in CATEGORY_TO_COLLECTION:
        return CATEGORY_TO_COLLECTION[category]
    if category:
        return [category]
    if suggested:
        return suggested[:3]
    if garment_type:
        gt = garment_type.lower().strip()
        return GARMENT_TO_COLLECTION.get(gt, ["tops", "top-wear"])
    return ["tops", "top-wear"]


@functions_framework.http
def create_product_handler(request):
    """
    HTTP Cloud Function entry point.
    Routes to preview or confirm based on ?action= query param.
    """
    if request.method == "OPTIONS":
        return _cors_preflight()

    try:
        action = request.args.get("action", "preview")
        if action == "confirm":
            return _handle_confirm(request)
        elif action == "tryon_fast":
            return _handle_tryon_fast(request)
        elif action == "tryon_grid":
            return _handle_tryon_grid(request)
        elif action == "tryon":
            # Legacy: combined single-call tryon (fallback)
            return _handle_tryon_fast(request)
        else:
            return _handle_preview(request)
    except Exception as e:
        traceback.print_exc()
        return (
            json.dumps({"success": False, "error": str(e), "stage": "unknown"}),
            500,
            _cors_headers(),
        )


# ===========================================================================
# STEP 1: PREVIEW — AI text + 6-pose image generation
# ===========================================================================
def _handle_preview(request):
    """
    Processes images through AI pipeline and returns preview data.
    Does NOT create a Shopify product.

    Pipeline:
      1. OpenAI text → name, description, tags, SEO, dress_style, model_prompt
      2. OpenAI image → 6-pose grid (2×3) in a single image
      3. PIL crop → hero (front view) + 6-panel collage
      4. Return 2 base64 images + all text data
    """
    files = request.files.getlist("images")
    if not files:
        return _error("No images uploaded. At least 1 image is required.")
    if len(files) > 3:
        return _error("Maximum 3 images allowed.")

    price = request.form.get("price")
    compare_at_price = request.form.get("compare_at_price")
    sizes = request.form.get("sizes", "")
    category = request.form.get("category", "")
    user_name = request.form.get("name", "")
    user_description = request.form.get("description", "")
    extra_prompt = request.form.get("extra_prompt", "")
    image_quality = request.form.get("image_quality", "low").lower()
    if image_quality not in ("low", "medium", "high"):
        image_quality = "low"
    use_my_description = request.form.get("use_my_description", "false") == "true"
    status = request.form.get("status", "DRAFT").upper()
    if status not in ("DRAFT", "ACTIVE"):
        status = "DRAFT"
    quantity = request.form.get("quantity", "1")
    try:
        quantity = max(1, int(quantity))
    except (ValueError, TypeError):
        quantity = 1

    # Raw garment photo option: auto / manual / skip
    garment_photo_option = request.form.get("garment_photo_option", "auto").lower()
    if garment_photo_option not in ("auto", "manual", "skip"):
        garment_photo_option = "auto"

    if not price or not compare_at_price:
        return _error("Price and compare-at price are required.")
    if not sizes:
        return _error("At least one size must be selected.")

    size_list = [s.strip() for s in sizes.split(",") if s.strip()]

    # Read image bytes
    raw_images = []
    for f in files:
        img_bytes = f.read()
        raw_images.append({
            "bytes": img_bytes,
            "filename": f.filename,
            "content_type": f.content_type or "image/jpeg",
            "base64": base64.b64encode(img_bytes).decode("utf-8"),
        })

    primary_image = raw_images[0]

    # ===== STEP 1: AI Text Generation (1 OpenAI call — $0.0003) =====
    print("[Preview] Step 1/2: AI text generation...")
    ai_result = analyze_and_generate_text(
        images=raw_images,
        user_name=user_name,
        user_description=user_description,
    )

    product_name = ai_result.get("product_name", user_name or "New Product")

    ai_description = ai_result.get("description", "<p>Beautiful fashion product by Pookie Style.</p>")
    if use_my_description and user_description:
        description_html = f"<p>{user_description}</p>"
    else:
        description_html = ai_description

    # Extract new AI fields
    model_prompt = ai_result.get("model_prompt", "")
    styling_tip = ai_result.get("styling_tip", "")
    target_persona = ai_result.get("target_persona", "genz")

    # Append styling tip to description if available
    if styling_tip and not use_my_description:
        description_html += f'\n<p class="pookie-styling-tip">✨ <em>Complete the Look: {styling_tip}</em></p>'

    tags = ai_result.get("tags", [])
    # Always include "automation" tag for bulk filtering
    if "automation" not in [t.lower() for t in tags]:
        tags.append("automation")
    seo_title = ai_result.get("seo_title", product_name)
    seo_description = ai_result.get("seo_description", "")
    detected_garment_type = ai_result.get("detected_garment_type", "")
    suggested_collections = ai_result.get("suggested_collections", [])
    dress_style = ai_result.get("dress_style", "western").lower()
    garment_brief = ai_result.get("garment_brief", "")
    accessories_note = ai_result.get("accessories_note", "")
    garment_design_details = ai_result.get("garment_design_details", "")
    uploaded_image_info = ai_result.get("uploaded_images", [])

    # ===== STEP 2: AI Image Generation — 6-pose grid =====
    print(f"[Preview] Step 2/2: Generating 6-pose grid (quality={image_quality})...")
    print(f"[Preview] Model prompt length: {len(model_prompt)} chars")
    print(f"[Preview] Design details length: {len(garment_design_details)} chars")
    print(f"[Preview] Reference images: {len(raw_images)} (sending ALL to image generator)")
    print(f"[Preview] Uploaded image labels: {[img.get('shows', '?') for img in uploaded_image_info]}")
    print(f"[Preview] API key configured: {'YES' if os.environ.get('OPENAI_API_KEY') else 'NO — MISSING!'}")
    provider = get_image_provider()

    # Pass ALL uploaded images (front + back + detail) to the image generator
    all_garment_bytes = [img["bytes"] for img in raw_images]
    grid_bytes = provider.generate_pose_grid(
        garment_images=all_garment_bytes,
        model_prompt=model_prompt,
        quality=image_quality,
        extra_prompt=extra_prompt,
        garment_design_details=garment_design_details,
        uploaded_image_info=uploaded_image_info,
        garment_type=detected_garment_type,
    )
    print(f"[Preview] Grid generation result: {'SUCCESS ({} bytes)'.format(len(grid_bytes)) if grid_bytes else 'FAILED (None returned)'}")

    # Build preview images from grid
    preview_images = []
    vton_failed = False

    if grid_bytes:
        result = build_collage_from_grid(grid_bytes)
        hero_bytes = result["hero"]
        collage_bytes = result["collage"]
        panels = result.get("panels", [])

        # Image 1: Hero (front view = panel 1)
        preview_images.append({
            "label": "Hero — Front View",
            "base64": base64.b64encode(hero_bytes).decode("utf-8"),
            "filename": "hero.jpg",
            "type": "hero",
        })

        # Images 2-6: Remaining cropped panels (panels 2 through 6)
        for idx, panel_bytes in enumerate(panels[1:], start=2):
            compressed_panel = compress_for_shopify(panel_bytes)
            preview_images.append({
                "label": f"Style View {idx}",
                "base64": base64.b64encode(compressed_panel).decode("utf-8"),
                "filename": f"style-{idx}.jpg",
                "type": "panel",
            })

        # Image 7: collage (all poses in one image)
        collage_label = f"{len(panels)}-Pose Lookbook Collage"
        preview_images.append({
            "label": collage_label,
            "base64": base64.b64encode(collage_bytes).decode("utf-8"),
            "filename": "collage.jpg",
            "type": "collage",
        })
        print(f"[Preview] Grid → hero + {len(panels) - 1} panels + collage ({len(collage_bytes)} bytes)")

        # Image 8: 3D front+back composite (for virtual try-on reference)
        threed_composite = build_3d_front_back(panels)
        if threed_composite:
            compressed_3d = compress_for_shopify(threed_composite)
            preview_images.append({
                "label": "3D Product — Front + Back",
                "base64": base64.b64encode(compressed_3d).decode("utf-8"),
                "filename": "product-3d.jpg",
                "type": "3d",
            })
            print(f"[Preview] 3D front+back composite added ({len(compressed_3d)} bytes)")
        else:
            print("[Preview] 3D front+back composite skipped (not enough panels)")
    else:
        # Fallback: if image generation failed entirely, include raw upload
        vton_failed = True
        print("[Preview] Image generation failed — using raw upload as fallback")
        preview_images.append({
            "label": "Original Upload",
            "base64": primary_image["base64"],
            "filename": "original.jpg",
        })

    # ===== RAW GARMENT PHOTO — append as last product image =====
    garment_photo_b64 = None
    if garment_photo_option == "auto":
        # Use the first uploaded image, compressed
        print("[Preview] Garment photo: using first upload (auto mode)")
        compressed = compress_for_shopify(primary_image["bytes"])
        garment_photo_b64 = base64.b64encode(compressed).decode("utf-8")
    elif garment_photo_option == "manual":
        # Read the separately uploaded garment photo
        manual_file = request.files.get("garment_photo")
        if manual_file:
            manual_bytes = manual_file.read()
            print(f"[Preview] Garment photo: manual upload ({len(manual_bytes)} bytes)")
            compressed = compress_for_shopify(manual_bytes)
            garment_photo_b64 = base64.b64encode(compressed).decode("utf-8")
        else:
            print("[Preview] Garment photo: manual selected but no file uploaded — skipping")
    else:
        print("[Preview] Garment photo: skipped by user")

    if garment_photo_b64:
        preview_images.append({
            "label": "Real Garment Photo",
            "base64": garment_photo_b64,
            "filename": "garment-real.jpg",
            "type": "raw",
        })
        print(f"[Preview] Added real garment photo as last image ({len(garment_photo_b64) // 1024}KB b64)")

    # Resolve collections
    collection_handles = _resolve_collections(
        category, suggested_collections, detected_garment_type
    )

    # ===== Return preview (NOT yet created on Shopify) =====
    print(f"[Preview] Done: {len(preview_images)} images, {len(tags)} tags")
    return (
        json.dumps({
            "success": True,
            "action": "preview",
            "preview": {
                "product_name": product_name,
                "description_html": description_html,
                "tags": tags,
                "seo_title": seo_title,
                "seo_description": seo_description,
                "product_type": detected_garment_type,
                "dress_style": dress_style,
                "sizes": size_list,
                "price": price,
                "compare_at_price": compare_at_price,
                "collections": collection_handles,
                "status": status,
                "category": category,
                "quantity": quantity,
                "images": preview_images,
                "vton_failed": vton_failed,
                "ai_analysis": {
                    "garment_type": detected_garment_type,
                    "dress_style": dress_style,
                    "color": ai_result.get("detected_color", ""),
                    "fabric": ai_result.get("detected_fabric", ""),
                    "style": ai_result.get("detected_style", ""),
                    "occasion": ai_result.get("detected_occasion", ""),
                    "target_persona": target_persona,
                    "styling_tip": styling_tip,
                },
                "ai_description": ai_description,
                "ai_product_name": ai_result.get("product_name", ""),
            },
        }),
        200,
        _cors_headers(),
    )


# ===========================================================================
# STEP 2: CONFIRM — Takes preview data and creates the Shopify product
# ===========================================================================
def _handle_confirm(request):
    """
    Creates the Shopify product from confirmed preview data.
    Expects JSON body with the full product payload (including base64 images).
    """
    data = request.get_json(force=True)
    if not data:
        return _error("No data provided.")

    product_name = data.get("product_name", "New Product")
    description_html = data.get("description_html", "<p></p>")
    tags = data.get("tags", [])
    seo_title = data.get("seo_title", product_name)
    seo_description = data.get("seo_description", "")
    product_type = data.get("product_type", "")
    sizes = data.get("sizes", ["Free Size"])
    price = data.get("price", "0")
    compare_at_price = data.get("compare_at_price", "0")
    collection_handles = data.get("collections", [])
    status = data.get("status", "DRAFT")
    category = data.get("category", "")
    images = data.get("images", [])
    quantity = data.get("quantity", 1)
    try:
        quantity = max(1, int(quantity))
    except (ValueError, TypeError):
        quantity = 1

    if not images:
        return _error("No images in confirm payload.")

    # ===== Upload images to Shopify =====
    print(f"[Confirm] Uploading {len(images)} images to Shopify...")
    uploaded_media = []
    garment_real_resource_url = ""
    product_3d_resource_url = ""
    for img in images:
        img_bytes = base64.b64decode(img["base64"])
        filename = img.get("filename", "product.jpg")
        alt_text = img.get("label", product_name)

        resource_url = upload_image_to_shopify(
            image_bytes=img_bytes,
            filename=filename,
            alt_text=alt_text,
        )
        if resource_url:
            uploaded_media.append((resource_url, alt_text))
            # Track the garment-real image URL for metafield storage
            if "garment-real" in filename:
                garment_real_resource_url = resource_url
                print(f"[Confirm] Garment-real image uploaded: {resource_url}")
            # Track the 3D front+back image URL for virtual try-on
            if "product-3d" in filename:
                product_3d_resource_url = resource_url
                print(f"[Confirm] 3D front+back image uploaded: {resource_url}")

    if not uploaded_media:
        return _error("Failed to upload images to Shopify.", 500)

    # ===== Create product =====
    print(f"[Confirm] Creating product: {product_name}...")
    product_result = create_product(
        title=product_name,
        description_html=description_html,
        product_type=product_type,
        vendor="Pookie Style",
        tags=tags,
        sizes=sizes,
        price=price,
        compare_at_price=compare_at_price,
        media_ids=uploaded_media,
        seo_title=seo_title,
        seo_description=seo_description,
        status=status,
        category=category,
        inventory_quantity=quantity,
    )

    # ===== Save garment metafields for Pookie Mirror =====
    product_id = product_result.get("product_id")
    garment_brief = data.get("garment_brief", "")
    garment_category = data.get("garment_category", "")
    garment_design_details = data.get("garment_design_details", "")
    if product_id:
        mf_list = []
        if garment_brief:
            mf_list.append({"key": "garment_brief", "value": garment_brief})
        if garment_category:
            mf_list.append({"key": "garment_category", "value": garment_category})
        if garment_design_details:
            mf_list.append({"key": "garment_design_details", "value": garment_design_details[:5000], "type": "multi_line_text_field"})
        # Store garment-real image URL so Pookie Mirror can retrieve it directly
        if garment_real_resource_url:
            mf_list.append({"key": "garment_real_url", "value": garment_real_resource_url})
            print(f"[Confirm] Saving garment_real_url metafield: {garment_real_resource_url[:80]}...")
        # Store 3D front+back image URL for virtual try-on reference
        if product_3d_resource_url:
            mf_list.append({"key": "product_image_3d", "value": product_3d_resource_url})
            print(f"[Confirm] Saving product_image_3d metafield: {product_3d_resource_url[:80]}...")
        if mf_list:
            set_product_metafields(product_id, mf_list)

    # ===== Assign to collections =====
    assigned = []
    if product_id and collection_handles:
        for handle in collection_handles:
            col_id = get_collection_id_by_handle(handle)
            if col_id:
                if assign_to_collections(product_id, col_id):
                    assigned.append(handle)

    # ===== Return success =====
    store_domain = os.environ.get("SHOPIFY_STORE", "udfphb-uk.myshopify.com")
    product_handle = product_result.get("handle", "")
    shopify_id = product_result.get("numeric_id", "")

    print(f"[Confirm] Success: {product_name} → {product_handle}")
    return (
        json.dumps({
            "success": True,
            "action": "confirmed",
            "product_name": product_name,
            "product_url": f"https://pookiestyle.in/products/{product_handle}",
            "admin_url": f"https://{store_domain}/admin/products/{shopify_id}",
            "images_uploaded": len(uploaded_media),
            "tags_count": len(tags),
            "collections_assigned": assigned,
        }),
        200,
        _cors_headers(),
    )


# ===========================================================================
# STEP 3: TRYON — Progressive 2-Phase Virtual Try-On (Pookie Mirror)
# ===========================================================================
# Phase 1 (tryon_fast): Real-face inpainting edit → 1 panel shown immediately
# Phase 2 (tryon_grid): Fictional model grid → 5-6 panels appended to slideshow
# Both calls are fired in parallel from the frontend. Cost: $0 + $0 = $0.
# ===========================================================================

def _parse_tryon_request(request):
    """
    Shared parser for tryon requests. Validates input and fetches garment images.
    Returns (person_bytes, garment_images, garment_briefs, garment_categories,
    garment_design_details_list, garment_3d_images, quality, tryon_mode)
    or raises ValueError with an error message.
    """
    import httpx as _httpx

    data = request.get_json(force=True)
    if not data:
        raise ValueError("No data provided.")

    person_b64 = data.get("person_image", "")
    garments = data.get("garments", [])
    tryon_mode = data.get("tryon_mode", "customer_editorial")
    quality = data.get("quality", "medium").lower()

    if not person_b64:
        raise ValueError("Customer photo is required.")
    if not garments:
        raise ValueError("At least one garment is required.")
    if len(garments) > 2:
        raise ValueError("Maximum 2 garments (top + bottom or full outfit).")

    # Decode customer photo
    try:
        person_bytes = base64.b64decode(person_b64)
    except Exception:
        raise ValueError("Invalid person_image base64.")

    # Fetch garment images
    garment_images = []
    garment_briefs = []
    garment_categories = []
    garment_design_details_list = []
    garment_3d_images = []

    for i, g in enumerate(garments):
        image_url = g.get("image_url", "")
        brief = g.get("garment_brief", "Fashion garment")
        category = g.get("garment_category", "full_body")
        design_details = g.get("garment_design_details", "")
        product_image_3d_url = g.get("product_image_3d", "")

        print(f"[Tryon] Garment {i+1}: image_url={'YES' if image_url else 'EMPTY'}, "
              f"product_image_3d={'YES (' + product_image_3d_url[:80] + ')' if product_image_3d_url else 'EMPTY'}, "
              f"brief={brief[:50]}, cat={category}")

        if not image_url:
            img_b64 = g.get("image_base64", "")
            if img_b64:
                garment_images.append(base64.b64decode(img_b64))
            else:
                raise ValueError(f"Garment {i+1}: no image_url or image_base64 provided.")
        else:
            try:
                resp = _httpx.get(image_url, timeout=15, follow_redirects=True)
                resp.raise_for_status()
                garment_images.append(resp.content)
                print(f"[Tryon] Garment {i+1}: fetched {len(resp.content):,} bytes from CDN")
            except Exception as e:
                raise ValueError(f"Failed to fetch garment image {i+1}: {str(e)}")

        # Fetch 3D mannequin image if provided (clean garment reference)
        product_image_3d_url = g.get("product_image_3d", "")
        if product_image_3d_url:
            try:
                resp_3d = _httpx.get(product_image_3d_url, timeout=15, follow_redirects=True)
                resp_3d.raise_for_status()
                garment_3d_images.append(resp_3d.content)
                print(f"[Tryon] Garment {i+1}: fetched 3D image {len(resp_3d.content):,} bytes from CDN")
            except Exception as e:
                print(f"[Tryon] Garment {i+1}: 3D image fetch failed ({e}), proceeding without")
                garment_3d_images.append(None)
        else:
            garment_3d_images.append(None)

        garment_briefs.append(brief)
        garment_categories.append(category)
        garment_design_details_list.append(design_details)

    return person_bytes, garment_images, garment_briefs, garment_categories, garment_design_details_list, garment_3d_images, quality, tryon_mode


def _handle_tryon_fast(request):
    """
    Phase 1: Real-face inpainting edit.
    Returns 1 panel with the customer's real face preserved.
    Background upgraded to editorial quality, accessories added.
    """
    try:
        person_bytes, garment_images, garment_briefs, garment_categories, garment_design_details_list, garment_3d_images, quality, tryon_mode = \
            _parse_tryon_request(request)
    except ValueError as e:
        return _error(str(e))

    print(f"[Tryon FAST] Starting: {len(garment_images)} garment(s), quality={quality}")

    provider = get_image_provider()
    result = provider.generate_tryon_single(
        person_image=person_bytes,
        garment_images=garment_images,
        garment_briefs=garment_briefs,
        garment_categories=garment_categories,
        quality=quality,
    )

    if not result:
        return _error("Try-on generation failed (fast phase). Please try again.", 500)

    # Compress and return single panel
    compressed = compress_for_shopify(result, max_size_kb=400)
    panel_b64 = base64.b64encode(compressed).decode("utf-8")

    print(f"[Tryon FAST] Success: 1 panel, {len(compressed):,} bytes")
    return (
        json.dumps({
            "success": True,
            "action": "tryon_fast",
            "phase": "fast",
            "panels": [panel_b64],
            "panel_count": 1,
        }),
        200,
        _cors_headers(),
    )


def _handle_tryon_grid(request):
    """
    Phase 2: Single grid call → mathematical crop into 6 panels.
    1 Gemini call returns a 2×3 grid image, then we split it with
    simple math (width÷2, height÷3) — no fragile divider detection.
    """
    try:
        person_bytes, garment_images, garment_briefs, garment_categories, garment_design_details_list, garment_3d_images, quality, tryon_mode = \
            _parse_tryon_request(request)
    except ValueError as e:
        return _error(str(e))

    print(f"[Tryon GRID] Starting: {len(garment_images)} garment(s), quality={quality}, mode={tryon_mode}")

    provider = get_image_provider()
    grid_result = provider.generate_tryon_grid(
        person_image=person_bytes,
        garment_images=garment_images,
        garment_briefs=garment_briefs,
        garment_categories=garment_categories,
        garment_design_details_list=garment_design_details_list,
        garment_3d_images=garment_3d_images,
        tryon_mode=tryon_mode,
        quality=quality,
    )

    if not grid_result:
        return _error("Try-on grid generation failed. Please try again.", 500)

    # Simple mathematical crop: width÷2, height÷3 — no divider detection
    from services.image_utils import math_crop_grid
    panels = math_crop_grid(grid_result)
    if not panels:
        print("[Tryon GRID] Math crop failed — returning raw grid as 1 panel")
        panels = [grid_result]

    # Compress each panel
    panel_list = []
    for idx, panel_bytes in enumerate(panels):
        compressed = compress_for_shopify(panel_bytes, max_size_kb=400)
        panel_list.append(base64.b64encode(compressed).decode("utf-8"))

    print(f"[Tryon GRID] Success: {len(panel_list)} panels")
    return (
        json.dumps({
            "success": True,
            "action": "tryon_grid",
            "phase": "grid",
            "panels": panel_list,
            "panel_count": len(panel_list),
        }),
        200,
        _cors_headers(),
    )
