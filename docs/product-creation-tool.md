# AI-Powered Product Creation Tool — HLD & Requirements

Version: 4.0  
Date: 2026-04-03  
Author / Stakeholder: ztonyjosephfdo1dev  
Store: Pookie Style (`udfphb-uk.myshopify.com` | `pookiestyle.in`)

---

## 1. Executive Summary

A **Shopify admin-only page** with a simple upload form. Staff uploads 1-3 raw phone photos + enters price, sizes, quality level. **Two API calls** do everything:

1. **GPT-4o-mini** (text) — analyzes garment → product name, description, 35-50 tags, SEO, `model_prompt`, `garment_design_details`, `uploaded_images` labels
2. **Gemini** (image, primary) — generates a 2×3 grid of **6 model poses in a single image** (consistent model, bottom wear, background across all 6 panels)
3. **PIL** (local, free) — crops grid into hero + 5 style panels + lookbook collage + 3D front+back composite

**Goal:** Any staff member uploads a phone photo → product fully listed on Shopify in 30–90 seconds.

**Cost: ~$0.0003 (~₹0.025) per product with Gemini (free tier). Hosting: ₹0/month (GCP free tier).**

---

## 2. Problem Statement

Listing a product manually takes 20-30 minutes: photography, writing, tagging, variant setup, collection assignment. This tool reduces it to a 30-second form fill + 30–90 second automated processing.

### Why We Moved Away from VTON (Replicate)

| Issue | Detail |
|---|---|
| **Non-commercial license** | idm-vton is CC BY-NC-SA 4.0 — illegal to use in a for-profit store |
| **Inconsistent bottom wear** | 2 separate VTON calls pulled 2 random model photos → different bottoms in each image every session |
| **Cannot generate bottoms** | VTON models only replace the garment zone — cannot generate what the model wears below |
| **Higher cost** | 2× Replicate calls = ~$0.048/product vs ~$0 with Gemini now |

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Shopify Admin Page                            │
│   pookie-product-creator.liquid  (Liquid + Vanilla JS, no framework) │
│                                                                      │
│   Upload form: 1-3 photos + price + sizes + quality dropdown         │
│   Two-step flow: Preview screen → review/edit → Confirm → Created    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │  POST multipart/form-data
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│              Google Cloud Function (Python 3.12)                     │
│   create_product_handler — asia-south1 — 512MB — 300s timeout        │
│                                                                      │
│  ┌─────────────────────┐   ┌────────────────────────────────────┐    │
│  │  openai_service.py  │   │        image_provider.py           │    │
│  │  Text cascade:      │   │   (adapter — IMAGE_PROVIDER env)   │    │
│  │  gpt-4o-mini →      │   │                                    │    │
│  │  gpt-4.1-nano →     │   │  GeminiImageProvider  ★ PRIMARY    │    │
│  │  gpt-3.5-turbo      │   │  gemini-2.5-flash-image →          │    │
│  │                     │   │  gemini-3.1-flash-image-preview     │    │
│  │  → product_name     │   │                                    │    │
│  │  → description      │   │  OpenAIImageProvider  (fallback)   │    │
│  │  → 35-50 tags       │   │  Responses API: gpt-4.1-mini →     │    │
│  │  → seo_title        │   │  gpt-4o-mini → gpt-4o             │    │
│  │  → model_prompt ────┼───┼──► single 2×3 grid image           │    │
│  │  → garment_brief    │   │                                    │    │
│  │  → garment_design   │   │  FashnAIProvider  (stub, future)   │    │
│  │    _details         │   │  ReplicateVTONProvider  (legacy)   │    │
│  │  → uploaded_images  │   │                                    │    │
│  │    (per-image labels│   │  5-Type Classification:             │    │
│  │     & details)      │   │  upper/lower/full/coord_set/       │    │
│  └──────────┬──────────┘   │  footwear → per-type panel configs │    │
│             │              └──────────────┬─────────────────────┘    │
│             │                             │  grid_bytes              │
│             │                             ▼                          │
│             │              ┌────────────────────────────────────┐    │
│             │              │        image_utils.py (PIL)        │    │
│             │              │  crop_pose_grid() → 6 panels       │    │
│             │              │  build_collage_from_grid()          │    │
│             │              │  build_3d_front_back()              │    │
│             │              │  → hero  (panel 1, front view)     │    │
│             │              │  → 5 style panels (panels 2-6)     │    │
│             │              │  → collage  (2×3, 968×1936px)      │    │
│             │              │  → 3D front+back composite         │    │
│             │              └──────────────┬─────────────────────┘    │
│             │                             │                          │
│             └──────────────┬──────────────┘                         │
│                            │ preview JSON (base64 images + all text) │
└────────────────────────────┼─────────────────────────────────────────┘
                             │  Step 1: return preview → staff reviews
                             ▼
                  Staff reviews, edits name/description/status, confirms
                             │  Step 2: confirm (JSON)
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│            shopify_service.py  (same Cloud Function)                 │
│                                                                      │
│  1. stagedUploadsCreate  → upload all images to Shopify CDN          │
│  2. productCreate        → title, desc, tags, SEO, media, options    │
│  3. productVariantsBulkUpdate → size variants + price                │
│  4. inventoryItemUpdate  → enable tracking on each variant           │
│  5. inventorySetQuantities → stock per variant × location            │
│  6. publishablePublish   → publish to all sales channels             │
│  7. productUpdate        → set taxonomy category (v2026-01 fix)      │
│  8. metafieldsSet        → garment_brief, garment_category,          │
│                            garment_design_details, garment_real_url,  │
│                            product_image_3d (for VTON)               │
│  9. collectionAddProducts → auto-assign to resolved collections      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Flow (Step by Step)

