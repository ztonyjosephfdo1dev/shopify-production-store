"""Fetch and update the Dawn announcement bar text via Shopify GraphQL API."""
import requests, json, base64, os

STORE = "udfphb-uk.myshopify.com"
CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "14a5489a839a93787909313b3955e940")
CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
API_VERSION = "2024-10"
THEME_GID = "gid://shopify/OnlineStoreTheme/135917666402"
TOKEN_URL = f"https://{STORE}/admin/oauth/access_token"
GRAPHQL_URL = f"https://{STORE}/admin/api/{API_VERSION}/graphql.json"

# Get token
r = requests.post(TOKEN_URL, json={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "client_credentials"})
token = r.json()["access_token"]
headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
print(f"[TOKEN] {token[:20]}...")

# --- New announcement text ---
NEW_TEXT = "Free Shipping on orders above \u20b9999 \U0001F69A  |  COD Available \U0001F4B5  |  Easy Returns \U0001F4E6"

# Fetch current header-group.json
FETCH_QUERY = """
query GetFile($id: ID!, $filenames: [String!]!) {
  theme(id: $id) {
    files(filenames: $filenames, first: 1) {
      nodes {
        filename
        body {
          ... on OnlineStoreThemeFileBodyText {
            content
          }
        }
      }
    }
  }
}
"""
resp = requests.post(GRAPHQL_URL, headers=headers, json={
    "query": FETCH_QUERY,
    "variables": {"id": THEME_GID, "filenames": ["sections/header-group.json"]}
})
nodes = resp.json()["data"]["theme"]["files"]["nodes"]
content = nodes[0]["body"]["content"]

# Parse JSON portion (strip leading comment block)
json_start = content.index("{")
comment = content[:json_start]
data = json.loads(content[json_start:])

# Update the announcement text
old_text = data["sections"]["announcement-bar"]["blocks"]["announcement-bar-0"]["settings"]["text"]
data["sections"]["announcement-bar"]["blocks"]["announcement-bar-0"]["settings"]["text"] = NEW_TEXT
print(f"OLD: {old_text.encode('ascii','replace').decode()}")
print(f"NEW: {NEW_TEXT.encode('ascii','replace').decode()}")

# Rebuild full content
new_content = comment + json.dumps(data, indent=2, ensure_ascii=False)

# Push via themeFilesUpsert
UPSERT_MUTATION = """
mutation upsertFile($themeId: ID!, $files: [OnlineStoreThemeFilesUpsertFileInput!]!) {
  themeFilesUpsert(themeId: $themeId, files: $files) {
    upsertedThemeFiles { filename }
    userErrors { filename message }
  }
}
"""
encoded = base64.b64encode(new_content.encode("utf-8")).decode("ascii")
push_resp = requests.post(GRAPHQL_URL, headers=headers, json={
    "query": UPSERT_MUTATION,
    "variables": {
        "themeId": THEME_GID,
        "files": [{"filename": "sections/header-group.json", "body": {"type": "TEXT", "value": new_content}}]
    }
})
result = push_resp.json()
upserted = result.get("data", {}).get("themeFilesUpsert", {}).get("upsertedThemeFiles", [])
errors = result.get("data", {}).get("themeFilesUpsert", {}).get("userErrors", [])
if upserted:
    print(f"[OK] Updated: {upserted[0]['filename']}")
else:
    print(f"[ERR] {errors}")
