# 🚀 Pookie Style — AI Product Creator (v2)
## Complete Deployment Documentation

**Deployment Date:** March 7, 2026  
**Status:** ✅ LIVE & READY FOR TESTING  
**Project Version:** 2.0 (Cost-Optimized)

---

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Frontend UI Details](#frontend-ui-details)
4. [Backend API Details](#backend-api-details)
5. [Credentials & Environment Variables](#credentials--environment-variables)
6. [Cost Breakdown](#cost-breakdown)
7. [Setup Instructions](#setup-instructions)
8. [Testing Procedures](#testing-procedures)
9. [Troubleshooting](#troubleshooting)
10. [Support & Contact](#support--contact)

---

## 📌 Project Overview

**Pookie Style — AI Product Creation Tool**

Automated product listing generation for fashion e-commerce. Merchants upload a garment photo + basic details, and the system:
- Uses AI to generate product names, descriptions, 35-50 tags, SEO metadata
- Creates 2 professional product images via virtual try-on
- Automatically assigns to relevant collections
- Creates draft product on Shopify

**Target Users:** Pookie Style admin team  
**Store:** https://pookiestyle.in  
**Use Case:** Rapid product catalog expansion without manual photography/writing

---

## 🏗️ Architecture

### Pipeline Flow (3 API Calls Total)

```
User uploads garment photo
        ↓
[CALL 1] OpenAI GPT-4.1-nano
         ├─ Analyzes image
         ├─ Detects dress_style (traditional/western/fusion/formal)
         └─ Generates: name, description, tags, SEO, collection suggestions
        ↓
[CALL 2] Replicate VTON (Hero)
         ├─ Front-facing full-body shot
         ├─ Smart background (selected based on dress_style)
         └─ Returns: Image 1 (hero-front.jpg)
        ↓
[CALL 3] Replicate VTON (Collage)
         ├─ Single prompt for 6 poses in 3×2 grid
         ├─ Mobile-friendly layout
         ├─ 4 poses + 2 styling variations
         └─ Returns: Image 2 (poses-collage.jpg)
        ↓
[UPLOAD] Shopify API
         ├─ Stage Image 1 & Image 2
         ├─ Create product with variants (by size)
         ├─ Assign tags & SEO metadata
         └─ Assign to collections
        ↓
Product saved as DRAFT in Shopify Admin
```

### Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| **Frontend** | Shopify Liquid + HTML/CSS/JS | Product upload form + UI |
| **Backend** | Python 3.12 | Business logic + orchestration |
| **Hosting** | Google Cloud Functions (Gen 2) | Serverless execution |
| **AI Analysis** | OpenAI GPT-4.1-nano | Text generation + image understanding |
| **Image Generation** | Replicate (VTON models) | Virtual try-on photos |
| **E-commerce** | Shopify GraphQL API | Product creation + management |
| **Storage** | Google Cloud Storage | Model images + backups |

---

## 📱 Frontend UI Details

### URL
```
https://pookiestyle.in/pages/product-upload
```

### How to Access
1. Go to Shopify Admin: https://udfphb-uk.myshopify.com/admin
2. Navigate: **Online Store** → **Pages** → **Create New Product**
3. Or direct link: https://pookiestyle.in/pages/product-upload

### UI Components

#### 1. Image Upload
- Drag & drop zone (accepts JPG, PNG, WebP)
- Max 3 photos per submission
- Max 10 MB per file
- Shows live preview thumbnails
- Remove individual photos

#### 2. Required Fields
- **Selling Price (₹)** — Product price
- **Compare-at Price (₹)** — Original/list price
- **Sizes** — Checkboxes: S, M, L, XL, XXL, Free Size (select 1+)

#### 3. Optional Fields
- **Product Name** — Leave blank for AI to generate
- **Description/Notes** — Help AI understand the garment
- **Category** — Pre-populated with Shopify collections, or let AI auto-detect

#### 4. Extra Styling Prompt
- **Not visible in current UI** (future feature)
- Backend supports `extra_prompt` for custom pose/styling instructions

### UI Behavior

| State | Display |
|---|---|
| **Idle** | Form with all fields visible |
| **Submitting** | Progress bar + animated status messages |
| **Success** | Green checkmark + product name + links to admin/store |
| **Error** | Red error icon + error message + Retry button |

### Progress Messages (Estimated ~84 seconds total)
```
10% → Uploading images...
25% → Analyzing product with AI...
40% → Removing backgrounds...
55% → Generating styled background...
70% → Creating on-model shot...
80% → Writing description & tags...
90% → Creating product on Shopify...
100% → Done!
```

---

## 🔌 Backend API Details

### Endpoint
```
https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product
```

### Deployment Info
- **Status:** ✅ ACTIVE
- **Region:** Asia South 1 (India)
- **Runtime:** Python 3.12
- **Memory:** 512 MB
- **Timeout:** 300 seconds
- **Concurrency:** 1 request per instance
- **Max Instances:** 60
- **Build Status:** ✅ Last built: 2026-03-07 10:37 UTC

### Request Format
```http
POST https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product
Content-Type: multipart/form-data

Form Fields:
  images:              [file, file, file]  (1-3 required)
  price:               "599"                (required)
  compare_at_price:    "999"                (required)
  sizes:               "S,M,L"              (required, comma-separated)
  name:                "Emerald Kurti"      (optional)
  description:         "Cotton..."          (optional)
  category:            "kurti"              (optional)
  extra_prompt:        "traditional pose"   (optional, v2 new)
```

### Response Format (Success)
```json
{
  "success": true,
  "product_name": "Emerald Green Embroidered A-Line Kurti",
  "product_url": "https://pookiestyle.in/products/emerald-green-a-line-kurti",
  "admin_url": "https://udfphb-uk.myshopify.com/admin/products/12345678",
  "images_uploaded": 2,
  "tags_count": 42,
  "collections_assigned": ["kurti", "ethnic-wear"],
  "dress_style": "traditional",
  "ai_analysis": {
    "garment_type": "Kurti",
    "dress_style": "traditional",
    "color": "Emerald Green",
    "fabric": "Cotton",
    "style": "Ethnic",
    "occasion": "daily-wear"
  }
}
```

### Response Format (Error)
```json
{
  "success": false,
  "error": "No images uploaded. At least 1 image is required."
}
```

### Error Codes
| HTTP | Error | Meaning |
|---|---|---|
| 400 | No images uploaded | Upload at least 1 image |
| 400 | Maximum 3 images allowed | Limit is 3 photos |
| 400 | Price and compare-at price are required | Both prices needed |
| 400 | At least one size must be selected | Select 1+ size |
| 500 | Any error during processing | Check logs in GCP |

### API Limits
- **Max file size:** 10 MB per image
- **Max images:** 3 per request
- **Max timeout:** 300 seconds
- **Concurrent requests:** Handled by GCP (up to 60 instances)
- **Rate limit:** None (serverless auto-scales)

---

## 🔐 Credentials & Environment Variables

### Environment Variables (Deployed on GCP)
```yaml
OPENAI_API_KEY: "<REDACTED — stored in GCP .env.yaml>"
REPLICATE_API_TOKEN: "<REDACTED — stored in GCP .env.yaml>"
SHOPIFY_STORE: "udfphb-uk.myshopify.com"
SHOPIFY_ACCESS_TOKEN: "<REDACTED — stored in GCP .env.yaml>"
VTON_MODEL_IMAGE_URL: "https://storage.googleapis.com/pookie-style-uploads/models/indian-model-1.jpg"
```

### Shopify Store Details
- **Store URL:** https://udfphb-uk.myshopify.com
- **Store Domain:** udfphb-uk.myshopify.com
- **Admin URL:** https://udfphb-uk.myshopify.com/admin
- **API Version:** 2026-01
- **Product Visibility:** Draft (manual approval needed)

### API Service Keys
| Service | Key Type | Status | Cost Model |
|---|---|---|---|
| OpenAI | API Key | ✅ Active | ~$0.005 per call |
| Replicate | API Token | ✅ Active | ~$0.01 per call |
| Shopify | Access Token | ✅ Active | Included in plan |
| Google Cloud | Service Account | ✅ Active | Pay-per-use |

### Storage Credentials
- **Google Cloud Project:** pookie-style-automation
- **Project ID:** 751815335949
- **Region:** asia-south1
- **Artifact Registry:** projects/pookie-style-automation/locations/asia-south1/repositories/gcf-artifacts

---

## 💰 Cost Breakdown

### Per-Product Cost (v2 Optimized)

| Service | API Calls | Cost per Call | Total |
|---|---|---|---|
| OpenAI GPT-4.1-nano | 1 | $0.005 | $0.005 |
| Replicate VTON (Hero) | 1 | $0.01 | $0.01 |
| Replicate VTON (Collage) | 1 | $0.01 | $0.01 |
| Shopify API | 3-5 | Free | $0.00 |
| Google Cloud Functions | Compute time | ~$0.001 | $0.001 |
| **Total per product** | | | **~$0.027** |

### Cost Comparison: v1 vs v2

| Aspect | v1 | v2 | Savings |
|---|---|---|---|
| Total API calls | 7 | 3 | 57% fewer |
| Images generated | 4 | 2 | 50% fewer |
| Total cost/product | ~$0.15 | ~$0.03 | **80% cheaper** |
| Photoroom calls | 2 | 0 | Eliminated |
| Processing time | ~120s | ~84s | 30% faster |

### Scaling Costs (100 products/month)
- **v1:** $15
- **v2:** $3
- **Monthly Savings:** $12

---

## 🛠️ Setup Instructions

### For Non-Technical Users (Using the UI)

1. **Access the upload page:**
   - Go to: https://pookiestyle.in/pages/product-upload
   - Or from admin: Online Store → Pages → Create New Product

2. **Configure backend URL (one-time):**
   - Go to Shopify Admin → Online Store → Pages
   - Edit "Create New Product" page
   - Find "Product Creator" section settings
   - Paste backend URL: `https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product`
   - Save

3. **Upload a product:**
   - Upload 1-3 garment photos (JPG/PNG, max 10MB each)
   - Enter selling price & compare-at price
   - Select at least 1 size
   - (Optional) Add product name, description, category
   - Click "🚀 Create Product"
   - Wait for success message

4. **Verify in Shopify:**
   - Click "View in Shopify Admin" link
   - Review product details
   - Adjust if needed
   - Publish when ready

### For Developers (Local Development)

#### Prerequisites
- Python 3.12+
- Git
- gcloud CLI (for GCP deployment)
- API keys (OpenAI, Replicate, Shopify)

#### Local Setup
```bash
# Clone repo
git clone <repo-url>
cd Automation/product-tool

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env.yaml locally (copy .env.yaml.example)
cp .env.yaml.example .env.yaml
# Edit .env.yaml with your API keys

# Run locally (using functions-framework)
functions-framework --target=create_product_handler --debug --port=8080

# Test via curl
curl -X POST http://localhost:8080/create-product \
  -F "images=@test.jpg" \
  -F "price=599" \
  -F "compare_at_price=999" \
  -F "sizes=M,L"
```

#### Deployment
```bash
# From product-tool directory
python deploy_script.py
```

---

## ✅ Testing Procedures

### Test Case 1: Happy Path (Everything Works)
**Input:**
- 1 product photo (high-quality, clear garment)
- Price: 599, Compare-at: 999
- Sizes: M, L
- Category: kurti

**Expected Output:**
- ✅ HTTP 200
- ✅ Product created as DRAFT
- ✅ 2 images uploaded
- ✅ 35-50 tags generated
- ✅ Product assigned to collection

**Time:** ~84 seconds

---

### Test Case 2: Invalid Input (No Images)
**Input:**
- No images
- Price: 599
- Sizes: M

**Expected Output:**
- ✅ HTTP 400
- ✅ Error: "No images uploaded. At least 1 image is required."

---

### Test Case 3: Multiple Images
**Input:**
- 3 product photos
- Price: 1299, Compare-at: 1999
- Sizes: S, M, L, XL
- Name: Custom Lehenga
- Description: Pure silk, embroidered
- Category: suits

**Expected Output:**
- ✅ HTTP 200
- ✅ Product name: "Custom Lehenga" (not AI-generated)
- ✅ Description: Includes user notes + AI-generated details
- ✅ All 4 sizes as variants

---

### Test Case 4: Optional Fields
**Input:**
- 1 image
- Price: 399, Compare-at: 699
- Sizes: Free Size
- (Leave name, description, category blank)

**Expected Output:**
- ✅ HTTP 200
- ✅ AI-generated product name
- ✅ AI-generated description
- ✅ AI-suggested collection

---

### Test Case 5: Extra Prompt (Future)
**Input:**
- 1 image
- All required fields
- Extra prompt: "Show in traditional Indian poses, add floral background"

**Expected Output:**
- ✅ HTTP 200
- ✅ Collage grid respects custom styling

---

## 🔧 Troubleshooting

### Issue: "Backend URL not configured"
**Cause:** Backend URL not set in Shopify page settings  
**Fix:**
1. Go to Shopify Admin → Pages → "Create New Product"
2. Edit the "Product Creator" section
3. Set "Backend URL" to: `https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product`
4. Save

---

### Issue: "Network error"
**Cause:** Backend endpoint unreachable  
**Fix:**
1. Verify backend URL is exactly: `https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product`
2. Check GCP console: Cloud Functions → create-product → Status should be "ACTIVE"
3. Check firewall: Endpoint should be publicly accessible (allow-unauthenticated)

---

### Issue: "OPENAI_API_KEY: PLACEHOLDER_NEED_FROM_USER"
**Cause:** OpenAI key not set in GCP environment  
**Fix:**
1. Update `.env.yaml` with real OpenAI API key
2. Run: `python deploy_script.py`
3. Wait for deployment to complete (~5 minutes)

---

### Issue: "Maximum 3 images allowed"
**Cause:** Uploaded more than 3 files  
**Fix:** Remove extra images using the preview panel

---

### Issue: "Processing time exceeded 300 seconds"
**Cause:** Timeout (rare, can happen with slow APIs)  
**Fix:**
1. Retry with fewer/smaller images
2. Check API status:
   - OpenAI: https://status.openai.com
   - Replicate: https://status.replicate.com
3. Contact support if persists

---

### Issue: Product created but images didn't upload
**Cause:** Shopify API rate limit or image corruption  
**Fix:**
1. Check product in admin: Images might be missing
2. Re-upload images manually to the product
3. Check image file sizes (max 10 MB)

---

### Issue: "dress_style detection failed"
**Cause:** AI couldn't categorize garment  
**Fix:** 
1. Add clear description in "Description/Notes" field
2. Specify category manually
3. Retry with clearer product photo

---

## 📚 Code Structure

```
product-tool/
├── main.py                      # Entry point (Cloud Function)
├── requirements.txt             # Python dependencies
├── deploy_script.py             # Deployment automation
├── .env.yaml                    # API keys (DO NOT COMMIT)
├── .env.yaml.example            # Template
└── services/
    ├── __init__.py
    ├── openai_service.py        # AI text generation + dress_style detection
    ├── replicate_service.py     # Virtual try-on (hero + collage)
    ├── shopify_service.py       # Shopify product creation
    ├── photoroom_service.py     # DEPRECATED (v1 — kept for reference)
    └── image_utils.py           # DEPRECATED (v1 — kept for reference)
```

---

## 📞 Support & Contact

### For Issues:
1. **Check logs:**
   - GCP Console → Cloud Functions → create-product → Logs
   - Filter by timestamp

2. **Check status:**
   - Backend: https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product (POST with empty data should return 400)
   - Shopify: https://status.shopify.com
   - OpenAI: https://status.openai.com
   - Replicate: https://status.replicate.com

3. **Test endpoint:**
   ```bash
   curl -X POST https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product \
     -F "images=@test.jpg" \
     -F "price=599" \
     -F "compare_at_price=999" \
     -F "sizes=M"
   ```

4. **Contact:**
   - GCP Project: pookie-style-automation
   - Support: Check GCP Cloud Function logs
   - Escalation: Shopify support, OpenAI support, Replicate support

---

## 📝 Version History

| Version | Date | Changes |
|---|---|---|
| **2.0** | 2026-03-07 | Cost-optimized (3 API calls, 2 images), dress_style detection, extra_prompt support |
| **1.0** | 2026-02-XX | Initial release (7 API calls, 4 images) |

---

## ✨ Future Enhancements

- [ ] Add extra_prompt UI field for custom styling
- [ ] Support video input (not just photos)
- [ ] Batch product creation (upload CSV)
- [ ] Image editing UI (crop, rotate, filters)
- [ ] A/B testing for product descriptions
- [ ] Multi-language support (Hindi, Bengali, etc.)
- [ ] Webhook notifications (email on completion)
- [ ] Product history & rollback

---

**Generated:** 2026-03-07  
**Status:** ✅ Production Ready  
**Last Updated:** 2026-03-07
