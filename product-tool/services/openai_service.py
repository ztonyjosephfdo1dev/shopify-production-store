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

Brand voice: trendy, boss-babe, effortlessly chic, aspirational. Target: GenZ women, office women, elegant/royal women 18-35.

DESCRIPTION FORMAT — MANDATORY STRUCTURE (use real HTML, MAX 40 WORDS):
<p><strong>Catchy one-liner hook</strong> — trendy, boss-babe energy, slay-worthy vibe.</p>
<p>One short sentence covering fabric, fit, key design detail, and when to wear it.</p>

CRITICAL RULES:
- EXACTLY 2 short paragraphs. NO bullet points. NO <ul>/<li> tags. NO Style Tip section.
- MAX 40 words total. Be punchy, not wordy.
- Target: GenZ women, office/corporate women, royal/elegant women.
- Tone: trendy, boss-babe, effortlessly chic, "slay", "vibe", "serve looks".
- NEVER echo the seller's notes verbatim. Use them as context clues only.
- Write as if YOU are describing this product to a shopper browsing the store.
- Use sensory language: "buttery-soft", "slay-worthy", "effortlessly chic", "main character energy".
- Be SPECIFIC about what you SEE in the photo — actual colors, patterns, collar style, sleeve type.

RESPOND ONLY WITH VALID JSON matching this exact schema:
{
  "product_name": "Specific descriptive name (e.g., 'Red Retro Graphic Cropped Polo Top' — include color, style, garment type)",
  "description": "Full HTML description following the MANDATORY STRUCTURE above.",
  "tags": ["array of 35-50 tags: garment type, color shades, fabric, pattern, style, occasion, season, fit, length, sleeve, neckline, sub-category, trending keywords, body type suitability"],
  "seo_title": "SEO title under 70 chars (e.g., 'Red Retro Cropped Polo Top | Pookie Style')",
  "seo_description": "Meta description under 160 chars with a call-to-action",
  "detected_color": "Primary color name",
  "detected_fabric": "Fabric type (cotton, silk, georgette, crepe, rayon, polyester, etc.)",
  "detected_garment_type": "Type (kurti, crop-top, top, dress, gown, cord-set, palazzo, skirt, jeans, pants, trousers, joggers, shorts, leggings, etc.)",
  "detected_style": "Style (casual, ethnic, western, indo-western, party, office, streetwear, etc.)",
  "detected_occasion": "Occasion (daily-wear, party, wedding, festival, office, date-night, brunch, etc.)",
  "dress_style": "EXACTLY one of: traditional | western | fusion | formal",
  "garment_brief": "One-line VTON description for virtual try-on model. Include: color, garment type, sleeve type, length, neckline, key design detail. Example: 'Red cropped polo top, half sleeves, ribbed collar, fitted cut, above-navel length'. Be PRECISE about sleeve length (sleeveless/cap/short/half/three-quarter/full) and garment length (cropped/waist/hip/knee/ankle/floor).",
  "garment_design_details": "CRITICAL: A DETAILED INVENTORY of every visual design element on the garment. This will be used by an image AI to reproduce the garment exactly. Be EXHAUSTIVE and PRECISE. Include ALL of: 1) TEXT — every word/letter/number visible, exact spelling, font style (gothic, serif, sans-serif, script, block), approximate size, position on garment (center chest, left chest, back, sleeve, hem). 2) LOGOS/ICONS — describe each logo/icon shape precisely (e.g., 'four-petal clover icon, white, top-left chest'), position, size, color. 3) GRAPHICS/EMBELLISHMENTS — any stars, circles, emblems, badges, crests, embroidery, prints, images. Describe shape, color, position. 4) STRIPES/PATTERNS — describe exact pattern (e.g., '2 dark burgundy vertical stripes, ~2cm wide, running from shoulder to hem, positioned ~8cm apart, on red base'). 5) COLOR MAP — base color + all accent colors and where they appear. 6) STRUCTURAL DETAILS — collar type+color, button/zipper placement, pocket positions, seam lines, ribbing, trim. Example: 'Base: red/cherry jersey fabric. CENTER CHEST: gothic-font text LEOPOLD in white, ~3cm tall. ABOVE TEXT: 4-pointed star icon in white. BELOW TEXT: oval spiral/chain graphic in white. LEFT CHEST: white 4-petal clover logo. RIGHT CHEST: circular crest/badge with star center, white outline. STRIPES: 2 dark burgundy vertical stripes from shoulder to hem, one on each side of center. COLLAR: white flat polo collar. SLEEVES: short, with number 2 in dark burgundy on left sleeve. HEM: cropped above navel, straight cut.'",
  "accessories_note": "One-line styling note for try-on model. For western: 'minimal western accessories, simple chain, no bindi, no Indian jewelry'. For traditional: 'traditional Indian jewelry, jhumkas, bangles'. For fusion: 'mix of minimal modern and ethnic accessories'.",
  "target_persona": "EXACTLY one of: genz | professional — Decide based on garment style, color, and occasion. GenZ = trendy, colorful, casual, street-style, fun, youthful. Professional = structured, formal, muted tones, office-appropriate, elegant.",
  "model_prompt": "A RICH scene description for AI image generation of a model wearing this garment. Follow MODEL_PROMPT RULES strictly. Include: 1) Model description (young Indian woman, age ~20-25), 2) The EXACT garment details (color, type, sleeves, length, pattern, fabric texture), 3) Fashion-expert bottom wear pick — see BOTTOM WEAR rules above — NEVER blue jeans, 4) Accessories (earrings, bag, shoes — match the persona), 5) Background/setting, 6) Photography style. Example: 'Young Indian woman, early 20s, wearing this exact black floral embroidered cropped knit top, short sleeves, ribbed trim, paired with dark charcoal wide-leg trousers, white chunky sneakers, dainty gold layered necklace, mini leather sling bag, standing in a sunlit café patio with potted plants, warm natural lighting, editorial fashion photography, shot on 85mm lens'.",
  "uploaded_images": [
    {
      "index": "1-based index matching the order photos were provided (1 = first photo, 2 = second, etc.)",
      "shows": "EXACTLY one of: front | back | side | detail | dupatta | accessory | full-outfit | other — what this specific photo shows",
      "details": "One-line description of what is visible in THIS photo. Be specific: 'front view showing Leopold text, white collar, vertical stripes' or 'back view showing number 24, same red base with burgundy stripes' or 'sheer pink dupatta with gold zari border and tassels'"
    }
  ],
  "styling_tip": "One-line 'Complete the Look' recommendation. As a fashion stylist pick the PERFECT bottom, shoes, and accessories that complement this specific garment. NEVER default to blue jeans. Be specific with colors and items. Example: 'Pair with black high-waisted cargo pants, white chunky sneakers, and a mini sling bag for effortless weekend slay \ud83d\udd25'",
  "suggested_collections": ["1-3 collection handles from the allowed list"]
}

