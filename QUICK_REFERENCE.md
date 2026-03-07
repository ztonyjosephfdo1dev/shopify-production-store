# 🎯 Pookie Style v2 — Quick Reference Card

## 🚀 Go-Live Checklist

- [x] Backend deployed to GCP
- [x] Frontend integrated with Shopify
- [x] API credentials configured
- [x] Cost optimized (3 calls, 2 images)
- [x] Testing ready

---

## 📱 **User Access (Customer-Facing)**

| What | URL |
|---|---|
| **Product Upload Page** | https://pookiestyle.in/pages/product-upload |
| **Shopify Admin** | https://udfphb-uk.myshopify.com/admin |
| **Storefront** | https://pookiestyle.in |

---

## 🔌 **Backend Endpoint**

```
https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product
```

**Status:** ✅ ACTIVE  
**Method:** POST  
**Content-Type:** multipart/form-data  

---

## 🔑 **Critical Credentials**

### API Keys (Deployed on GCP)
```
OPENAI_API_KEY:         <REDACTED — stored in GCP .env.yaml>
REPLICATE_API_TOKEN:    <REDACTED — stored in GCP .env.yaml>
SHOPIFY_ACCESS_TOKEN:   <REDACTED — stored in GCP .env.yaml>
SHOPIFY_STORE:          udfphb-uk.myshopify.com
```

### Storage Location
- **Local:** `c:\Users\ADMIN\Documents\pookie style\projects\Automation\product-tool\.env.yaml`
- **GCP:** Cloud Functions environment variables
- **⚠️ SECURITY:** `.env.yaml` is gitignored (do NOT commit)

---

## 📊 **API Calls & Cost**

### Per Product
| Step | Service | Calls | Cost |
|---|---|---|---|
| 1 | OpenAI (text) | 1 | $0.005 |
| 2 | Replicate (hero) | 1 | $0.01 |
| 3 | Replicate (collage) | 1 | $0.01 |
| **Total** | | **3** | **$0.025** |

### Expected Volume
- 100 products/month: **$2.50**
- 1,000 products/month: **$25**
- Savings vs v1: **80% cheaper**

---

## 📝 **Request Format**

```bash
curl -X POST https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product \
  -F "images=@photo.jpg" \
  -F "price=599" \
  -F "compare_at_price=999" \
  -F "sizes=S,M,L" \
  -F "name=Custom Kurti" \
  -F "description=Cotton, embroidered" \
  -F "category=kurti" \
  -F "extra_prompt=traditional poses"
```

---

## ✅ **Success Response**

```json
{
  "success": true,
  "product_name": "Emerald Green Embroidered A-Line Kurti",
  "product_url": "https://pookiestyle.in/products/...",
  "admin_url": "https://udfphb-uk.myshopify.com/admin/products/...",
  "images_uploaded": 2,
  "tags_count": 42,
  "dress_style": "traditional"
}
```

---

## ❌ **Error Response**

```json
{
  "success": false,
  "error": "No images uploaded. At least 1 image is required."
}
```

---

## 🔍 **Monitoring & Logs**

### View Logs
1. Go to: https://console.cloud.google.com/functions
2. Select: **create-product** function
3. Click: **Logs**
4. Filter by timestamp

### Check Status
```bash
# Function status
gcloud functions describe create-product \
  --region=asia-south1 \
  --gen2

# Recent deployments
gcloud functions list \
  --region=asia-south1
```

---

## 🛠️ **Common Issues & Fixes**

| Issue | Fix |
|---|---|
| Network error | Check backend URL is exactly: `https://asia-south1-pookie-style-automation.cloudfunctions.net/create-product` |
| Backend URL not set | Shopify Admin → Pages → Edit "Create New Product" → Set Backend URL field |
| OpenAI key placeholder | Update `.env.yaml` → Run `python deploy_script.py` |
| Image size too large | Max 10 MB per image; compress before upload |
| Timeout (>300s) | Retry; check OpenAI/Replicate status pages |
| Product created but no images | Manually upload images to Shopify product |

---

## 🚀 **Quick Start Testing**

### Test 1: Happy Path (5 min)
1. Go to: https://pookiestyle.in/pages/product-upload
2. Upload a garment photo
3. Enter: Price 599, Compare-at 999, Size M
4. Click: Create Product
5. Verify: ✅ Product appears in Shopify Admin as Draft

### Test 2: Verify AI Analysis (3 min)
1. Check success response
2. Verify: `dress_style` is detected (traditional/western/fusion/formal)
3. Verify: 35-50 tags generated
4. Verify: Description & SEO metadata

### Test 3: Check Image Quality (2 min)
1. View product in Shopify
2. Check: Hero image (front, clear, professional)
3. Check: Collage grid (6 poses, mobile-friendly)

---

## 📞 **Support**

| Problem | Where to Look |
|---|---|
| Function error | GCP Cloud Functions Logs |
| Product creation failed | GCP error message + Shopify API status |
| API rate limit | Check OpenAI/Replicate dashboards |
| Shopify issues | Shopify Admin → Settings → Notifications |

---

## 📚 **Full Documentation**

For complete details, see: `DEPLOYMENT_COMPLETE.md`

---

**Last Updated:** 2026-03-07  
**Status:** ✅ Production Ready  
**Cost per Product:** ~$0.025
