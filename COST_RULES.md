# 🔒 COST RULES — Pookie Style (MANDATORY REFERENCE)

**Read this file BEFORE making ANY change to API calls, models, or image generation.**

## Rule 1: NEVER increase API calls without owner approval
- Virtual try-on (Pookie Mirror): **1 API call per generation** (Gemini free tier, $0)
  - Single grid call: identity-preserving 6-pose grid → math-crop into 6 panels
- Product image grid: **1 API call per product** — NEVER more
- Store homepage images: **1 API call per image** — already generated, don't regenerate
- NEVER add more calls beyond the above without owner approval

## Rule 2: NEVER change models without asking
- Current image model: Gemini (free tier via AI Studio API key)
- NEVER switch to paid models (OpenAI DALL-E, FASHN.ai, Replicate, etc.)
- NEVER add additional model calls "for better quality"
- If a model change is needed, PRESENT OPTIONS with cost breakdown FIRST

## Rule 3: Cost per customer try-on must stay low
- Gemini AI Studio: ~$0.039/image (gemini-2.5-flash) or ~$0.067/image (gemini-3.1-flash)
- Budget is extremely limited — every cent matters

## Rule 4: Quality vs Cost tradeoff
- Medium quality is GOOD ENOUGH — don't chase perfection at higher cost
- Try-on: 1 grid call (free tier) → 6 panels with customer's face preserved
- Product grid: 1 API call returning 1 grid image
- NO retry loops that multiply cost
- If generation fails, fail gracefully — don't retry 5 times silently

## Rule 5: Always consult before
- Adding new API integrations
- Changing request frequency or batch sizes
- Any architectural change that could increase per-customer cost
- Switching from free tier to paid tier on any service

## Current Architecture (March 2026)
| Feature | API Calls | Model | Cost |
|---------|-----------|-------|------|
| Virtual Try-On | 1 call (grid) | gemini-3.1-flash-image-preview / gemini-2.5-flash-image | ~$0.04-0.07 per generation |
| Product Grid | 1 call, 1 grid image | gemini-2.5-flash-image | ~$0.04 |
| Text Analysis | 1 call | gpt-4.1-mini | ~$0.001 |
| Store Images | 12 calls total (one-time) | gemini-2.5-flash-image | ~$0.48 total |

---
**Owner rule: "its not your money its my money" — respect this always.**
