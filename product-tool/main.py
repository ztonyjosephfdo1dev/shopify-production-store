"""
Pookie Style — AI Product Creation Tool (v4)
Google Cloud Function Entry Point

Two-step flow:
  Step 1 (preview):  Receives images + details -> runs AI pipeline -> returns preview JSON
  Step 2 (confirm):  Receives confirmed preview data -> creates Shopify product

Image Pipeline (cost-optimized — $0.012/product, 3 API calls total):
  1 OpenAI call      → Text (name, description, tags, SEO, dress_style)   $0.0003
  1 Replicate VTON   → 4-pose 2×2 grid image                              $0.01
  2 Replicate ESRGAN → Upscale 2 grid halves 4x                            $0.002
"""

import functions_framework
import json
import os
import base64
import traceback
from services.openai_service import analyze_and_generate_text
from services.replicate_service import generate_and_process_poses
from services.shopify_service import (
    upload_image_to_shopify,
    create_product,
    assign_to_collections,
    get_collection_id_by_handle,
)


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
# STEP 1: PREVIEW — AI text + 4-pose image generation
# ===========================================================================
def _handle_preview(request):
    """
    Processes images through AI pipeline and returns preview data.
    Does NOT create a Shopify product.

    Pipeline:
      1. OpenAI → name, description, tags, SEO, dress_style
      2. Replicate VTON → 4-pose 2×2 grid
      3. Local crop → 4 individual poses
      4. Replicate ESRGAN → upscale each 4x
      5. Return 4 base64 images + all text data
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
    use_my_description = request.form.get("use_my_description", "false") == "true"

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

    tags = ai_result.get("tags", [])
    seo_title = ai_result.get("seo_title", product_name)
    seo_description = ai_result.get("seo_description", "")
    detected_garment_type = ai_result.get("detected_garment_type", "")
    suggested_collections = ai_result.get("suggested_collections", [])
    dress_style = ai_result.get("dress_style", "western").lower()

    # ===== STEP 2: Grid → Split 2 → Upscale 2 → Crop 4 (1+2 Replicate calls — $0.012) =====
    print("[Preview] Step 2/2: Generating 4-pose images...")
    pose_images = generate_and_process_poses(
        garment_bytes=primary_image["bytes"],
        dress_style=dress_style,
        extra_prompt=extra_prompt,
    )

    # Build preview images (base64 for browser display)
    preview_images = []
    for img_data in pose_images:
        preview_images.append({
            "label": img_data["label"],
            "base64": base64.b64encode(img_data["bytes"]).decode("utf-8"),
            "filename": img_data["filename"],
        })

    # Fallback: if image generation failed entirely, include raw upload
    if not preview_images:
        preview_images.append({
            "label": "Original Upload (AI generation unavailable)",
            "base64": primary_image["base64"],
            "filename": "original.jpg",
        })

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
                "images": preview_images,
                "ai_analysis": {
                    "garment_type": detected_garment_type,
                    "dress_style": dress_style,
                    "color": ai_result.get("detected_color", ""),
                    "fabric": ai_result.get("detected_fabric", ""),
                    "style": ai_result.get("detected_style", ""),
                    "occasion": ai_result.get("detected_occasion", ""),
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
    images = data.get("images", [])

    if not images:
        return _error("No images in confirm payload.")

    # ===== Upload images to Shopify =====
    print(f"[Confirm] Uploading {len(images)} images to Shopify...")
    uploaded_media = []
    for img in images:
        img_bytes = base64.b64decode(img["base64"])
        filename = img.get("filename", "product.jpg")
        alt_text = img.get("label", product_name)

        media_id = upload_image_to_shopify(
            image_bytes=img_bytes,
            filename=filename,
            alt_text=alt_text,
        )
        if media_id:
            uploaded_media.append(media_id)

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
        status="DRAFT",
    )

    # ===== Assign to collections =====
    product_id = product_result.get("product_id")
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
