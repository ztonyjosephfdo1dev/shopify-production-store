# Smart Collage Architecture — Fashion-Aware Zoom Panels

## Overview

**Photo 1**: Primary hero shot — full VTON model wearing garment (front view, full frame)
**Photo 2**: 6-panel collage — smart zoom crops from VTON front + side/back images

**Cost**: $0.00 extra — collage is 100% local PIL processing from existing VTON output.

---

## VTON Image Anatomy (Reference)

A typical `idm-vton` output (768×1024px) has consistent body layout:

```
 0% ┌────────────────┐
    │    Head/Hair    │
10% ├────────────────┤
    │ Neck/Shoulders  │
15% ├────────────────┤
    │  Chest / Bust   │
30% ├────────────────┤
    │   Midriff       │
40% ├────────────────┤
    │  Waist / Hips   │
50% ├────────────────┤
    │  Upper Thighs   │
60% ├────────────────┤
    │   Thigh–Knee    │
75% ├────────────────┤
    │  Calf–Ankle     │
90% ├────────────────┤
    │     Feet        │
100%└────────────────┘
```

All crop percentages below are `(left%, top%, right%, bottom%)` of the source image.

---

## Garment-Specific Crop Maps

### 1. Upper Body — `top, t-shirt, shirt, casual-top, korean-top`

**Buyer inspects:** Neckline shape, sleeve length, overall fit, hem length, back design.

| Panel | Source | Crop `(L%, T%, R%, B%)` | Shows |
|-------|--------|------------------------|-------|
| 1 | Front | `(0, 0, 100, 100)` | Full front look |
| 2 | Side | `(0, 0, 100, 100)` | Full side/back look |
| 3 | Front | `(5, 5, 95, 55)` | Shoulders-to-waist fit |
| 4 | Side | `(5, 5, 95, 55)` | Back view upper half |
| 5 | Front | `(10, 8, 90, 38)` | Neckline close-up |
| 6 | Front | `(5, 25, 95, 55)` | Hem & fit detail |

### 2. Crop Top — `crop-top, fancy-crop-top`

**Buyer inspects:** Exact crop length, midriff exposure, sleeve detail, neckline.

| Panel | Source | Crop | Shows |
|-------|--------|------|-------|
| 1 | Front | `(0, 0, 100, 100)` | Full body — midriff visible |
| 2 | Side | `(0, 0, 100, 100)` | Side/back — back length |
| 3 | Front | `(5, 8, 95, 50)` | The crop zone — cut line visible |
| 4 | Side | `(5, 8, 95, 50)` | Back crop line |
| 5 | Front | `(10, 8, 90, 32)` | Neckline + sleeves |
| 6 | Front | `(10, 28, 90, 52)` | Crop line detail — where it ends |

### 3. Kurti — `kurti, kurti-set`

**Buyer inspects:** Neck embroidery, sleeve detail, length, side slit, back yoke.

| Panel | Source | Crop | Shows |
|-------|--------|------|-------|
| 1 | Front | `(0, 0, 100, 100)` | Full front — complete length |
| 2 | Side | `(0, 0, 100, 100)` | Side profile — drape |
| 3 | Front | `(10, 8, 90, 35)` | Neckline/yoke embroidery |
| 4 | Front | `(5, 10, 95, 55)` | Chest-to-waist fit |
| 5 | Front | `(5, 55, 95, 95)` | Hem & length — border detail |
| 6 | Side | `(5, 10, 95, 60)` | Back design — yoke, zip |

### 4. Lower Body — `skirt, palazzo, jeans, trousers, pants, shorts, leggings`

**Buyer inspects:** Waistband, drape/flare, hem design, back fit, leg silhouette.

| Panel | Source | Crop | Shows |
|-------|--------|------|-------|
| 1 | Front | `(0, 0, 100, 100)` | Full body for proportion |
| 2 | Side | `(0, 0, 100, 100)` | Side silhouette |
| 3 | Front | `(5, 35, 95, 95)` | Full bottom zoom |
| 4 | Side | `(5, 35, 95, 95)` | Side drape / jean fit |
| 5 | Front | `(10, 35, 90, 55)` | Waistband close-up |
| 6 | Front | `(5, 70, 95, 98)` | Hem detail |

### 5. Dress — `single-piece, bodycon, maxi, casual-maxi`

**Buyer inspects:** Bodice design, waist definition, skirt fullness, hem, back.

