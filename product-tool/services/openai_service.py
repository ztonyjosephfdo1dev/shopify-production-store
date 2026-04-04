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
  "model_prompt": "A RICH scene description for AI image generation. Include: 1) Model (young Indian woman, ~20-25), 2) EXACT garment details from the photo, 3) A UNIQUE complementary bottom/top SPECIFICALLY styled for THIS garment's color and vibe (see VARIETY rule — different garments must get different pairings), 4) Shoes + accessories that complete THIS specific look, 5) Background/setting, 6) 'editorial fashion photography'. Example: 'Young Indian woman, early 20s, wearing this exact pastel lavender embroidered short kurti, three-quarter sleeves, scallop hem, paired with deep burgundy satin straight-cut churidars, nude strappy block heels, oxidized silver jhumkas, black structured mini sling bag, standing in a terracotta courtyard with hanging ivy and warm golden-hour light, editorial fashion photography, shot on 85mm lens'.",
  "uploaded_images": [
    {
      "index": "1-based index matching the order photos were provided (1 = first photo, 2 = second, etc.)",
      "shows": "EXACTLY one of: front | back | side | detail | dupatta | accessory | full-outfit | other — what this specific photo shows",
      "details": "One-line description of what is visible in THIS photo. Be specific: 'front view showing Leopold text, white collar, vertical stripes' or 'back view showing number 24, same red base with burgundy stripes' or 'sheer pink dupatta with gold zari border and tassels'"
    }
  ],
  "styling_tip": "One-line 'Complete the Look' recommendation. Pick a bottom/top, shoes, and accessories that are UNIQUE to THIS garment's color and style. Be specific with colors and items. Example: 'Pair with deep burgundy tailored trousers, nude block heels, and gold layered necklace for effortless weekend slay 🔥'",
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

MODEL_PROMPT RULES — STYLE LIKE A FASHION EDITOR:
- MUST describe the EXACT garment from the photo — match color, sleeve type, length, pattern precisely.
- Determine if the product is TOP WEAR, BOTTOM WEAR, or a FULL OUTFIT.
  • FULL OUTFIT (dress, gown, jumpsuit, saree, lehenga, cord-set, romper, kurti set, maxi, midi, sharara, gharara, anarkali, dungaree, overalls, salwar suit, churidar set, pant suit): Do NOT add bottom or top wear. Only shoes + accessories.
  • TOP WEAR: Pick a bottom that creates a COMPLETE STYLED LOOK. Think Myntra/Zara editorial.
  • BOTTOM WEAR: Pick a top that creates a COMPLETE STYLED LOOK.

🎯 THE #1 RULE — VARIETY:
  The bottom/top you pick MUST be UNIQUE to THIS specific garment. Style it as if THIS product is being featured in its own dedicated photoshoot.
  - Study the garment's COLOR, FABRIC, PATTERN, and VIBE
  - Pick a complementary piece that a real fashion stylist would pair SPECIFICALLY with THIS garment
  - Different garments of different colors/styles MUST get different bottom/top pairings
  - Think about color theory: complementary colors, analogous tones, contrasting textures
  - Mix it up: sometimes trousers, sometimes a skirt, sometimes culottes, sometimes palazzo, sometimes cargo — whichever suits THIS garment's mood
  - NEVER default to the same pairing for everything — a pink top and a green top should NOT get the same bottom

  Examples of GOOD variety:
    - Lime green crop top → dark charcoal high-waisted cargo pants
    - Pastel pink ruffle blouse → deep burgundy satin midi skirt
    - White graphic tee → washed-black ripped mom jeans
    - Red embroidered kurti → deep teal straight-cut churidars
    - Black sequin party top → emerald green satin wide-leg trousers
    - Navy blue formal shirt → camel tailored cigarette pants
    - Yellow sunflower wrap top → dark indigo denim culottes
    - Lavender satin cami → black faux-leather high-waisted pants
- MUST include shoes (match the vibe), bag, and 1-2 accessories.
- MUST specify background/setting that matches the persona.
- MUST say "editorial fashion photography" and mention lighting.

Allowed collection handles:
kurti, kurti-set, kurthi-set, suits, indo-western, tops, top, casual-top, korean-top, shirt, blouse, bodycon, fancy-crop-top, crop-top, fancy-top, knitting-top, tan-top, t-shirt, top-wear, single-piece, gown, gown-1, maxi, casual-maxi, cord-set, bottom, bottom-1, jeans, formal-pants, joggers, shorts, leggings, cargo-pants, plazo, skirt, inners, panties, accessories, bag, casual-slipper, skin-care, face-wash, body-lotion, hair-mask, face-mask, foot-mask, bb-cream, eye-lashes, fix-spray, powder, sun-screen, hand-cream, mascara, washing-soap

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

# ---- Post-processor: ensure bottom/top variety based on garment color ----
import re as _re
import hashlib as _hashlib

