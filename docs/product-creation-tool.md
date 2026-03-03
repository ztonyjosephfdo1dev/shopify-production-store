# AI-Powered Product Creation Tool — HLD & Requirements

Version: 2.0 (Complete Rewrite)  
Date: 2026-03-03  
Author / Stakeholder: ztonyjosephfdo1dev  
Store: Pookie Style (`udfphb-uk.myshopify.com` | `pookiestyle.in`)

---

## 1. Executive Summary

A **Shopify page** (admin-only, hidden from storefront) with a simple upload form. Staff/employee uploads 1-3 raw phone photos + enters price, sizes. **One backend call** does everything:

1. **GPT-4.1-nano** (single API call) — analyzes image + generates product name, description, 35-50 tags, SEO metadata, detects color/fabric/category
2. **Photoroom API** — removes background, creates white BG + styled BG product shots
3. **Replicate VTON** — places real garment on Indian model (virtual try-on)
4. **Shopify GraphQL** — creates the product with all images, variants, tags, collection

**Goal:** Any staff member uploads a phone photo with minimal details -> product is fully listed on Shopify in 1-3 minutes.

**Cost:** ~INR 12/product. Hosting: INR 0/month (Google Cloud free tier — permanent).

---

## 2. Problem Statement

Listing a product manually takes 20-30 minutes: photography, writing, tagging, variant setup, collection assignment. This tool reduces it to a 30-second form fill + 1-3 minute automated processing.

---

## 3. User Persona

- **Users:** Store owner + any staff/employee
- **Access:** Admin-only Shopify page (hidden from online store; only accessible when logged into Shopify Admin)
- **No password/PIN required** — Shopify's own admin authentication handles access control
- **Input method:** Mobile phone photos + quick form entry
- **Expected volume:** 5-20 products per session
- **Efficiency over performance** — 1-3 minutes per product is acceptable

---

## 4. Functional Requirements

### 4.1 Inputs (Staff Provides)

| Field | Required | Description |
|---|---|---|
| **Raw photo(s)** | Mandatory | 1-3 images from phone (hand, hanger, mannequin, flat-lay) |
| **Price (INR)** | Mandatory | Selling price (MRP) |
| **Compare-at price (INR)** | Mandatory | Original price (for discount strikethrough) |
| **Sizes** | Mandatory | Checkboxes: S, M, L, XL, XXL, Free Size |
| **Category / Collection** | Optional | If blank -> AI detects from image and auto-assigns |
| **Product name** | Optional | If blank -> AI generates from image analysis |
| **Description / Notes** | Optional | Any details, hints, or description. AI uses these + image to generate the full listing |

**Design principle:** Minimal mandatory fields. AI handles everything else.

### 4.2 AI Image Processing Pipeline (4 Images)

**CRITICAL:** We do NOT use DALL-E or any text-to-image AI for product photos. DALL-E generates imagined garments — not the actual product. All images preserve the **real product**.

| # | Image | Method | Preserves Real Product? | Cost |
|---|---|---|---|---|
| 1 | **White background** | Photoroom API — remove BG, place on white | 100% real | `$`0.02 |
| 2 | **Styled background** | Photoroom API — remove BG, add complementary AI background | 100% real | `$`0.10 |
| 3 | **On-model shot** | Replicate VTON — real garment mapped onto model body | Garment is real | `$`0.02 |
| 4 | **Detail/close-up** | Crop from raw photo (center region) — no API | 100% real | `$`0.00 |

### 4.3 AI Text Generation (Single API Call)

**ONE call to GPT-4.1-nano** (cheapest multimodal model) does ALL text generation:

**Input:** 1-3 product images + any user-provided description/notes  
**Output (structured JSON):**

| Output | Details |
|---|---|
| **product_name** | SEO-friendly name. E.g., "Emerald Green Embroidered A-Line Kurti" |
| **description** | 3-5 sentence HTML description. Brand voice: trendy, feminine, relatable. Covers silhouette, fabric, occasion, styling tips. |
| **tags** | **35-50 tags** covering: garment type, color, fabric, pattern, style, occasion, season, fit, length, sleeve, neckline, sub-category, search keywords |
| **seo_title** | 70 chars or less, optimized for Google |
| **seo_description** | 160 chars or less, meta description |
| **detected_color** | Primary color name |
| **detected_fabric** | Fabric type (cotton, silk, georgette, etc.) |
| **detected_garment_type** | Kurti, top, dress, gown, cord-set, palazzo, etc. |
| **detected_style** | Casual, ethnic, western, party, office, etc. |
| **detected_occasion** | Daily-wear, party, wedding, festival, etc. |
| **suggested_collections** | Array of collection handles for auto-assignment |

