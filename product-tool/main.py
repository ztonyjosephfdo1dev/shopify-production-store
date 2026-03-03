"""
Pookie Style — AI Product Creation Tool
Google Cloud Function Entry Point

Receives multipart form data (images + product details),
runs AI pipeline, creates Shopify product.
"""

import functions_framework
import json
import os
import base64
import traceback
from services.openai_service import analyze_and_generate_text
from services.photoroom_service import remove_background, create_styled_background
from services.replicate_service import virtual_tryon
from services.shopify_service import (
    upload_image_to_shopify,
    create_product,
    assign_to_collections,
    get_collection_id_by_handle,
)
from services.image_utils import create_detail_crop


@functions_framework.http
def create_product_handler(request):
    """
    HTTP Cloud Function entry point.

    Expects multipart/form-data with:
      - images: 1-3 product photos
      - price: selling price (required)
      - compare_at_price: original price (required)
      - sizes: comma-separated size list (required)
      - category: collection handle (optional)
      - name: product name (optional)
      - description: notes/description (optional)

    Returns JSON with product URL and admin URL.
    """

    # --- CORS headers ---
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }
        return ("", 204, headers)

    cors_headers = {"Access-Control-Allow-Origin": "*"}

    try:
        # --- Parse form data ---
        files = request.files.getlist("images")
        if not files:
            return (
                json.dumps({"error": "No images uploaded. At least 1 image is required."}),
                400,
                cors_headers,
            )
        if len(files) > 3:
            return (
                json.dumps({"error": "Maximum 3 images allowed."}),
                400,
                cors_headers,
            )

        price = request.form.get("price")
        compare_at_price = request.form.get("compare_at_price")
        sizes = request.form.get("sizes", "")
        category = request.form.get("category", "")
        user_name = request.form.get("name", "")
        user_description = request.form.get("description", "")

        if not price or not compare_at_price:
            return (
                json.dumps({"error": "Price and compare-at price are required."}),
                400,
                cors_headers,
            )

        if not sizes:
            return (
                json.dumps({"error": "At least one size must be selected."}),
                400,
                cors_headers,
            )

        size_list = [s.strip() for s in sizes.split(",") if s.strip()]

        # Read image bytes
        raw_images = []
        for f in files:
            img_bytes = f.read()
            raw_images.append(
                {
                    "bytes": img_bytes,
                    "filename": f.filename,
                    "content_type": f.content_type or "image/jpeg",
                    "base64": base64.b64encode(img_bytes).decode("utf-8"),
                }
            )

        primary_image = raw_images[0]

        # ===== STEP 1: AI Text Generation (GPT-4.1-nano) =====
        ai_result = analyze_and_generate_text(
            images=raw_images,
            user_name=user_name,
            user_description=user_description,
        )

        product_name = user_name if user_name else ai_result.get("product_name", "New Product")
        description_html = ai_result.get("description", "<p>Beautiful fashion product by Pookie Style.</p>")
        tags = ai_result.get("tags", [])
        seo_title = ai_result.get("seo_title", product_name)
        seo_description = ai_result.get("seo_description", "")
        detected_garment_type = ai_result.get("detected_garment_type", "")
        suggested_collections = ai_result.get("suggested_collections", [])

        # ===== STEP 2: Photoroom — White Background (Image 1) =====
        white_bg_bytes = remove_background(primary_image["bytes"])

        # ===== STEP 3: Photoroom — Styled Background (Image 2) =====
        styled_bg_bytes = create_styled_background(primary_image["bytes"])

        # ===== STEP 4: Replicate VTON — On-Model Shot (Image 3) =====
        vton_bytes = virtual_tryon(primary_image["bytes"])

        # ===== STEP 5: Detail Crop (Image 4) =====
        detail_bytes = create_detail_crop(primary_image["bytes"])

        # ===== STEP 6: Upload all images to Shopify =====
        processed_images = [
            {"bytes": white_bg_bytes, "filename": "white-bg.jpg", "alt": f"{product_name} - White Background"},
            {"bytes": styled_bg_bytes, "filename": "styled-bg.jpg", "alt": f"{product_name} - Styled"},
            {"bytes": vton_bytes, "filename": "on-model.jpg", "alt": f"{product_name} - On Model"},
            {"bytes": detail_bytes, "filename": "detail.jpg", "alt": f"{product_name} - Detail"},
        ]

        # Filter out any None images (if an API failed gracefully)
        valid_images = [img for img in processed_images if img["bytes"] is not None]

        # Also include raw image as fallback if all processing failed
        if not valid_images:
            valid_images = [
                {"bytes": primary_image["bytes"], "filename": "original.jpg", "alt": product_name}
            ]

        uploaded_media = []
        for img in valid_images:
            media_id = upload_image_to_shopify(
                image_bytes=img["bytes"],
                filename=img["filename"],
                alt_text=img["alt"],
            )
            if media_id:
                uploaded_media.append(media_id)

        # ===== STEP 7: Create Shopify Product =====
        product_result = create_product(
            title=product_name,
            description_html=description_html,
            product_type=detected_garment_type,
            vendor="Pookie Style",
            tags=tags,
            sizes=size_list,
            price=price,
            compare_at_price=compare_at_price,
            media_ids=uploaded_media,
            seo_title=seo_title,
            seo_description=seo_description,
            status="DRAFT",
        )

        # ===== STEP 8: Assign to Collections =====
        # Use user-selected category or AI-suggested collections
        collection_handles = []
        if category:
            collection_handles = [category]
        elif suggested_collections:
            collection_handles = suggested_collections[:3]  # Max 3 collections

        product_id = product_result.get("product_id")
        if product_id and collection_handles:
            for handle in collection_handles:
                col_id = get_collection_id_by_handle(handle)
                if col_id:
                    assign_to_collections(product_id, col_id)

        # ===== Return Success =====
        store_domain = os.environ.get("SHOPIFY_STORE", "udfphb-uk.myshopify.com")
        product_handle = product_result.get("handle", "")
        shopify_id = product_result.get("numeric_id", "")

        return (
            json.dumps(
                {
                    "success": True,
                    "product_name": product_name,
                    "product_url": f"https://pookiestyle.in/products/{product_handle}",
                    "admin_url": f"https://{store_domain}/admin/products/{shopify_id}",
                    "images_uploaded": len(uploaded_media),
                    "tags_count": len(tags),
                    "collections_assigned": collection_handles,
                    "ai_analysis": {
                        "garment_type": detected_garment_type,
                        "color": ai_result.get("detected_color", ""),
                        "fabric": ai_result.get("detected_fabric", ""),
                        "style": ai_result.get("detected_style", ""),
                        "occasion": ai_result.get("detected_occasion", ""),
                    },
                }
            ),
            200,
            cors_headers,
        )

    except Exception as e:
        traceback.print_exc()
        return (
            json.dumps(
                {
                    "success": False,
                    "error": str(e),
                    "stage": "unknown",
                }
            ),
            500,
            cors_headers,
        )