| Panel | Source | Crop | Shows |
|-------|--------|------|-------|
| 1 | Front | `(0, 0, 100, 100)` | Complete silhouette |
| 2 | Side | `(0, 0, 100, 100)` | Side drape & back |
| 3 | Front | `(5, 5, 95, 45)` | Bodice — neckline + waist |
| 4 | Side | `(5, 5, 95, 50)` | Back detail — zip, cut-out |
| 5 | Front | `(5, 45, 95, 95)` | Skirt — flare, pleats |
| 6 | Front | `(10, 70, 90, 98)` | Hem close-up |

### 6. Gown — `gown`

**Buyer inspects:** Bodice embellishment, waist cinch, skirt volume, back design.

| Panel | Source | Crop | Shows |
|-------|--------|------|-------|
| 1 | Front | `(0, 0, 100, 100)` | Majestic full-length |
| 2 | Side | `(0, 0, 100, 100)` | Side/back dramatic view |
| 3 | Front | `(5, 5, 95, 40)` | Bodice / embellishment |
| 4 | Side | `(5, 5, 95, 45)` | Back design — open back, lace-up |
| 5 | Front | `(0, 50, 100, 100)` | Skirt volume — layers, flare |
| 6 | Front | `(10, 8, 90, 35)` | Neckline — sweetheart, halter |

### 7. Saree — `saree` (3 visual zones: blouse, pleats, pallu)

| Panel | Source | Crop | Shows |
|-------|--------|------|-------|
| 1 | Front | `(0, 0, 100, 100)` | Full drape |
| 2 | Side | `(0, 0, 100, 100)` | Pallu drape from behind |
| 3 | Front | `(5, 5, 95, 38)` | Blouse + pallu |
| 4 | Side | `(5, 5, 95, 45)` | Pallu back drape |
| 5 | Front | `(5, 32, 95, 62)` | Pleats — tucked section |
| 6 | Front | `(0, 60, 100, 100)` | Border & fall |

### 8. Coord Set — `cord-set, co-ord` (top + bottom shown separately)

| Panel | Source | Crop | Shows |
|-------|--------|------|-------|
| 1 | Front | `(0, 0, 100, 100)` | Full set together |
| 2 | Side | `(0, 0, 100, 100)` | Side view of complete set |
| 3 | Front | `(5, 5, 95, 50)` | Top piece only |
| 4 | Front | `(5, 40, 95, 98)` | Bottom piece only |
| 5 | Front | `(10, 8, 90, 35)` | Top detail — neckline, print |
| 6 | Side | `(5, 35, 95, 95)` | Bottom from behind |

### 9. Lehenga — `lehenga` (3 pieces: choli + skirt + dupatta)

| Panel | Source | Crop | Shows |
|-------|--------|------|-------|
| 1 | Front | `(0, 0, 100, 100)` | Full ensemble |
| 2 | Side | `(0, 0, 100, 100)` | Side — skirt flare visible |
| 3 | Front | `(5, 5, 95, 40)` | Choli — embroidery, cut |
| 4 | Front | `(0, 40, 100, 100)` | Lehenga skirt — flare |
| 5 | Front | `(10, 8, 90, 32)` | Choli neckline detail |
| 6 | Side | `(5, 5, 95, 50)` | Back design — dori, open back |

### 10. Anarkali / Sharara — `anarkali, sharara`

| Panel | Source | Crop | Shows |
|-------|--------|------|-------|
| 1 | Front | `(0, 0, 100, 100)` | Full flare visible |
| 2 | Side | `(0, 0, 100, 100)` | Side silhouette — flare |
| 3 | Front | `(5, 5, 95, 40)` | Bodice embroidery |
| 4 | Side | `(5, 5, 95, 45)` | Back detail — closure |
| 5 | Front | `(0, 50, 100, 100)` | Flare/skirt volume |
| 6 | Front | `(10, 8, 90, 32)` | Neckline — keyhole, round, V |

---

## Collage Layout

```
┌──────────┬──────────┐
│ Panel 1  │ Panel 2  │
│ (480×640)│ (480×640)│
├──────────┼──────────┤
│ Panel 3  │ Panel 4  │
│ (480×640)│ (480×640)│
├──────────┼──────────┤
│ Panel 5  │ Panel 6  │
│ (480×640)│ (480×640)│
└──────────┴──────────┘
  Total: 968 × 1936 px
  8px gap between panels
  Background: #F5F5F5
```

## Pipeline Flow

```
VTON Call 1 → Front View image ($0.024)
VTON Call 2 → Side/Back image  ($0.024)
      ↓
PIL (local, $0.00):
  ├── Photo 1: Front View (hero, as-is)
  └── Photo 2: build_smart_collage(front, side, garment_type)
            → 6 panels from garment-specific crop map
      ↓
2 photos → Shopify product
Total: ~$0.048/product
```