**Cost per call: ~INR 0.04 (`$`0.0005)**

### 4.4 Shopify Product Creation

After processing, the backend auto-creates the product:

- **Title** -> AI-generated name
- **Body HTML** -> AI-generated description
- **Vendor** -> "Pookie Style"
- **Product type** -> AI-detected garment type
- **Tags** -> 35-50 AI-generated tags (comma-separated)
- **Images** -> 4 processed images uploaded via staged uploads
- **Variants** -> One per selected size (Price + Compare-at Price set)
- **Status** -> Draft (staff reviews in Shopify Admin before publishing)
- **Collections** -> Auto-assigned based on AI detection
- **SEO** -> Title + meta description set

---

## 5. Technical Architecture

### 5.1 System Overview

```
  SHOPIFY ADMIN (theme page)
  pookiestyle.in/pages/product-upload

  [Upload photos] [Price] [Sizes]
  [Optional: name, description, category]
  [Create Product]
         |
         | HTTPS POST (multipart/form-data)
         v
  GOOGLE CLOUD FUNCTION (Python 3.11)
  https://REGION-PROJECT.cloudfunctions.net/create-product

  Sequential pipeline (1-3 min):

  1. Upload images to Cloud Storage
  2. Photoroom API -> white BG (img 1)
  3. Photoroom API -> styled BG (img 2)
  4. Replicate VTON -> on-model (img 3)
  5. Crop raw photo -> detail (img 4)
  6. GPT-4.1-nano -> name, desc, 35-50
     tags, SEO, color, fabric, category
  7. Shopify GraphQL -> staged upload
     images -> create product with all
     variants, tags, collections

  Return: { success, product_url, admin_url }
         |           |          |
    Photoroom    Replicate    OpenAI
     API          VTON       GPT-4.1-nano
    (0.02-0.10   (0.02/     (0.0005/
     /image)      image)      call)
```

### 5.2 Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Frontend** | Shopify Liquid section (`pookie-product-creator.liquid`) | Lives inside the store — no separate hosting. Vanilla JS + CSS. |
| **Backend** | Google Cloud Function (Python 3.11, HTTP trigger) | Serverless, permanently free, no server to manage |
| **Temp Storage** | Google Cloud Storage (5 GB free) | Store raw uploads temporarily during processing |
| **AI Vision + Text** | OpenAI GPT-4.1-nano (single call: image analysis + structured JSON) | Cheapest multimodal model. ~INR 0.04/product |
| **BG Removal** | Photoroom API (Basic plan: `$`0.02/image) | Industry-leading BG removal |
| **Styled Background** | Photoroom API (Plus: `$`0.10/image) | AI background generation |
| **Virtual Try-On** | Replicate — `prunaai/p-tryon` or `omnious/vella-1.5` | Commercial-licensed, ~`$`0.02/image |
| **Shopify API** | GraphQL Admin API v2026-01 | Product creation, media upload, collections |

### 5.3 Why NOT DALL-E 3

| Approach | Problem |
|---|---|
| DALL-E 3 | **Text-to-image only.** Cannot accept a product photo and reproduce the exact garment. Generates an imagined similar garment — NOT the actual product. Unacceptable for e-commerce. |
| GPT Image (gpt-image-1) | Can edit images but still re-generates — subtle changes to fabric texture, color, stitching. Not pixel-perfect. |
| **Our approach** | Photoroom removes/replaces background (garment untouched). Replicate VTON maps real garment onto model (garment preserved). **100% real product in every image.** |

---

## 6. Shopify API — Verified Scopes & Version

**Token:** `shpat_***REDACTED***`  
**API Version:** `2026-01` (Latest)

### Current scopes (verified 2026-03-03):

All required scopes are **already active**:

