# VTON Pipeline — Debugging Report

## Date: March 8, 2025

---

## Executive Summary

The Virtual Try-On (VTON) image generation was failing silently, returning only the raw uploaded image instead of AI-generated poses. Root cause analysis identified **two critical issues**:

1. **Replicate Rate Limit**: Account credit below $5 triggers strict rate limiting
2. **Model Image 404**: Reference model image URL was returning Not Found

---

## Issue #1: Replicate Rate Limit (429)

### Symptoms
```
textPayload: [p-tryon] 429: rate limit; burst=1, sustained=1
textPayload: Your rate limit is reduced while you have less than $5.0 in credit
```

### Root Cause
- Replicate account `pookie_style` has $1.00 credit
- Accounts with less than $5 have severely restricted rate limits:
  - Burst limit: 1 request
  - Sustained limit: 1 request/second
- This causes 429 errors even with no concurrent requests

### Solution
**User action required**: Add $4+ more credit to Replicate (total ≥$5)

Steps:
1. Go to https://replicate.com/pookie_style/billing
2. Add credit card if not already done
3. Add funds (minimum $4 more, recommend $10 for buffer)
4. Credits unlock immediately

---

## Issue #2: Model Image 404

### Symptoms
```
textPayload: [idm-vton] ERROR: 404 Client Error: Not Found for url: 
    https://storage.googleapis.com/pookie-style-uploads/models/indian-model-1.jpg
```

### Root Cause
- Code referenced a GCS bucket URL that doesn't exist
- The model reference image (a person to wear the garment) was never uploaded to GCS
- Fallback model (cuuupid/idm-vton) also failed because it uses the same broken URL

### Solution Applied
Updated `replicate_service.py` with fallback URLs:

```python
MODEL_IMAGE_URLS = [
    # Primary: our GCS bucket (when uploaded)
    "https://storage.googleapis.com/pookie-style-uploads/models/indian-model-1.jpg",
    # Fallback 1: Professional Indian woman portrait (Unsplash)
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=1024&h=1024&fit=crop",
    # Fallback 2: Fashion model pose (Unsplash)  
    "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=1024&h=1024&fit=crop",
    # Fallback 3: Studio portrait (Unsplash)
    "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=1024&h=1024&fit=crop",
]
```

Added `_get_valid_model_image()` function that:
1. Tests each URL with a HEAD request
2. Returns the first URL that responds with 200 OK
3. Returns `None` if all URLs fail (prevents wasted API calls)

---

## Code Changes Summary

### File: `product-tool/services/replicate_service.py`

| Change | Description |
|--------|-------------|
| `MODEL_IMAGE_URLS` | Added list of 4 fallback model image URLs |
| `_log()` | New helper for `[REPLICATE]` prefixed logging |
| `_validate_url()` | New function to test URL availability |
| `_get_valid_model_image()` | New function to find first working URL |
| `_try_replicate()` | Enhanced with error type classification |
| `_run_vton()` | Now validates model image before API call |

### New Logging Format
All Replicate service logs now follow this pattern:
```
[REPLICATE] [COMPONENT] Message with details
```

Examples:
```
[REPLICATE] [VTON] Starting virtual try-on pipeline...
[REPLICATE] [VTON] API token present (starts with r8_U3qLr...)
[REPLICATE] [URL-CHECK] Testing: https://storage.googleapis.com/...
[REPLICATE] [URL-CHECK] ✓ URL valid (200 OK)
[REPLICATE] [p-tryon] Running model prunaai/p-tryon...
[REPLICATE] [p-tryon] ✓ Success in 28.4s
[REPLICATE] [VTON] SUCCESS: Downloaded 245780 bytes
```

---

## Error Classification

The updated `_try_replicate()` now classifies errors:

| Error Code | Type | Description | Recommended Action |
|------------|------|-------------|-------------------|
| 429 + "$5" | `RATE_LIMIT_429_NEED_$5_CREDIT` | Need more Replicate credit | Add $5+ credit |
| 429 | `RATE_LIMIT_429` | Rate limited | Wait and retry |
| 422 | `VALIDATION_ERROR_422` | Invalid input params | Check API docs |
| 401/403 | `AUTH_ERROR` | Bad API token | Regenerate token |
| 404 | `NOT_FOUND_404` | Model/URL not found | Check model name |
| 5xx | `SERVER_ERROR` | Replicate server issue | Retry later |

---

## Deployment History

| Version | Date | Changes |
|---------|------|---------|
| v4.0 | Mar 7 | 4-pose grid pipeline (grid→halves→upscale→crop) |
| v4.1 | Mar 8 | Fixed p-tryon input field (`clothing_images`) |
| v4.2 | Mar 8 | Replaced dead vella-1.5 with cuuupid/idm-vton |
| v4.3 | Mar 8 | New Replicate token (pookie_style org) |
| v4.4 | Mar 8 | Fallback model URLs + comprehensive logging |

---

## Testing Checklist

After adding Replicate credit, test with these steps:

1. [ ] Open product creator: https://pookie-style-automation.myshopify.com/pages/product-upload
2. [ ] Upload a garment image (preferably upper body clothing)
3. [ ] Fill in product name and select style
4. [ ] Click "Generate Preview"
5. [ ] Wait ~60 seconds for VTON generation
6. [ ] Should see 4 AI-generated pose images instead of raw upload

### Verifying in GCP Logs
```bash
gcloud functions logs read create-product --region=asia-south1 --limit=50 2>&1 | grep "\[REPLICATE\]"
```

Expected success logs:
```
[REPLICATE] [VTON] Starting virtual try-on pipeline...
[REPLICATE] [VTON] API token present (starts with r8_U3qLr...)
[REPLICATE] [URL-CHECK] ✓ URL valid (200 OK)
[REPLICATE] [p-tryon] Running model prunaai/p-tryon...
[REPLICATE] [p-tryon] ✓ Success in X.Xs
[REPLICATE] [VTON] SUCCESS: Downloaded XXXXX bytes
```

---

## Cost Analysis (Per Product)

| Step | API Call | Cost |
|------|----------|------|
| 4-Pose Grid | VTON (1 call) | $0.010 |
| Upscale Top Half | Real-ESRGAN | $0.001 |
| Upscale Bottom Half | Real-ESRGAN | $0.001 |
| **Total** | | **$0.012** |

---

## Accounts Reference

See [accounts.md](./accounts.md) for all service credentials and metadata.

| Service | Account | Credit Required |
|---------|---------|-----------------|
| Replicate | pookie_style (org) | **$5+ minimum** |
| OpenAI | pookiestyle0 | $10 (sufficient) |
| Shopify | pookie-style-automation | Free tier |

---

## Next Steps

1. **Immediate**: Add $4+ to Replicate billing
2. **Short-term**: Upload actual Indian model reference image to GCS
3. **Medium-term**: Add retry logic with exponential backoff
4. **Long-term**: Consider caching model images locally in Cloud Function