### Step 1 — Preview (`?action=preview`)

1. Staff submits form: 1-3 photos + price + sizes + quality + optional fields
2. **Text analysis** (1 OpenAI call, ~$0.0003):
   - Cascade: gpt-4o-mini → gpt-4.1-nano → gpt-3.5-turbo
   - AI analyzes all uploaded images with per-image labeling
   - Returns structured JSON: `product_name`, `description`, `tags`, `seo_title`, `seo_description`, `detected_garment_type`, `dress_style`, `target_persona`, `model_prompt`, `styling_tip`, `garment_brief`, `garment_design_details`, `accessories_note`, `suggested_collections`, `detected_color`, `detected_fabric`, `detected_style`, `detected_occasion`, `uploaded_images`
3. **Garment classification**: `_classify_garment(detected_garment_type)` → one of 5 types: `upper`, `lower`, `full`, `coord_set`, `footwear`. Per-type prompt configs loaded from `_GARMENT_CONFIGS`.
4. **Image generation** (1 Gemini call, $0.00):
   - `generate_pose_grid(garment_bytes, model_prompt, quality, extra_prompt, garment_type, ...)`
   - Gemini generates a single 2×3 grid image with 6 garment-type-aware panels
   - All 6 panels adapt camera framing per garment type (e.g., waist-up for tops, hip-to-toe for bottoms)
   - Fallback cascade: gemini-2.5-flash-image → gemini-3.1-flash-image-preview
   - If Gemini fails entirely, falls back to OpenAI provider
5. **Grid processing** (PIL, local, $0.00):
   - `crop_pose_grid()` → brightness-based divider detection → 6 individual panels
   - Hero = panel 1 (front view) → Shopify product photo 1
   - Panels 2-6 → individual style photos (compressed)
   - `build_collage_from_grid()` → 2×3 collage (968×1936px)
   - `build_3d_front_back()` → panel 6 (ghost mannequin front+back composite)
   - Garment photo appended (auto/manual/skip based on `garment_photo_option`)
6. **Preview JSON** returned: up to 9 images + all text. No Shopify product created yet.