| Scope | Status | Used For |
|---|---|---|
| `write_products` / `read_products` | Active | Create products, set variants, tags |
| `write_files` / `read_files` | Active | Upload product images via staged uploads |
| `read_content` / `write_content` | Active | Page template operations |
| `write_themes` / `read_themes` | Active | Push theme files (section + template) |
| `read_inventory` | Active | Inventory queries |
| `write_translations` / `read_translations` | Active | Locale/translation operations |

### Verified capabilities (tested 2026-03-03):
- `stagedUploadsCreate` — image upload works on `2026-01`
- Collections access — all 43 collections readable
- GraphQL endpoint responding correctly

**No new app version or token regeneration needed.**

---

## 7. Google Cloud Setup — Complete Guide

### 7.1 Why Google Cloud (Not AWS)

| Factor | AWS | Google Cloud |
|---|---|---|
| **Lambda / Cloud Functions** | Always Free (1M/mo) | Always Free (2M/mo) |
| **S3 / Cloud Storage** | **12-month trial — EXPIRED for your account** | **Always Free (5 GB permanent)** |
| **API Gateway** | **12-month trial — EXPIRED** | **Not needed** (Cloud Functions have built-in HTTP triggers) |
| **Total after free tier expires** | ~`$`0.03+/mo | **`$`0.00/mo** |

**Your AWS account has been active for 1+ year.** S3 and API Gateway free tiers are expired. Lambda is still free but you would pay for S3 + API Gateway. **Google Cloud is permanently free for this workload.**

### 7.2 Google Cloud Free Tier — Permanent Limits

These **never expire** (not a 12-month trial):

| Service | Always Free Allowance | Your Usage |
|---|---|---|
| **Cloud Functions** | 2,000,000 invocations/month | ~100/month |
| **Cloud Functions compute** | 400,000 GB-seconds/month | ~6,000 GB-sec/month |
| **Cloud Storage** | 5 GB (US regions) | ~1 GB |
| **Cloud Storage operations** | 5,000 Class A + 50,000 Class B/month | ~200/month |
| **Cloud Build** | 120 build-minutes/day | ~5 min/deploy |
| **Cloud Monitoring** | 5 GB logs + 10 metrics | Minimal |

**Result: `$`0.00/month — permanently, forever, no trial period.**

### 7.3 Step-by-Step Setup

#### Step 1: Create Google Cloud Account
1. Go to https://cloud.google.com/free
2. Sign in with your Google account
3. Add a credit card (required but will not be charged within free tier)
4. You will get `$`300 trial credits for 90 days (bonus — not needed for our use case)

#### Step 2: Create a Project
1. Go to https://console.cloud.google.com
2. Click "Select a project" then "New Project"
3. Name: `pookie-style-automation`
4. Click "Create"

#### Step 3: Enable Required APIs
In Google Cloud Console then APIs & Services then Enable APIs:
- **Cloud Functions API**
- **Cloud Build API**
- **Cloud Storage API** (usually enabled by default)
- **Artifact Registry API** (for Cloud Functions deployment)

#### Step 4: Install Google Cloud CLI (on your PC)

Download and install from: https://cloud.google.com/sdk/docs/install

Then authenticate:
```
gcloud auth login
gcloud config set project pookie-style-automation
```

#### Step 5: Create Cloud Storage Bucket (for temp images)
```
gcloud storage buckets create gs://pookie-style-uploads --location=asia-south1
```
(Mumbai region — closest to India, lowest latency)

#### Step 6: Deploy the Cloud Function
```
cd product-tool
gcloud functions deploy create-product --gen2 --runtime=python311 --region=asia-south1 --trigger-http --allow-unauthenticated --timeout=300 --memory=512MB --set-env-vars="OPENAI_API_KEY=sk-xxx,PHOTOROOM_API_KEY=xxx,REPLICATE_API_TOKEN=xxx,SHOPIFY_STORE=udfphb-uk.myshopify.com,SHOPIFY_ACCESS_TOKEN=shpat_xxx"
```

The function URL will be: `https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product`

#### Step 7: Put the function URL in the Shopify theme section
The `pookie-product-creator.liquid` section will POST to this URL.

---

## 8. API Keys & Accounts — Complete Checklist

### Already Have (No Action Needed)

| Service | Credential | Status |
|---|---|---|
| **Shopify Admin API** | `shpat_***REDACTED***` | Working, all scopes active |

