"""
Shopify GraphQL Service
Handles: staged image uploads, product creation, collection assignment.
Uses Shopify Admin GraphQL API v2026-01.
"""

import os
import json
import httpx


SHOPIFY_STORE = os.environ.get("SHOPIFY_STORE", "udfphb-uk.myshopify.com")
SHOPIFY_CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
API_VERSION = "2026-01"
GRAPHQL_URL = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/graphql.json"
TOKEN_URL = f"https://{SHOPIFY_STORE}/admin/oauth/access_token"

# Mutable token — refreshed automatically at runtime when 401 occurs
_token_state = {
    "token": os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
}


def _refresh_token() -> str:
    """
    Regenerate Shopify access token via Client Credentials Grant.
    Called automatically on 401 — no manual intervention needed.
    """
    if not SHOPIFY_CLIENT_ID or not SHOPIFY_CLIENT_SECRET:
        raise Exception(
            "Token expired (401) and SHOPIFY_CLIENT_ID/SHOPIFY_CLIENT_SECRET "
            "are not set — cannot auto-refresh. Update .env.yaml and redeploy."
        )
    response = httpx.post(
        TOKEN_URL,
        json={
            "client_id": SHOPIFY_CLIENT_ID,
            "client_secret": SHOPIFY_CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=15.0,
    )
    response.raise_for_status()
    new_token = response.json().get("access_token", "")
    if not new_token:
        raise Exception("Token refresh returned empty access_token")
    _token_state["token"] = new_token
    print("[shopify] Token auto-refreshed via Client Credentials Grant")
    return new_token


def _graphql(query: str, variables: dict = None, _retry: bool = True) -> dict:
    """Execute a Shopify GraphQL query. Auto-refreshes token on 401."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": _token_state["token"],
    }

    response = httpx.post(
        GRAPHQL_URL,
        headers=headers,
        json=payload,
        timeout=30.0,
    )

    # Auto-refresh and retry once on 401
    if response.status_code == 401 and _retry and SHOPIFY_CLIENT_ID:
        print("[shopify] 401 received — auto-refreshing token...")
        _refresh_token()
        return _graphql(query, variables, _retry=False)

    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        raise Exception(f"GraphQL errors: {json.dumps(data['errors'])}")

    return data.get("data", {})


def upload_image_to_shopify(image_bytes: bytes, filename: str, alt_text: str = "") -> str | None:
    """
    Upload an image to Shopify via staged uploads.

    1. Create a staged upload target
    2. PUT the image to the staged URL
    3. Return the staged upload resource URL for use in product creation

    Args:
        image_bytes: processed image bytes
        filename: image filename
        alt_text: alt text for accessibility

    Returns:
        The resource URL string for use in productCreate, or None on failure
    """
    try:
        # Step 1: Create staged upload
        staged_query = """
        mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
            stagedUploadsCreate(input: $input) {
                stagedTargets {
                    url
                    resourceUrl
                    parameters {
                        name
                        value
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        staged_vars = {
            "input": [
                {
                    "resource": "PRODUCT_IMAGE",
                    "filename": filename,
                    "mimeType": "image/jpeg",
                    "httpMethod": "PUT",
                }
            ]
        }

        staged_data = _graphql(staged_query, staged_vars)
        targets = staged_data.get("stagedUploadsCreate", {}).get("stagedTargets", [])

        if not targets:
            errors = staged_data.get("stagedUploadsCreate", {}).get("userErrors", [])
            print(f"Staged upload errors: {errors}")
            return None

        target = targets[0]
        upload_url = target["url"]
        resource_url = target["resourceUrl"]

        # Step 2: PUT the image to the staged URL
        upload_headers = {}
        for param in target.get("parameters", []):
            if param["name"].lower() == "content-type":
                upload_headers["Content-Type"] = param["value"]

        if "Content-Type" not in upload_headers:
            upload_headers["Content-Type"] = "image/jpeg"

        put_response = httpx.put(
            upload_url,
            content=image_bytes,
            headers=upload_headers,
            timeout=60.0,
        )
        put_response.raise_for_status()

        return resource_url

    except Exception as e:
        print(f"Image upload error: {e}")
        return None


def create_product(
    title: str,
    description_html: str,
    product_type: str,
    vendor: str,
    tags: list,
    sizes: list,
    price: str,
    compare_at_price: str,
    media_ids: list,
    seo_title: str = "",
    seo_description: str = "",
    status: str = "DRAFT",
) -> dict:
    """
    Create a Shopify product with variants, images, tags, and SEO.

    Args:
        title: product title
        description_html: HTML description
        product_type: garment type
        vendor: brand name
        tags: list of tag strings
        sizes: list of size strings (S, M, L, etc.)
        price: selling price
        compare_at_price: original/compare price
        media_ids: list of staged upload resource URLs
        seo_title: SEO title
        seo_description: meta description
        status: ACTIVE or DRAFT

    Returns:
        dict with product_id, handle, numeric_id
    """
    # Build media from staged upload URLs
    media = []
    for url in media_ids:
        media.append(
            {
                "originalSource": url,
                "mediaContentType": "IMAGE",
            }
        )

    # Step 1: Create product WITHOUT variants (removed from ProductCreateInput in API v2024-01+)
    create_mutation = """
    mutation productCreate($product: ProductCreateInput!, $media: [CreateMediaInput!]) {
        productCreate(product: $product, media: $media) {
            product {
                id
                handle
                title
                status
            }
            userErrors {
                field
                message
            }
        }
    }
    """

    create_variables = {
        "product": {
            "title": title,
            "descriptionHtml": description_html,
            "productType": product_type,
            "vendor": vendor,
            "tags": tags,
            "status": status,
            "productOptions": [{"name": "Size", "values": [{"name": s} for s in sizes]}],
            "seo": {
                "title": seo_title,
                "description": seo_description,
            },
        },
        "media": media,
    }

    data = _graphql(create_mutation, create_variables)
    result = data.get("productCreate", {})

    errors = result.get("userErrors", [])
    if errors:
        raise Exception(f"Product creation errors: {json.dumps(errors)}")

    product = result.get("product", {})
    product_gid = product.get("id", "")
    numeric_id = product_gid.split("/")[-1] if product_gid else ""

    # Step 2: Create variants separately via productVariantsBulkCreate (required in API v2024-01+)
    variants_input = []
    for size in sizes:
        variants_input.append(
            {
                "optionValues": [{"optionName": "Size", "name": size}],
                "price": str(price),
                "compareAtPrice": str(compare_at_price),
            }
        )

    variants_mutation = """
    mutation productVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
        productVariantsBulkCreate(productId: $productId, variants: $variants) {
            productVariants {
                id
                title
                price
            }
            userErrors {
                field
                message
            }
        }
    }
    """

    variants_data = _graphql(variants_mutation, {
        "productId": product_gid,
        "variants": variants_input,
    })
    variant_errors = variants_data.get("productVariantsBulkCreate", {}).get("userErrors", [])
    if variant_errors:
        print(f"Variant creation errors (non-fatal): {json.dumps(variant_errors)}")

    return {
        "product_id": product_gid,
        "handle": product.get("handle", ""),
        "numeric_id": numeric_id,
        "title": product.get("title", ""),
        "status": product.get("status", ""),
    }


def get_collection_id_by_handle(handle: str) -> str | None:
    """
    Look up a collection's GID by its handle.

    Args:
        handle: collection handle (e.g., "kurti", "tops")

    Returns:
        Collection GID string, or None if not found
    """
    query = """
    query collectionByHandle($handle: String!) {
        collectionByHandle(handle: $handle) {
            id
            title
        }
    }
    """

    try:
        data = _graphql(query, {"handle": handle})
        collection = data.get("collectionByHandle")
        if collection:
            return collection["id"]
        return None
    except Exception as e:
        print(f"Collection lookup error for '{handle}': {e}")
        return None


def assign_to_collections(product_id: str, collection_id: str) -> bool:
    """
    Add a product to a collection using collectionAddProducts.

    Args:
        product_id: product GID
        collection_id: collection GID

    Returns:
        True if successful
    """
    mutation = """
    mutation collectionAddProducts($id: ID!, $productIds: [ID!]!) {
        collectionAddProducts(id: $id, productIds: $productIds) {
            collection {
                id
                title
            }
            userErrors {
                field
                message
            }
        }
    }
    """

    try:
        data = _graphql(mutation, {"id": collection_id, "productIds": [product_id]})
        errors = data.get("collectionAddProducts", {}).get("userErrors", [])
        if errors:
            print(f"Collection assign errors: {errors}")
            return False
        return True
    except Exception as e:
        print(f"Collection assign error: {e}")
        return False
