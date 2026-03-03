"""
OpenAI GPT-4.1-nano Service
Single API call: image analysis + structured JSON output
Generates: product name, description, 35-50 tags, SEO, garment analysis
"""

import os
import json
from openai import OpenAI


SYSTEM_PROMPT = """You are a product listing expert for "Pookie Style", an Indian women's fashion e-commerce store.
You analyze product photos and generate complete product listings.

Brand voice: trendy, feminine, relatable, confident. Target: Indian women 18-35.

RESPOND ONLY WITH VALID JSON matching this exact schema:
{
  "product_name": "SEO-friendly product name (e.g., 'Emerald Green Embroidered A-Line Kurti')",
  "description": "3-5 sentence HTML description. Include <p> tags. Cover silhouette, fabric, occasion, styling tips. Use the brand voice.",
  "tags": ["array of 35-50 tags covering: garment type, color, fabric, pattern, style, occasion, season, fit, length, sleeve, neckline, sub-category, trending keywords, body type suitability"],
  "seo_title": "SEO title under 70 characters",
  "seo_description": "Meta description under 160 characters",
  "detected_color": "Primary color name",
  "detected_fabric": "Fabric type (cotton, silk, georgette, crepe, rayon, etc.)",
  "detected_garment_type": "Type (kurti, top, dress, gown, cord-set, palazzo, skirt, etc.)",
  "detected_style": "Style (casual, ethnic, western, indo-western, party, office, etc.)",
  "detected_occasion": "Occasion (daily-wear, party, wedding, festival, office, date-night, etc.)",
  "suggested_collections": ["array of 1-3 Shopify collection handles that best match this product"]
}

Available collection handles for suggested_collections:
kurti, kurti-set, kurthi-set, suits, indo-western, tops, top, casual-top, korean-top, shirt, blouse, bodycon, fancy-crop-top, top-wear, single-piece, gown, gown-1, maxi, casual-maxi, cord-set, bottom, bottom-1, plazo, skirt, inners, panties, skin-care, face-wash, body-lotion, hair-mask, face-mask, foot-mask, bb-cream, eye-lashes, fix-spray, powder, sun-screen, hand-cream, mascara, washing-soap

IMPORTANT:
- Generate EXACTLY 35-50 tags (no fewer)
- Tags should be lowercase, single or two-word phrases
- Include color variations (e.g., "green", "emerald", "dark green")
- Include style variations (e.g., "casual", "everyday", "relaxed fit")
- Include seasonal tags (e.g., "summer", "all-season")
- Include trending keywords (e.g., "instagram fashion", "viral outfit")
- Product name should be specific and descriptive, not generic
- Description should mention fabric feel, who it's for, and how to style it
"""


def analyze_and_generate_text(images: list, user_name: str = "", user_description: str = "") -> dict:
    """
    Single GPT-4.1-nano call: analyzes product image(s) + generates all text.

    Args:
        images: list of dicts with 'base64' and 'content_type' keys
        user_name: optional user-provided product name
        user_description: optional user-provided description/notes

    Returns:
        dict with all product text and metadata
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # Build the user message with image(s)
    content_parts = []

    # Add images (up to 3)
    for img in images[:3]:
        content_parts.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['content_type']};base64,{img['base64']}",
                    "detail": "low",  # low detail = cheaper, sufficient for garment analysis
                },
            }
        )

    # Build text prompt
    user_text = "Analyze this product photo and generate a complete product listing as JSON."
    if user_name:
        user_text += f"\nThe seller suggests the name: '{user_name}'"
    if user_description:
        user_text += f"\nSeller notes: {user_description}"

    content_parts.append({"type": "text", "text": user_text})

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content_parts},
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.7,
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        # Validate minimum tag count
        if "tags" in result and len(result["tags"]) < 35:
            # Pad with generic fashion tags if AI returned too few
            generic_tags = [
                "women fashion", "online shopping", "indian fashion", "trendy",
                "stylish", "affordable", "pookie style", "new arrival",
                "fashion forward", "instagram fashion", "ootd", "women clothing",
                "ethnic wear", "western wear", "party wear", "casual wear",
                "office wear", "festival wear", "daily wear", "all season",
            ]
            existing = set(t.lower() for t in result["tags"])
            for tag in generic_tags:
                if len(result["tags"]) >= 35:
                    break
                if tag not in existing:
                    result["tags"].append(tag)

        return result

    except Exception as e:
        print(f"OpenAI API error: {e}")
        # Return fallback data so product can still be created
        return {
            "product_name": user_name or "New Fashion Product",
            "description": f"<p>{user_description or 'Beautiful fashion product by Pookie Style.'}</p>",
            "tags": [
                "women fashion", "pookie style", "new arrival", "trendy",
                "indian fashion", "online shopping", "affordable",
                "women clothing", "stylish", "casual wear",
                "ethnic wear", "western wear", "daily wear",
                "party wear", "festival wear", "office wear",
                "all season", "summer collection", "instagram fashion",
                "fashion forward", "ootd", "women style",
                "kurta", "top", "dress", "outfit", "fashion",
                "clothing", "indian wear", "indo western",
                "comfortable", "breathable", "lightweight",
                "printed", "solid", "embroidered",
            ],
            "seo_title": user_name or "New Fashion Product | Pookie Style",
            "seo_description": "Shop the latest fashion at Pookie Style. Trendy, affordable women's clothing.",
            "detected_color": "",
            "detected_fabric": "",
            "detected_garment_type": "",
            "detected_style": "casual",
            "detected_occasion": "daily-wear",
            "suggested_collections": [],
        }