### Need to Create / Activate

| # | Service | Sign Up URL | What You Get | Monthly Cost | Action Steps |
|---|---|---|---|---|---|
| 1 | **OpenAI** | https://platform.openai.com/ | API Key (`sk-...`) | ~INR 4 (100 products) | Sign up then Add payment method then Settings then API Keys then "Create new secret key" |
| 2 | **Photoroom** | https://app.photoroom.com/api-dashboard | API Key | FREE (10 images/mo) or `$`20/mo (1,000 images) | Sign up on desktop then API Dashboard then Enable API then Copy key. **Start with free tier (10 images/mo = ~3 products).** |
| 3 | **Replicate** | https://replicate.com/ | API Token (`r8_...`) | ~INR 170 (100 products) | Sign up with GitHub then Account Settings then API Tokens then Create |
| 4 | **Google Cloud** | https://cloud.google.com/free | Service Account JSON | INR 0 (always free) | Sign up then Create project then Follow steps in Section 7.3 |

### Cost Summary Per API Key

| API Key | What It Powers | Free Tier | Cost If Free Exceeded |
|---|---|---|---|
| **OpenAI** (`sk-...`) | Image analysis + product name + description + 35-50 tags + SEO (1 call per product) | Pay-as-you-go only | ~INR 0.04/product |
| **Photoroom** (`photoroom_...`) | BG removal (white) + styled BG with AI background | 10 images/month free (= ~3 products) | Basic: `$`0.02/image, Plus: `$`0.10/image |
| **Replicate** (`r8_...`) | Virtual try-on (garment on model) | Pay-as-you-go only | ~`$`0.02/run (~INR 1.7) |
| **Google Cloud** (service account) | Hosting the backend function + temp image storage | 2M invocations + 5GB storage **permanently free** | `$`0.00 |
| **Shopify** (`shpat_...`) | Product creation, image upload, collection assignment | Included with Shopify plan | `$`0.00 |

---

## 9. Cost Analysis — Final

### Per Product (4 images)

| Step | API | Cost USD | Cost INR |
|---|---|---|---|
| GPT-4.1-nano (vision + text, 1 call) | OpenAI | `$`0.0005 | INR 0.04 |
| BG removal -> white background | Photoroom Basic | `$`0.02 | INR 1.70 |
| BG removal -> styled AI background | Photoroom Plus | `$`0.10 | INR 8.40 |
| Virtual try-on (garment on model) | Replicate | `$`0.02 | INR 1.70 |
| Detail crop from raw photo | None (local) | `$`0.00 | INR 0.00 |
| Google Cloud Function execution | GCP | `$`0.00 | INR 0.00 |
| Shopify product creation | Shopify | `$`0.00 | INR 0.00 |
| **Total per product** | | **`$`0.14** | **INR 11.84** |

### Monthly Operating Cost

| Volume | AI + APIs | Hosting | Total Monthly |
|---|---|---|---|
| **10 products/mo** | ~INR 120 | INR 0 | **~INR 120** |
| **50 products/mo** | ~INR 590 | INR 0 | **~INR 590** |
| **100 products/mo** | ~INR 1,180 | INR 0 | **~INR 1,180** |

### Cost Optimization Options

| Option | Change | Savings |
|---|---|---|
| **Skip styled BG** (use white BG only) | Drop Photoroom Plus call | -INR 8.40/product (INR 3.44 total) |
| **Skip VTON** (no on-model shot) | Drop Replicate call | -INR 1.70/product (INR 10.14 total) |
| **Cheapest mode** (white BG + detail only) | Only Photoroom Basic + GPT-4.1-nano | **INR 1.74/product** |
| **Photoroom free tier** (10 images/mo) | Use for first 3 products free/mo | 3 free products/mo |

---

## 10. User Flow

```
Staff opens: pookiestyle.in/pages/product-upload
(Must be logged into Shopify Admin — page is hidden from store)

  Upload 1-3 photos (drag and drop)
  Price: INR 599    Compare: INR 999
  Sizes: S M L XL
  Any details (optional textarea)
  Category (optional dropdown)

  [Create Product]

  Processing (1-3 min)
  ████████████░░░░░  70%
  "Removing backgrounds..."
  "Generating on-model shot..."
  "Writing description & tags..."
  "Creating product on Shopify..."

  Product created!
  View in Shopify Admin link
  View on store link
  Create another product
```