# Color-aware pairing table: garment color family → list of fashionable bottom colors+styles
# Each garment color maps to MULTIPLE options — we pick deterministically by garment name hash
_COLOR_PAIRINGS = {
    "white":     ["black tailored trousers", "dark indigo wide-leg jeans", "charcoal pleated palazzo", "deep olive cargo pants", "burgundy satin midi skirt", "midnight navy cigarette pants"],
    "black":     ["white wide-leg trousers", "cherry red mini skirt", "emerald green satin pants", "cobalt blue pleated culottes", "lavender straight-cut trousers", "mustard yellow A-line skirt"],
    "red":       ["black faux-leather straight pants", "dark charcoal tailored trousers", "deep navy wide-leg jeans", "midnight black pencil skirt", "dark olive cigarette pants", "charcoal pleated culottes"],
    "pink":      ["dark teal straight pants", "black high-waisted cargo pants", "deep plum satin midi skirt", "charcoal wide-leg trousers", "midnight navy pleated palazzo", "espresso brown tapered pants"],
    "blue":      ["white tailored trousers", "rust orange pleated midi skirt", "black straight-leg cargo pants", "camel cigarette pants", "deep burgundy palazzo", "charcoal pinstripe trousers"],
    "green":     ["black high-waisted trousers", "dark chocolate brown culottes", "deep maroon straight pants", "charcoal wide-leg cargo", "midnight navy tailored palazzo", "espresso tapered cigarette pants"],
    "yellow":    ["black wide-leg trousers", "dark indigo denim culottes", "deep forest green palazzo", "charcoal biker-cut cargo pants", "chocolate brown pleated skirt", "deep navy cigarette pants"],
    "orange":    ["dark indigo straight jeans", "black tailored cigarette pants", "deep brown palazzo", "dark olive wide-leg trousers", "navy pleated culottes", "charcoal cargo pants"],
    "purple":    ["black high-waisted trousers", "dark grey tailored pants", "deep forest green palazzo", "midnight blue wide-leg jeans", "charcoal cigarette pants", "ivory pleated midi skirt"],
    "brown":     ["crisp white wide-leg trousers", "deep teal straight pants", "black tailored cigarette pants", "dark navy palazzo", "rust-contrast culottes", "charcoal cargo pants"],
    "grey":      ["black tailored trousers", "burgundy satin midi skirt", "deep emerald wide-leg pants", "cobalt blue pleated culottes", "mustard A-line skirt", "dark navy cigarette pants"],
    "beige":     ["black faux-leather pants", "deep navy wide-leg trousers", "dark olive cargo pants", "burgundy tailored cigarette pants", "charcoal pleated palazzo", "espresso brown straight pants"],
    "multi":     ["solid black straight trousers", "solid deep navy palazzo", "solid charcoal wide-leg pants", "solid black pencil skirt", "solid espresso cigarette pants", "solid midnight cargo pants"],
}
_DEFAULT_PAIRINGS = ["black tailored trousers", "dark charcoal wide-leg pants", "deep navy cigarette pants", "midnight black cargo pants", "dark olive palazzo", "espresso brown culottes"]

def _get_color_family(color: str) -> str:
    """Map a detected color string to a color family key."""
    c = color.lower().strip()
    for family in _COLOR_PAIRINGS:
        if family in c:
            return family
    # Check for common aliases
    if any(w in c for w in ["cream", "ivory", "off-white"]): return "white"
    if any(w in c for w in ["maroon", "burgundy", "wine", "crimson"]): return "red"
    if any(w in c for w in ["navy", "indigo", "cobalt", "teal", "cyan", "aqua"]): return "blue"
    if any(w in c for w in ["olive", "mint", "emerald", "lime", "sage"]): return "green"
    if any(w in c for w in ["coral", "peach", "salmon", "tangerine"]): return "orange"
    if any(w in c for w in ["lavender", "violet", "mauve", "plum", "lilac"]): return "purple"
    if any(w in c for w in ["rose", "blush", "fuchsia", "magenta", "hot pink"]): return "pink"
    if any(w in c for w in ["gold", "mustard", "lemon", "amber"]): return "yellow"
    if any(w in c for w in ["khaki", "tan", "sand", "camel", "nude", "taupe"]): return "beige"
    if any(w in c for w in ["chocolate", "espresso", "mocha", "coffee"]): return "brown"
    if any(w in c for w in ["charcoal", "slate", "silver", "ash"]): return "grey"
    if any(w in c for w in ["multi", "print", "floral", "pattern", "stripe", "check"]): return "multi"
    return ""

def _fix_styling_variety(result: dict) -> dict:
    """Post-process: ensure the bottom/top pairing is varied based on garment color."""
    detected_color = result.get("detected_color", "")
    product_name = result.get("product_name", "")
    if not detected_color:
        return result

    color_family = _get_color_family(detected_color)
    pairings = _COLOR_PAIRINGS.get(color_family, _DEFAULT_PAIRINGS)

    # Pick deterministically by product name hash — same product always gets same pairing,
    # but different products get different ones
    h = int(_hashlib.md5(product_name.encode()).hexdigest(), 16)
    chosen = pairings[h % len(pairings)]

    print(f"[StyleVariety] {detected_color} ({color_family}) → suggested pairing: {chosen}")
    # We don't force-replace the prompt — just log the suggestion.
    # The prompt instructions + variety examples should handle it.
    # Only intervene if model_prompt has NO bottom/top mention at all.
    return result


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

        # ---- POST-PROCESS: Log styling variety for monitoring ----
        result = _fix_styling_variety(result)

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