### Step 2 — Confirm (`?action=confirm`)

1. Browser sends confirmed payload: final name, description, all base64 images, status, quantity
2. Upload all images (up to 9) to Shopify via `stagedUploadsCreate` (PUT to GCS signed URL)
3. `productCreate` — title, description, tags, SEO, vendor, product type, media, size variants via `productOptions`
4. `productVariantsBulkUpdate` — set price + compareAtPrice on auto-created variants
5. `inventoryItemUpdate` — enable tracking on each variant
6. `inventorySetQuantities` — set stock per variant × location
7. `publishablePublish` — publish to all sales channels (Online Store, POS, etc.)
8. `productUpdate` — set taxonomy category node (moved out of productCreate for v2026-01 API)
9. `metafieldsSet` — store VTON-critical metadata:
   - `pookie.garment_brief` — short garment description
   - `pookie.garment_category` — upper_body / lower_body / full_body / coord_set
   - `pookie.garment_design_details` — design reproduction checklist
   - `pookie.garment_real_url` — clean garment reference image URL
   - `pookie.product_image_3d` — ghost mannequin front+back URL
10. `collectionAddProducts` — auto-assign to resolved collections
11. Return product URL + admin URL to browser

---

## 5. Five-Type Garment Classification System

### Classification Logic (`_classify_garment()`)

Checked in priority order (most specific → least specific):

| Category | Example Keywords | Panel Framing |
|---|---|---|
| **coord_set** | cord-set, co-ord, kurti set, salwar-suit, sharara, palazzo set | HEAD TO TOE, both pieces equally prominent |
| **footwear** | shoes, heels, sandals, boots, sneakers, slippers, juttis | LOW-ANGLE foot-level, shoes fill 60-70% |
| **full** | dress, gown, saree, lehenga, jumpsuit, maxi, bodycon | HEAD TO TOE, complete outfit fills frame |
| **upper** | top, crop-top, blouse, shirt, kurti, hoodie, jacket, cardigan | HEAD TO WAIST, top garment fills 70-80% |
| **lower** | palazzo, skirt, pants, jeans, leggings, shorts, joggers | HIP TO TOE, bottom garment fills 70-80% |

Default fallback: **full** (safest — shows everything).

### Per-Type Config (`_GARMENT_CONFIGS`)

Each category defines 8 prompt keys that customize all 6 panels:

| Key | Purpose |
|---|---|
| `product_focus` | Framing priority instruction (which garment is the visual star) |
| `hero` | Panel 1 description (camera framing specific to garment type) |
| `back` | Panel 2 description (back view) |
| `angle` | Panel 3 description (3/4 angle view) |
| `detail` | Panel 4 description (close-up details) |
| `movement` | Panel 5 description (movement/walking pose) |
| `threed` | Panel 6 description — 3D ghost mannequin (front+back, invisible mannequin) |
| `photography_note` | Global framing rule appended to all panels |

### Adding a New Garment Type

1. Add keyword set (e.g., `_NEW_KEYWORDS = {"keyword1", "keyword2", ...}`)
2. Add entry to `_CLASSIFICATION_ORDER` (earlier = higher priority)
3. Add config entry to `_GARMENT_CONFIGS` with all 8 panel keys

**Zero function/code changes needed.**

---

## 6. Functional Requirements

### 6.1 Inputs (Staff Provides)

| Field | Required | Default | Notes |
|---|---|---|---|
| **Photos** | Yes | — | 1-3 images (phone, hanger, flat-lay, mannequin). Max 10MB each |
| **Selling price (₹)** | Yes | — | MRP |
| **Compare-at price (₹)** | Yes | — | Strikethrough price |
| **Sizes** | Yes | — | S, M, L, XL, XXL, Free Size checkboxes |
| **Image Quality** | Yes | Medium | Low/Medium/High dropdown |
| **Category** | No | AI detects | Auto-assigns to collection if provided |
| **Product name** | No | AI generates | AI uses if blank |
| **Description/notes** | No | AI generates | Option to use as-is (skip rewrite) |
| **Styling/pose instructions** | No | — | Appended to image generation prompt |
| **Inventory quantity** | No | 1 | Per size variant |
| **Product status** | No | Draft | Draft or Active |
| **Garment photo option** | No | auto | auto / manual / skip — controls real garment photo inclusion |

