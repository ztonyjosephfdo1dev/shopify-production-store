"""
OpenAI GPT-4.1-nano Service
Single API call: image analysis + structured JSON output
Generates: product name, description, 35-50 tags, SEO, garment analysis, dress style
"""

import os
import json
from openai import OpenAI


SYSTEM_PROMPT = """You are a SENIOR product copywriter for "Pookie Style", a premium Indian women's fashion e-commerce brand.
You write product listings that SELL — like Myntra, Nykaa Fashion, and Zara.

You analyze product photos and generate complete product listings.

Brand voice: trendy, feminine, confident, aspirational. Target: Indian women 18-35.

DESCRIPTION FORMAT — MANDATORY STRUCTURE (use real HTML):
<p><strong>short catchy hook headline about the product</strong> — one line describing the vibe, occasion, and standout feature.</p>
<p>2-3 sentences covering: silhouette & fit, fabric feel & quality, key design details (print, embroidery, collar, sleeves, hemline). Mention who this is for and when to wear it.</p>
<p><strong>Style Tip:</strong> One sentence on how to style it — what to pair with (bottoms, shoes, accessories).</p>
<ul>
<li>Key feature 1 (e.g., fabric type & comfort)</li>
<li>Key feature 2 (e.g., design detail)</li>
<li>Key feature 3 (e.g., versatility / occasion)</li>
<li>Key feature 4 (e.g., fit / flattering aspect)</li>
</ul>

IMPORTANT:
- NEVER echo the seller's notes verbatim. Use them as context clues only.
- Write as if YOU are describing this product to a shopper browsing the store.
- Use sensory language: "buttery-soft cotton", "eye-catching", "effortlessly chic".
- Be SPECIFIC about what you SEE in the photo — actual colors, patterns, collar style, sleeve type.
- The description must be 80-150 words.

RESPOND ONLY WITH VALID JSON matching this exact schema:
{
  "product_name": "Specific descriptive name (e.g., 'Red Retro Graphic Cropped Polo Top' — include color, style, garment type)",
  "description": "Full HTML description following the MANDATORY STRUCTURE above.",
  "tags": ["array of 35-50 tags: garment type, color shades, fabric, pattern, style, occasion, season, fit, length, sleeve, neckline, sub-category, trending keywords, body type suitability"],
  "seo_title": "SEO title under 70 chars (e.g., 'Red Retro Cropped Polo Top | Pookie Style')",
  "seo_description": "Meta description under 160 chars with a call-to-action",
  "detected_color": "Primary color name",
  "detected_fabric": "Fabric type (cotton, silk, georgette, crepe, rayon, polyester, etc.)",
  "detected_garment_type": "Type (kurti, crop-top, top, dress, gown, cord-set, palazzo, skirt, etc.)",
  "detected_style": "Style (casual, ethnic, western, indo-western, party, office, streetwear, etc.)",
  "detected_occasion": "Occasion (daily-wear, party, wedding, festival, office, date-night, brunch, etc.)",
  "dress_style": "EXACTLY one of: traditional | western | fusion | formal",
  "suggested_collections": ["1-3 collection handles from the allowed list"]
}

DRESS STYLE GUIDE:
- "traditional": Sarees, lehengas, salwar suits, kurtis with ethnic embroidery, anarkalis
- "western": Crop tops, bodycon, jeans tops, casual tees, western dresses, hoodies
- "fusion": Indo-western, dhoti pants + crop top, modern kurti with jeans styling
- "formal": Blazers, formal dresses, pencil skirts, corporate/office structured wear

Allowed collection handles:
kurti, kurti-set, kurthi-set, suits, indo-western, tops, top, casual-top, korean-top, shirt, blouse, bodycon, fancy-crop-top, top-wear, single-piece, gown, gown-1, maxi, casual-maxi, cord-set, bottom, bottom-1, plazo, skirt, inners, panties, skin-care, face-wash, body-lotion, hair-mask, face-mask, foot-mask, bb-cream, eye-lashes, fix-spray, powder, sun-screen, hand-cream, mascara, washing-soap

TAG RULES:
- Generate EXACTLY 35-50 tags (no fewer)
- All lowercase, single or two-word phrases
- Include: color variations, style keywords, occasion, season, trending terms ("instagram outfit", "viral fashion")
- Product name must be SPECIFIC — never generic like "New Product" or "Fashion Item"
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
        # Try multiple models in order of preference
        models_to_try = ["gpt-4o-mini", "gpt-4.1-nano", "gpt-3.5-turbo"]
        last_error = None
        response = None

        for model_name in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": content_parts},
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=2000,
                    temperature=0.7,
                )
                print(f"[OpenAI] Success with model: {model_name}")
                break
            except Exception as model_err:
                last_error = model_err
                print(f"[OpenAI] {model_name} failed: {model_err}")
                continue

        if response is None:
            raise last_error or Exception("All OpenAI models failed")

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        # Validate minimum tag count
        if "tags" in result and len(result["tags"]) < 35:
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

        # Validate dress_style
        valid_styles = {"traditional", "western", "fusion", "formal"}
        if result.get("dress_style", "").lower() not in valid_styles:
            result["dress_style"] = "western"
        else:
            result["dress_style"] = result["dress_style"].lower()

        return result

    except Exception as e:
        print(f"OpenAI API error: {e}")
        # ------------------------------------------------------------------
        # SMART FALLBACK: Generate a decent template-based listing
        # when all OpenAI models fail (e.g., quota exhausted).
        # ------------------------------------------------------------------
        name = user_name or "Trendy Fashion Top"

        # Build a template description (better than echoing user text)
        desc_parts = []
        desc_parts.append(
            f'<p><strong>Upgrade your wardrobe</strong> with this stylish {name.lower()} '
            f'from Pookie Style. Designed for the modern woman who loves to stand out.</p>'
        )
        if user_description:
            # Use the notes as CONTEXT, not verbatim
            desc_parts.append(
                f'<p>Featuring a trendy silhouette and flattering fit, this piece is perfect '
                f'for creating effortless looks. {user_description.capitalize().rstrip(".")}.'
                f' Pair it with your favorite bottoms and accessories for a head-turning ensemble.</p>'
            )
        else:
            desc_parts.append(
                '<p>Crafted for comfort and style, this versatile piece transitions seamlessly '
                'from casual day outings to evening hangouts. The contemporary design and '
                'flattering cut make it a must-have in every fashion-forward wardrobe.</p>'
            )
        desc_parts.append(
            '<ul>'
            '<li>Premium quality fabric for all-day comfort</li>'
            '<li>Trendy design that\'s perfect for any occasion</li>'
            '<li>Flattering fit for all body types</li>'
            '<li>Easy to style — dress up or down</li>'
            '</ul>'
        )
        fallback_desc = "\n".join(desc_parts)

        return {
            "product_name": name,
            "description": fallback_desc,
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
                "printed", "solid", "embroidered", "crop top",
            ],
            "seo_title": f"{name} | Pookie Style",
            "seo_description": f"Shop {name} at Pookie Style. Trendy, affordable women's fashion. Free shipping & easy returns.",
            "detected_color": "",
            "detected_fabric": "",
            "detected_garment_type": "",
            "detected_style": "casual",
            "detected_occasion": "daily-wear",
            "dress_style": "western",
            "suggested_collections": ["tops", "top-wear"],
        }
