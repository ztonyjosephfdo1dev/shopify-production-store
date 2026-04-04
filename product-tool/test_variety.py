"""Test that different products get different bottom pairings."""
import os, json, urllib.request, ssl, base64, sys

sys.path.insert(0, os.path.dirname(__file__))

STORE = os.environ.get("SHOPIFY_STORE", "udfphb-uk.myshopify.com")
CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
API = "2024-10"
ctx = ssl.create_default_context()

def get_token():
    data = json.dumps({"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(f"https://{STORE}/admin/oauth/access_token", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return json.loads(resp.read().decode())["access_token"]

_token = get_token()
print(f"Got Shopify token: shpat_{_token[6:14]}...")

def shopify_get(path):
    url = f"https://{STORE}/admin/api/{API}/{path}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("X-Shopify-Access-Token", _token)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return json.loads(resp.read().decode())

def fetch_image_b64(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return base64.b64encode(resp.read()).decode("ascii")

# 1) Grab 5 products that have images
products = shopify_get("products.json?limit=20&status=active")["products"]
targets = []
for p in products:
    if p.get("images") and len(targets) < 5:
        targets.append({"title": p["title"], "image_url": p["images"][0]["src"]})
print(f"Testing with {len(targets)} products:")
for t in targets:
    print(f"  - {t['title']}")

# 2) Run each through OpenAI analysis
from services.openai_service import analyze_and_generate_text

results = []
for t in targets:
    print(f"\n{'='*60}")
    print(f"Analyzing: {t['title']}")
    b64 = fetch_image_b64(t["image_url"])
    try:
        result = analyze_and_generate_text(
            [{"base64": b64, "content_type": "image/jpeg"}],
            user_name=t["title"]
        )
        mp = result.get("model_prompt", "")
        st = result.get("styling_tip", "")
        dc = result.get("detected_color", "")
        print(f"  Color: {dc}")
        print(f"  Model Prompt (bottom/styling): {mp[:200]}...")
        print(f"  Styling Tip: {st[:150]}")
        results.append({"title": t["title"], "color": dc, "prompt": mp, "tip": st})
    except Exception as e:
        print(f"  ERROR: {e}")

# 3) Check variety
print(f"\n{'='*60}")
print("VARIETY CHECK:")
prompts = [r["prompt"].lower() for r in results]
# Extract bottom mentions
import re
bottom_phrases = []
for i, r in enumerate(results):
    # Look for "paired with X" pattern
    m = re.search(r'paired with\s+(.{20,80}?)(?:,|\.|$)', r["prompt"], re.I)
    phrase = m.group(1).strip() if m else "(no match)"
    bottom_phrases.append(phrase)
    print(f"  {r['title'][:30]:30s} | color={r['color']:15s} | bottom='{phrase[:50]}'")

unique = len(set(bottom_phrases))
print(f"\nUnique pairings: {unique}/{len(bottom_phrases)}")
if unique == len(bottom_phrases):
    print("✅ PASS — All products got different bottom pairings!")
elif unique > 1:
    print("⚠️  PARTIAL — Some variety but not fully unique")
else:
    print("❌ FAIL — All products got the same bottom")
