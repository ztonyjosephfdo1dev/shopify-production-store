"""
Shopify GraphQL Service
Handles: staged image uploads, product creation, collection assignment.
Uses Shopify Admin GraphQL API v2026-01.
"""

import os
import json
import httpx


SHOPIFY_STORE = os.environ.get("SHOPIFY_STORE", "udfphb-uk.myshopify.com")
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
API_VERSION = "2026-01"
GRAPHQL_URL = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/graphql.json"

HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": SHOPIFY_TOKEN,
}


def _graphql(query: str, variables: dict = None) -> dict:
    """Execute a Shopify GraphQL query."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = httpx.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json=payload,
        timeout=30.0,
    )
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
    # Build variants (one per size)
    variants = []
    for size in sizes:
        variants.append(
            {
                "optionValues": [{"optionName": "Size", "name": size}],
                "price": str(price),
                "compareAtPrice": str(compare_at_price),
            }
        )

    # Build media from staged upload URLs
    media = []
    for url in media_ids:
        media.append(
            {
                "originalSource": url,
                "mediaContentType": "IMAGE",
            }
        )

    mutation = """
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

    variables = {
        "product": {
            "title": title,
            "descriptionHtml": description_html,
            "productType": product_type,
            "vendor": vendor,
            "tags": tags,
            "status": status,
            "productOptions": [{"name": "Size", "values": [{"name": s} for s in sizes]}],
            "variants": variants,
            "seo": {
                "title": seo_title,
                "description": seo_description,
            },
        },
        "media": media,
    }

    data = _graphql(mutation, variables)
    result = data.get("productCreate", {})

    errors = result.get("userErrors", [])
    if errors:
        raise Exception(f"Product creation errors: {json.dumps(errors)}")

    product = result.get("product", {})
    product_gid = product.get("id", "")
    # Extract numeric ID from GID (e.g., "gid://shopify/Product/12345" -> "12345")
    numeric_id = product_gid.split("/")[-1] if product_gid else ""

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