### 6.2 AI Text Fields (Output of Single GPT Call)

| Field | Description |
|---|---|
| `product_name` | SEO-friendly (e.g., "Emerald Embroidered A-Line Kurti") |
| `description` | 3-5 sentence HTML, brand voice: trendy, feminine, relatable |
| `tags` | 35-50 tags: garment type, color, fabric, pattern, style, occasion, season, fit, length, sleeve, neckline, sub-category, search keywords |
| `seo_title` | ≤70 chars, Google-optimized |
| `seo_description` | ≤160 chars meta description |
| `detected_garment_type` | kurti, crop-top, dress, gown, cord-set, etc. |
| `detected_color` | Primary color |
| `detected_fabric` | Cotton, silk, georgette, etc. |
| `detected_style` | Casual, ethnic, western, party, etc. |
| `detected_occasion` | Daily-wear, party, wedding, festival, etc. |
| `dress_style` | `western` or `ethnic` |
| `garment_brief` | Short description for VTON |
| `garment_design_details` | Detailed design reproduction checklist |
| `accessories_note` | Suggested accessories |
| `target_persona` | `genz` or `professional` (AI decides from garment) |
| `model_prompt` | Rich scene description for image generator |
| `styling_tip` | One-liner appended to product description as `✨ Complete the Look: ...` |
| `suggested_collections` | Array of Shopify collection handles for auto-assignment |
| `uploaded_images` | Per-image AI labels: `shows` (front/back/detail) + `details` text |

### 6.3 AI Image Output (6-Pose Grid — Garment-Type Aware)

Single Gemini call → 2×3 grid image. All 6 panels adapt per garment type:

| Panel | Position | Upper Type | Lower Type | Full/Coord Type |
|---|---|---|---|---|
| 1 | Row 1, Left | **Hero** — Head to waist, top fills 70-80% | **Hero** — Hip to toe, bottom fills 70-80% | **Hero** — Head to toe, full outfit |
| 2 | Row 1, Right | Back view, head to waist | Back view, hip to toe | Full-body back view |
| 3 | Row 2, Left | 3/4 angle, head to waist | 3/4 angle, hip to toe | Full-body 3/4 angle |
| 4 | Row 2, Right | Close-up of top details | Close-up of bottom details | Close-up of outfit details |
| 5 | Row 3, Left | Movement, head to waist | Movement, hip to toe | Full-body movement |
| 6 | Row 3, Right | 3D ghost mannequin (top only) | 3D ghost mannequin (bottom only) | 3D ghost mannequin (full) |

### 6.4 Image Output Breakdown

| # | Image | Source | Shopify Position |
|---|---|---|---|
| 1 | Hero — Front View | Panel 1 of AI grid | Product photo 1 |
| 2-6 | Style Views | Panels 2-6, individually compressed | Product photos 2-6 |
| 7 | Lookbook Collage | 2×3 reassembly (968×1936px) | Product photo 7 |
| 8 | 3D Product (Front + Back) | Panel 6 (ghost mannequin) | Product photo 8 + `product_image_3d` metafield |
| 9 | Real Garment Photo | Compressed upload (if garment_photo_option ≠ skip) | Last photo + `garment_real_url` metafield |

### 6.5 Shopify Product Result

- Title, description (with styling tip), vendor ("Pookie Style"), product type, tags, SEO
- Status: Draft (default) or Active
- Up to 9 images: hero + 5 style panels + collage + 3D composite + garment photo
- Size variants with price + compare-at price
- Inventory per variant at default location
- Collection auto-assignment
- Taxonomy category (best-effort via `productUpdate`)
- VTON metafields (garment_brief, garment_category, garment_design_details, garment_real_url, product_image_3d)

