"""
Pookie Style — AI Product Creation Tool (v3)
Google Cloud Function Entry Point

Two-step flow:
  Step 1 (preview):  Receives images + details -> runs AI pipeline -> returns preview JSON
  Step 2 (confirm):  Receives confirmed preview data -> creates Shopify product

Image Pipeline (cost-optimized, 3 API calls total):
  1 OpenAI call  -> Text (name, description, tags, SEO, dress_style)
  1 Replicate    -> Hero front shot (VTON + smart background)
  1 Replicate    -> 3x2 collage grid (6 poses/styles in ONE call)
"""

import functions_framework
import json
import os
import base64
import time
import traceback
from services.openai_service import analyze_and_generate_text
from services.replicate_service import virtual_tryon_hero, virtual_tryon_collage_grid
from services.shopify_service import (
    upload_image_to_shopify,
    create_product,
    assign_to_collections,
    get_collection_id_by_handle,
)


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


@functions_framework.http
def create_product_handler(request):
    """
    HTTP Cloud Function entry point.
    Routes to preview or confirm based on ?action= query param.

    action=preview (default):
      Input:  multipart/form-data with images, price, sizes, etc.
      Output: JSON with AI-generated name, description, tags, generated image base64

    action=confirm:
      Input:  JSON body with confirmed product data + base64 images
      Output: JSON with Shopify product URL
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
# STEP 1: PREVIEW — AI text + image generation, returns preview data
# ===========================================================================
def _handle_preview(request):
    """
    Processes images through AI pipeline and returns preview data.
    Does NOT create a Shopify product — just returns what WOULD be created.
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

    # ===== STEP 1: AI Text Generation (1 OpenAI call) =====
    # AI ALWAYS analyzes the image + user notes to generate name, description, tags
    ai_result = analyze_and_generate_text(
        images=raw_images,
        user_name=user_name,
        user_description=user_description,
    )

    # Product name: use AI-generated (incorporates user_name as a hint)
    product_name = ai_result.get("product_name", user_name or "New Product")

    # Description logic:
    #   - AI always generates a description from image + user notes
    #   - If user checked "use my description", we use their text as-is
    #   - Both are sent in preview so user can switch in the preview screen
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

    # ===== STEP 2: Hero Image (1 Replicate call) =====
    hero_bytes = virtual_tryon_hero(
        garment_bytes=primary_image["bytes"],
        dress_style=dress_style,
        extra_prompt=extra_prompt,
    )

    # Wait between calls to avoid Replicate 429 rate limit (free tier: burst of 1)
    if hero_bytes:
        time.sleep(15)

    # ===== STEP 3: Collage Grid (1 Replicate call) =====
    collage_bytes = virtual_tryon_collage_grid(
        garment_bytes=primary_image["bytes"],
        dress_style=dress_style,
        extra_prompt=extra_prompt,
    )

    # Build image data for preview (base64 for display in browser)
    preview_images = []
    if hero_bytes:
        preview_images.append({
            "label": "Hero - Front View",
            "base64": base64.b64encode(hero_bytes).decode("utf-8"),
            "filename": "hero-front.jpg",
        })
    if collage_bytes:
        preview_images.append({
            "label": "6-Pose Collage Grid",
            "base64": base64.b64encode(collage_bytes).decode("utf-8"),
            "filename": "poses-collage.jpg",
        })

    # Fallback: if both image generations failed, include the raw uploaded photo
    if not preview_images:
        preview_images.append({
            "label": "Original Upload (AI generation unavailable)",
            "base64": primary_image["base64"],
            "filename": "original.jpg",
        })

    # Determine collections — multiple fallback layers
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
    # Garment type → collection mapping for AI-detected types
    GARMENT_TO_COLLECTION = {
        "crop top": ["fancy-crop-top", "tops"], "crop-top": ["fancy-crop-top", "tops"],
        "top": ["tops", "top-wear"], "t-shirt": ["tops", "casual-top"],
        "kurti": ["kurti"], "dress": ["single-piece"], "gown": ["gown"],
        "maxi": ["maxi"], "palazzo": ["plazo"], "skirt": ["skirt"],
        "blouse": ["blouse", "tops"], "shirt": ["shirt", "tops"],
        "bodycon": ["bodycon"], "cord-set": ["cord-set"],
        "korean top": ["korean-top", "tops"], "polo": ["tops", "top-wear"],
    }

    collection_handles = []
    if category and category in CATEGORY_TO_COLLECTION:
        collection_handles = CATEGORY_TO_COLLECTION[category]
    elif category:
        collection_handles = [category]
    elif suggested_collections:
        collection_handles = suggested_collections[:3]
    elif detected_garment_type:
        # Use AI-detected garment type to find collections
        gt_lower = detected_garment_type.lower().strip()
        collection_handles = GARMENT_TO_COLLECTION.get(gt_lower, ["tops", "top-wear"])
    else:
        # Ultimate fallback
        collection_handles = ["tops", "top-wear"]

    # ===== Return preview (NOT yet created on Shopify) =====
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
                # Always include AI-generated alternatives so user can switch
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
    if product_id and collection_handles:
        for handle in collection_handles:
            col_id = get_collection_id_by_handle(handle)
            if col_id:
                assign_to_collections(product_id, col_id)

    # ===== Return success =====
    store_domain = os.environ.get("SHOPIFY_STORE", "udfphb-uk.myshopify.com")
    product_handle = product_result.get("handle", "")
    shopify_id = product_result.get("numeric_id", "")

    return (
        json.dumps({
            "success": True,
            "action": "confirmed",
            "product_name": product_name,
            "product_url": f"https://pookiestyle.in/products/{product_handle}",
            "admin_url": f"https://{store_domain}/admin/products/{shopify_id}",
            "images_uploaded": len(uploaded_media),
            "tags_count": len(tags),
            "collections_assigned": collection_handles,
        }),
        200,
        _cors_headers(),
    )
