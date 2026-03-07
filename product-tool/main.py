"""
Pookie Style — AI Product Creation Tool (v2)
Google Cloud Function Entry Point

Receives multipart form data (images + product details),
runs AI pipeline (3 API calls total), creates Shopify product.

Image Pipeline (cost-optimized):
  Image 1 → Hero front shot (VTON + smart background based on dress style)
  Image 2 → 3×2 collage grid (6 poses/styles in ONE single API call)
"""

import functions_framework
import json
import os
import base64
import traceback
from services.openai_service import analyze_and_generate_text
from services.replicate_service import virtual_tryon_hero, virtual_tryon_collage_grid
from services.shopify_service import (
    upload_image_to_shopify,
    create_product,
    assign_to_collections,
    get_collection_id_by_handle,
)


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
      - extra_prompt: custom styling/pose instruction (optional)

    Returns JSON with product URL and admin URL.

    Total API calls: 3 (1 OpenAI + 1 Replicate hero + 1 Replicate collage)
    Total images uploaded to Shopify: 2
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
        extra_prompt = request.form.get("extra_prompt", "")  # User custom styling/pose instruction

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

        # ===== STEP 1: AI Text Generation (1 OpenAI call) =====
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
        # dress_style → "traditional" | "western" | "fusion" | "formal"
        dress_style = ai_result.get("dress_style", "western").lower()

        # ===== STEP 2: Image 1 — Hero Front Shot (1 Replicate call) =====
        # Smart background auto-selected based on dress style
        hero_bytes = virtual_tryon_hero(
            garment_bytes=primary_image["bytes"],
            dress_style=dress_style,
            extra_prompt=extra_prompt,
        )

        # ===== STEP 3: Image 2 — 3×2 Collage Grid (1 Replicate call) =====
        # Single API call generates all 6 poses/styles in one grid image
        collage_bytes = virtual_tryon_collage_grid(
            garment_bytes=primary_image["bytes"],
            dress_style=dress_style,
            extra_prompt=extra_prompt,
        )

        # ===== STEP 4: Upload to Shopify (2 images only) =====
        processed_images = [
            {
                "bytes": hero_bytes,
                "filename": "hero-front.jpg",
                "alt": f"{product_name} - Front View",
            },
            {
                "bytes": collage_bytes,
                "filename": "poses-collage.jpg",
                "alt": f"{product_name} - All Poses",
            },
        ]

        # Filter out None (if an API call failed gracefully)
        valid_images = [img for img in processed_images if img["bytes"] is not None]

        # Fallback: use raw upload if all processing failed
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

        # ===== STEP 5: Create Shopify Product =====
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

        # ===== STEP 6: Assign Collections =====
        collection_handles = []
        if category:
            collection_handles = [category]
        elif suggested_collections:
            collection_handles = suggested_collections[:3]

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
                    "dress_style": dress_style,
                    "ai_analysis": {
                        "garment_type": detected_garment_type,
                        "dress_style": dress_style,
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