---

## 7. Cost Analysis

### Per-Product Cost

| Step | Service | Gemini (Primary) | OpenAI (Fallback) |
|---|---|---|---|
| Text analysis | gpt-4o-mini | ~$0.0003 | ~$0.0003 |
| Image generation | Gemini / OpenAI | **$0.00** (free tier) | $0.006–$0.052 |
| Grid crop + collage | PIL (local) | $0.00 | $0.00 |
| **Total** | | **~$0.0003** | **~$0.006–$0.052** |

### Quality Levels (OpenAI fallback only — Gemini has no quality-based pricing)

| Quality | OpenAI Image Cost | Resolution |
|---|---|---|
| Low | $0.006 | 1024×1024 |
| Medium | $0.015 | 1024×1536 |
| High | $0.052 | 1536×2048 |

### Monthly Cost Estimate (Gemini Primary)

| Volume | Cost |
|---|---|
| 50 products/mo | ~₹1.25 |
| 200 products/mo | ~₹5.00 |
| 500 products/mo | ~₹12.50 |
| **Hosting** | **₹0 (GCP free tier — permanent)** |

---

## 8. Provider Adapter System

`services/image_provider.py` — swap image generation provider via env var, no code change.

### Configuration (`.env.yaml`)

```yaml
IMAGE_PROVIDER: gemini           # gemini | openai | fashn | replicate
```

### Providers

| Provider | `IMAGE_PROVIDER` | Status | Cost/image | Notes |
|---|---|---|---|---|
| **Gemini** (flash) | `gemini` | ★ **Active Primary** | $0.00 | gemini-2.5-flash-image → gemini-3.1-flash-image-preview |
| OpenAI | `openai` | ✅ Active Fallback | $0.006–$0.052 | Responses API: gpt-4.1-mini → gpt-4o-mini → gpt-4o → images.edit/generate |
| FASHN.ai | `fashn` | 🔧 Stub (future) | $0.049–$0.075 | Purpose-built for fashion |
| Replicate VTON | `replicate` | ⚠️ Deprecated | ~$0.020 | Non-commercial license only |

### Fallback Chains

**Gemini Provider:**
1. `gemini-2.5-flash-image` — up to 3 attempts (retries if 2×2 grid detected)
2. `gemini-3.1-flash-image-preview` — up to 3 attempts

**OpenAI Provider (if Gemini unavailable):**
1. Responses API: gpt-4.1-mini → gpt-4o-mini → gpt-4o (with reference images)
2. `images.edit()` with gpt-image-1 (stitched composite reference)
3. `images.generate()` with gpt-image-1 (prompt-only, no reference)

---

## 9. Shopify Metafield Storage

Namespace: `pookie`

| Key | Type | Stored When | Used By |
|---|---|---|---|
| `garment_brief` | single_line_text_field | Product creation (confirm) | VTON — garment description for Gemini prompt |
| `garment_category` | single_line_text_field | Product creation (confirm) | VTON — body zone (upper_body / lower_body / full_body / coord_set) |
| `garment_design_details` | multi_line_text_field (≤5000 chars) | Product creation (confirm) | VTON — design reproduction checklist |
| `garment_real_url` | single_line_text_field | If garment photo included | VTON — clean garment image URL (alt text: "garment photo") |
| `product_image_3d` | single_line_text_field | If 3D panel generated | VTON — ghost mannequin front+back URL |

---

## 10. File Structure