---

## 11. Backend — Cloud Function Structure

```
product-tool/
  main.py                     # Cloud Function entry point
  requirements.txt            # Python dependencies
  services/
    openai_service.py       # GPT-4.1-nano — single call: vision + text + tags
    photoroom_service.py    # BG removal + styled background
    replicate_service.py    # Virtual try-on
    shopify_service.py      # Product creation via GraphQL
    image_utils.py          # Crop/resize utilities
  .env.yaml                   # Environment variables for GCP deployment
```

**requirements.txt:**
```
functions-framework==3.*
openai>=1.0
httpx>=0.25
replicate>=0.25
Pillow>=10.0
google-cloud-storage>=2.0
```

---

## 12. Collection Mapping

The AI suggests collections via `suggested_collections` in its JSON response. The backend maps these to Shopify collection GIDs:

| Category Group | Collections (handles) |
|---|---|
| **Ethnic Wear** | `kurti`, `kurti-set`, `kurthi-set`, `suits`, `indo-western` |
| **Western Wear** | `tops`, `top`, `casual-top`, `korean-top`, `shirt`, `blouse`, `bodycon`, `fancy-crop-top`, `top-wear` |
| **Dresses & Gowns** | `single-piece`, `gown`, `gown-1`, `maxi`, `casual-maxi` |
| **Cord Sets** | `cord-set` |
| **Bottoms** | `bottom`, `bottom-1`, `plazo`, `skirt` |
| **Innerwear** | `inners`, `panties` |
| **Beauty & Care** | `skin-care`, `face-wash`, `body-lotion`, `hair-mask`, `face-mask`, `foot-mask`, `bb-cream`, `eye-lashes`, `fix-spray`, `powder`, `sun-screen`, `hand-cream`, `mascara`, `washing-soap` |

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Photoroom BG removal quality varies | Admin reviews product in Shopify Draft before publishing |
| VTON model does not look natural | Use commercial-licensed model (`omnious/vella-1.5`); skip VTON for beauty/skincare products |
| GPT-4.1-nano generates wrong tags | Review in Shopify Admin; tags are editable |
| Cloud Function times out (>5 min) | Set timeout to 300s; process sequentially; retry on failure |
| API key compromise | Store in GCP environment variables (encrypted at rest); never in code |
| Shopify rate limits | Single product at a time; no batch pressure |

---

## 14. Implementation Phases

### Phase 1 — MVP (Week 1-2)
- [ ] Create Shopify section (`pookie-product-creator.liquid`) with upload form
- [ ] Create page template (`page.product-upload.json`)
- [ ] Build Google Cloud Function backend
- [ ] Integrate GPT-4.1-nano for text generation (name, desc, 35-50 tags, SEO)
- [ ] Integrate Photoroom for BG removal (white background)
- [ ] Integrate Shopify GraphQL for product creation
- [ ] Deploy to Google Cloud Functions

### Phase 2 — Enhanced Images (Week 3)
- [ ] Add Photoroom styled background (Image 2)
- [ ] Add Replicate VTON on-model shot (Image 3)
- [ ] Add detail crop (Image 4)
- [ ] Progress indicator in UI

### Phase 3 — Future
- [ ] Batch upload mode (CSV + image folder)
- [ ] Collection auto-assignment refinement
- [ ] Mobile camera capture
- [ ] Prompt refinement based on results

---

## 15. Success Criteria

- [ ] Any staff member can create a Shopify product from a phone photo in under 3 minutes
- [ ] All 4 images preserve the real product (no AI-imagined garments)
- [ ] 35-50 accurate, SEO-friendly tags generated per product
- [ ] Auto-detected category matches the actual garment type >90% of the time
- [ ] Cost stays under INR 12/product
- [ ] Hosting remains at INR 0/month

---

## Document Control

- Version: 2.0 (Complete rewrite — corrected architecture, removed DALL-E 3, simplified to serverless)
- Date: 2026-03-03
- Previous version: 1.0 (2026-03-02) — SUPERSEDED
- Author: ztonyjosephfdo1dev
- Status: **Architecture approved — ready for implementation**