UPLOADED_IMAGES RULES:
- You MUST include one entry for EACH uploaded photo, in order (index 1, 2, 3...)
- Auto-detect what each photo shows by analyzing its content:
  • 'front' = shows the front of the garment (most common first photo)
  • 'back' = shows the back of the garment (look for back neckline, back prints, back closure)
  • 'side' = shows a side/profile view
  • 'detail' = close-up of fabric, embroidery, print, or specific design element
  • 'dupatta' = a dupatta, scarf, stole, or draping accessory shown separately
  • 'accessory' = belt, bag, jewelry, or other accessory shown separately
  • 'full-outfit' = shows the complete styled outfit (top + bottom + accessories together)
  • 'other' = anything else
- The 'details' field is CRITICAL — describe exactly what design elements are visible in that specific photo. This will be used to tell the image AI which reference to use for which pose panel.

DRESS STYLE GUIDE:
- "traditional": Sarees, lehengas, salwar suits, kurtis with ethnic embroidery, anarkalis
- "western": Crop tops, bodycon, jeans tops, casual tees, western dresses, hoodies
- "fusion": Indo-western, dhoti pants + crop top, modern kurti with jeans styling
- "formal": Blazers, formal dresses, pencil skirts, corporate/office structured wear

TARGET PERSONA GUIDE:
- "genz": Trendy, colorful, casual garments — crop tops, graphic tees, streetwear, fun prints, bold colors, casual dresses, co-ord sets. Background: urban, café, graffiti walls, parks.
- "professional": Structured, elegant, formal garments — blazers, formal kurtis, pencil skirts, office tops, muted/classic colors. Background: modern office, clean studio, elegant interiors.