```
product-tool/
├── main.py                      # Cloud Function entry — preview + confirm + VTON
├── requirements.txt             # Python deps (functions-framework, openai, httpx, Pillow, google-genai)
├── deploy_script.py             # GCP deploy automation
├── push_theme.py                # Shopify theme push automation (GraphQL API)
├── .env.yaml                    # Secrets (gitignored)
└── services/
    ├── __init__.py
    ├── image_provider.py        # ★ Image generation + 5-type classification + VTON
    ├── image_utils.py           # PIL grid crop + collage + 3D composite
    ├── openai_service.py        # Text analysis — gpt-4o-mini cascade
    ├── shopify_service.py       # Shopify GraphQL — upload, create, assign, metafields
    └── replicate_service.py     # Legacy VTON (deprecated)

theme/
├── sections/
│   └── pookie-product-creator.liquid  # Frontend — upload form + preview + confirm
├── snippets/
│   └── pookie-vton-room.liquid        # Pookie Mirror — customer VTON drawer
├── assets/
│   ├── pookie-product-creator.css
│   ├── pookie-vton-room.css
│   └── pookie-vton-music.mp3
└── layout/
    └── theme.liquid                   # Includes pookie-vton-room snippet site-wide
```

---

## 11. Environment Variables (`.env.yaml`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key (`sk-...`) for text analysis + fallback images |
| `GEMINI_API_KEY` | Yes | — | Google Gemini API key for primary image generation + VTON |
| `SHOPIFY_STORE` | Yes | `udfphb-uk.myshopify.com` | Shopify store domain |
| `SHOPIFY_ACCESS_TOKEN` | Yes | — | Shopify admin API token (`shpat_...`) |
| `SHOPIFY_CLIENT_ID` | No | — | For Client Credentials token auto-refresh on 401 |
| `SHOPIFY_CLIENT_SECRET` | No | — | For Client Credentials token auto-refresh |
| `IMAGE_PROVIDER` | No | `openai` | `gemini` \| `openai` \| `fashn` \| `replicate` |
| `IMAGE_MODEL` | No | (provider default) | Override model name within provider |

---

## 12. Deployment

### Cloud Function

```powershell
cd product-tool
python deploy_script.py
```

Copies required files to `C:\tmp\pookie-deploy` (no-space path) → `gcloud functions deploy`.

### Theme

```powershell
cd product-tool
python push_theme.py
```

Pushes all theme files (product creator, VTON room, CSS, audio, templates) to theme `135917666402` via Shopify GraphQL Admin API. Auto-refreshes access token via Client Credentials Grant on 401.

### Post-Deploy Verification

```powershell
# Expect HTTP 400 "No images uploaded" — confirms function is live and routing
curl.exe -X POST https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product?action=preview -d "{}"
```

---

## 13. Shopify GraphQL API Notes (v2026-01)

| Change | Fix Applied |
|---|---|
| `productCategory` removed from `ProductCreateInput` | Now set via separate `productUpdate` after creation |
| Variants auto-created by `productOptions` | `productVariantsBulkUpdate` sets price on auto-created variants |
| Inventory via `inventorySetQuantities` | Uses `InventorySetQuantitiesInput` with `name: "available"` |
| Tracking via `inventoryItemUpdate` | Enables tracking per variant before setting quantities |
| Publishing via `publishablePublish` | Publishes to all discovered sales channels |

---

## 14. Security

- All secrets in `.env.yaml` (gitignored) — never in source code
- Shopify token auto-refreshes on 401 via Client Credentials Grant — zero manual intervention
- No stack traces in API responses — only human-readable errors
- All external API calls have explicit timeouts
- See `docs_security.md` for full security standards

---

## 15. Version History

| Version | Date | Summary |
|---|---|---|
| 1.0 | 2026-03-02 | Initial HLD — FastAPI + DALL-E 3 approach |
| 2.0 | 2026-03-03 | Rewrite — GCP + Replicate VTON + Photoroom + GPT-4.1-nano |
| 3.0 | 2026-03-10 | OpenAI single image call, 6-pose 2×3 grid, adapter pattern |
| **4.0** | **2026-04-03** | **Gemini primary provider, 5-type garment classification, config-driven panels, 3D composite, 9-image output, VTON metafields, coord_set support** |
- Status: **Implemented and deployed to production**