MODEL_PROMPT RULES — ACT AS A FASHION STYLIST:
- MUST describe the EXACT garment from the photo — match color, sleeve type, length, pattern precisely.
- FIRST: Determine if the product is TOP WEAR, BOTTOM WEAR, or a FULL OUTFIT.
  • If the product is BOTTOM WEAR (jeans, pants, trousers, palazzo, skirt, shorts, joggers, leggings, culottes, dhoti-pants, capri): Pick matching TOP wear. Think like a Myntra/Zara stylist:
    - Casual bottoms (jeans, joggers, cargo pants) → pick from: crop tops, graphic tees, basic tees, tank tops, oversized shirts, hoodies, sweatshirts
    - Ethnic bottoms (palazzos, dhoti-pants, sharara) → pick from: short kurtis, peplum tops, embroidered blouses, crop tops with ethnic print
    - Formal bottoms (trousers, pencil skirts) → pick from: blazers, formal shirts, structured tops, silk blouses, turtlenecks
    - ALWAYS specify the exact COLOR of the top that complements the bottom. NEVER default to white tops.
  • If the product is TOP WEAR (top, shirt, kurti, blouse, crop-top, etc.): Pick matching BOTTOM wear. NEVER default to blue jeans:
    - Crop tops / casual tees → pick from: cargo pants, paperbag-waist trousers, wide-leg pants, pleated skirts, mini skirts, denim shorts, culottes, straight-leg khakis, joggers
    - Ethnic / fusion tops → pick from: palazzos, dhoti pants, flared skirts, churidars, straight pants in contrasting color
    - Formal / office tops → pick from: tailored trousers, pencil skirts, high-waisted cigarette pants, A-line midi skirts
    - Party / glam tops → pick from: leather pants, sequin mini skirt, satin midi skirt, bodycon skirt, high-waisted slit trousers
    - ALWAYS specify the exact COLOR of the bottom that complements the top (e.g., 'olive cargo pants', 'beige wide-leg trousers', 'black pleated midi skirt'). NEVER say just 'jeans' or 'blue jeans'.
  • EXCEPTION: If the garment IS a full outfit (dress, gown, jumpsuit, saree, lehenga, cord-set, romper, kurti set, maxi, midi, sharara, gharara, anarkali, dungaree, overalls, salwar suit, churidar set, pant suit), do NOT add separate top or bottom wear — the garment already covers the full body. Only add shoes and accessories.
  • VARY the pairing color — do NOT always default to beige, khaki, cream, sand, or neutral tones. Match the garment's COLOR and ENERGY: bold pieces deserve bold/dark/contrasting pairings (black, navy, burgundy, emerald, white). Only use neutrals when the garment itself is bold enough to need toning down.
- MUST include shoes (match the vibe), bag, and 1-2 accessories.
- MUST specify background/setting that matches the persona.
- MUST say "editorial fashion photography" and mention lighting.

Allowed collection handles:
kurti, kurti-set, kurthi-set, suits, indo-western, tops, top, casual-top, korean-top, shirt, blouse, bodycon, fancy-crop-top, top-wear, single-piece, gown, gown-1, maxi, casual-maxi, cord-set, bottom, bottom-1, plazo, skirt, inners, panties, skin-care, face-wash, body-lotion, hair-mask, face-mask, foot-mask, bb-cream, eye-lashes, fix-spray, powder, sun-screen, hand-cream, mascara, washing-soap

TAG RULES:
- Generate EXACTLY 35-50 tags (no fewer)
- All lowercase, single or two-word phrases
- Include: color variations, style keywords, occasion, season, trending terms ("instagram outfit", "viral fashion")
- ALWAYS include these tags when applicable: "office wear", "genz fashion", "boss babe", "corporate chic", "work outfit", "slay outfit", "trending now", "instagram worthy"
- Product name must be SPECIFIC — never generic like "New Product" or "Fashion Item"
"""


def _sanitize(s: str) -> str:
    """Strip surrogate characters that can't be UTF-8 encoded."""
    if not s:
        return s
    return s.encode("utf-8", errors="ignore").decode("utf-8")


def _sanitize_deep(obj):
    """Recursively sanitize all strings in a nested data structure (dicts, lists, strings)."""
    if isinstance(obj, str):
        return _sanitize(obj)
    if isinstance(obj, dict):
        return {_sanitize_deep(k): _sanitize_deep(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_deep(item) for item in obj]
    return obj


# Pre-sanitize the system prompt at module load time
_CLEAN_SYSTEM_PROMPT = _sanitize(SYSTEM_PROMPT)


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

    # Sanitize ALL user-supplied text
    user_name = _sanitize(user_name)
    user_description = _sanitize(user_description)

    # Build the user message with image(s)
    content_parts = []

    # Add images (up to 3)
    for img in images[:3]:
        # Ensure base64 string is clean ASCII
        clean_b64 = img['base64'].encode("ascii", errors="ignore").decode("ascii")
        clean_ct = _sanitize(img.get('content_type', 'image/jpeg')) or 'image/jpeg'
        content_parts.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{clean_ct};base64,{clean_b64}",
                    "detail": "high",
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

    # Build messages and deep-sanitize EVERYTHING to prevent surrogate crashes
    messages = _sanitize_deep([
        {"role": "system", "content": _CLEAN_SYSTEM_PROMPT},
        {"role": "user", "content": content_parts},
    ])

    try:
        # Try multiple models in order of preference
        models_to_try = ["gpt-4o-mini", "gpt-4.1-nano", "gpt-3.5-turbo"]
        last_error = None
        response = None

        for model_name in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    response_format={"type": "json_object"},
                    max_tokens=2000,
                    temperature=0.7,
                )
                print(f"[OpenAI] Success with model: {model_name}")
                break
            except Exception as model_err:
                last_error = model_err
                import traceback
                print(f"[OpenAI] {model_name} failed: {model_err}")
                traceback.print_exc()
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
        name = user_name or "Stylish Fashion Piece"

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
            "suggested_collections": [],
        }
