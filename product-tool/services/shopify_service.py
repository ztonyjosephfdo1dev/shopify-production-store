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


# ---- Taxonomy & Inventory helpers (best-effort, non-blocking) ----

_taxonomy_cache: dict = {}


def _resolve_taxonomy_id(category: str, garment_type: str) -> str | None:
    """
    Best-effort Shopify Standard Product Taxonomy lookup.
    Queries the taxonomy search API. Returns None if no match.
    Product creation proceeds without category on failure.
    """
    KEYWORD_MAP = {
        # Category handles
        "kurti": "Kurta", "kurti-set": "Kurta", "suits": "Suits",
        "indo-western": "Dresses", "top-wear": "Shirts & Tops",
        "tops": "Shirts & Tops", "casual-top": "Shirts & Tops",
        "korean-top": "Shirts & Tops", "shirt": "Shirts & Tops",
        "blouse": "Shirts & Tops", "bodycon": "Dresses",
        "fancy-crop-top": "Shirts & Tops", "single-piece": "Dresses",
        "gown": "Dresses", "maxi": "Dresses", "casual-maxi": "Dresses",
        "cord-set": "Clothing Sets", "bottom": "Pants",
        "plazo": "Pants", "skirt": "Skirts", "inners": "Underwear",
        "skin-care": "Skin Care", "face-wash": "Skin Care",
        "body-lotion": "Skin Care",
        # Detected garment types (from OpenAI)
        "crop top": "Shirts & Tops", "crop-top": "Shirts & Tops",
        "top": "Shirts & Tops", "t-shirt": "Shirts & Tops",
        "dress": "Dresses", "palazzo": "Pants",
    }

    key = (category or "").lower().strip()
    keyword = KEYWORD_MAP.get(key, "")
    if not keyword and garment_type:
        keyword = KEYWORD_MAP.get(garment_type.lower().strip(), "")
    if not keyword:
        return None

    if keyword in _taxonomy_cache:
        return _taxonomy_cache[keyword]

    try:
        data = _graphql(
            "query($q:String!){taxonomy{categories(first:1,search:$q){nodes{id name fullName}}}}",
            {"q": keyword},
        )
        nodes = data.get("taxonomy", {}).get("categories", {}).get("nodes", [])
        if nodes:
            tid = nodes[0]["id"]
            _taxonomy_cache[keyword] = tid
            print(f"[shopify] Taxonomy: '{keyword}' \u2192 {nodes[0].get('fullName','')} ({tid})")
            return tid
        print(f"[shopify] No taxonomy match for '{keyword}'")
    except Exception as e:
        print(f"[shopify] Taxonomy lookup skipped: {e}")
    return None


_location_cache: dict = {"id": None}


def _get_default_location() -> str | None:
    """Get the store's first (default) inventory location. Cached per instance."""
    if _location_cache["id"]:
        return _location_cache["id"]
    try:
        # Only query 'id' — 'name' requires read_locations scope
        data = _graphql("{ locations(first:1) { nodes { id } } }")
        nodes = data.get("locations", {}).get("nodes", [])
        if nodes:
            _location_cache["id"] = nodes[0]["id"]
            print(f"[shopify] Default location: {nodes[0]['id']}")
            return _location_cache["id"]
    except Exception as e:
        print(f"[shopify] Location lookup failed: {e}")
    return None


def _activate_and_set_inventory(variant_nodes: list, quantity: int = 1) -> None:
    """
    Enable inventory tracking + set quantities at the default location.
    Shopify creates products with tracked=false by default, so we must:
    1. Enable tracking on each inventory item (inventoryItemUpdate)
    2. Set quantity via inventorySetQuantities with ignoreCompareQuantity=true
    """
    location_id = _get_default_location()
    if not location_id:
        print("[shopify] Skipping inventory — no location found")
        return

    # Collect inventory item IDs
    inv_items = []
    for v in variant_nodes:
        inv_item = v.get("inventoryItem", {})
        inv_id = inv_item.get("id") if inv_item else None
        if inv_id:
            inv_items.append(inv_id)

    if not inv_items:
        print("[shopify] Skipping inventory — no inventory item IDs")
        return

    # Step 1: Enable tracking on each inventory item
    for inv_id in inv_items:
        try:
            track_data = _graphql(
                """mutation invTrack($id: ID!, $input: InventoryItemInput!) {
                    inventoryItemUpdate(id: $id, input: $input) {
                        inventoryItem { id tracked }
                        userErrors { field message }
                    }
                }""",
                {"id": inv_id, "input": {"tracked": True}},
            )
            track_errors = track_data.get("inventoryItemUpdate", {}).get("userErrors", [])
            if track_errors:
                print(f"[shopify] Tracking enable errors for {inv_id}: {json.dumps(track_errors)}")
            else:
                print(f"[shopify] Tracking enabled: {inv_id} ✓")
        except Exception as e:
            print(f"[shopify] Tracking enable failed for {inv_id}: {e}")

    # Step 2: Set quantities
    quantities = []
    for inv_id in inv_items:
        quantities.append({
            "inventoryItemId": inv_id,
            "locationId": location_id,
            "quantity": quantity,
        })

    try:
        data = _graphql(
            """mutation inventorySet($input: InventorySetQuantitiesInput!) {
                inventorySetQuantities(input: $input) {
                    inventoryAdjustmentGroup { changes { name delta } }
                    userErrors { field message }
                }
            }""",
            {
                "input": {
                    "name": "available",
                    "reason": "correction",
                    "ignoreCompareQuantity": True,
                    "quantities": quantities,
                }
            },
        )
        errors = data.get("inventorySetQuantities", {}).get("userErrors", [])
        if errors:
            print(f"[shopify] Inventory set errors: {json.dumps(errors)}")
        else:
            print(f"[shopify] Inventory set: {len(quantities)} items × {quantity} units ✓")
    except Exception as e:
        print(f"[shopify] Inventory set failed (non-fatal): {e}")


def _publish_to_channels(product_gid: str) -> None:
    """
    Publish a product to all available sales channels (publications).
    Queries all publications and publishes the product to each one.
    Best-effort: logs failures but doesn't block product creation.
    """
    try:
        # Query all available publications (sales channels)
        pub_data = _graphql(
            """query {
                publications(first: 50) {
                    nodes {
                        id
                        name
                    }
                }
            }"""
        )
        publications = pub_data.get("publications", {}).get("nodes", [])
        if not publications:
            print("[shopify] No publications found — skipping channel publish")
            return

        print(f"[shopify] Found {len(publications)} publications: {[p.get('name','?') for p in publications]}")

        # Build publication inputs for publishablePublish
        publication_inputs = [{"publicationId": p["id"]} for p in publications]

        publish_data = _graphql(
            """mutation publishProduct($id: ID!, $input: [PublicationInput!]!) {
                publishablePublish(id: $id, input: $input) {
                    publishable {
                        ... on Product {
                            id
                            title
                        }
                    }
                    userErrors {
                        field
                        message
                    }
                }
            }""",
            {"id": product_gid, "input": publication_inputs},
        )
        pub_errors = publish_data.get("publishablePublish", {}).get("userErrors", [])
        if pub_errors:
            print(f"[shopify] Publish errors (non-fatal): {json.dumps(pub_errors)}")
        else:
            print(f"[shopify] Published to {len(publications)} channels successfully")

    except Exception as e:
        print(f"[shopify] Channel publish failed (non-fatal): {e}")


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
    category: str = "",
    inventory_quantity: int = 1,
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
        media_ids: list of (resource_url, alt_text) tuples or plain URL strings
        seo_title: SEO title
        seo_description: meta description
        status: ACTIVE or DRAFT

    Returns:
        dict with product_id, handle, numeric_id
    """
    # Build media from staged upload URLs
    media = []
    for item in media_ids:
        if isinstance(item, tuple):
            url, alt = item
        else:
            url, alt = item, title
        media.append(
            {
                "originalSource": url,
                "alt": alt,
                "mediaContentType": "IMAGE",
            }
        )

    # Step 1: Create product WITH productOptions (creates first variant only)
    create_mutation = """
    mutation productCreate($product: ProductCreateInput!, $media: [CreateMediaInput!]) {
        productCreate(product: $product, media: $media) {
            product {
                id
                handle
                title
                status
                options {
                    id
                    name
                }
                variants(first: 30) {
                    nodes {
                        id
                        title
                        inventoryItem {
                            id
                        }
                    }
                }
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

    # Resolve taxonomy ID for later (set via productUpdate after creation)
    taxonomy_id = _resolve_taxonomy_id(category, product_type)

    data = _graphql(create_mutation, create_variables)
    result = data.get("productCreate", {})

    errors = result.get("userErrors", [])
    if errors:
        raise Exception(f"Product creation errors: {json.dumps(errors)}")

    product = result.get("product", {})
    product_gid = product.get("id", "")
    numeric_id = product_gid.split("/")[-1] if product_gid else ""

    # Set product category via productCategoryUpdate (dedicated mutation for API v2026-01)
    if taxonomy_id and product_gid:
        try:
            _graphql(
                """mutation productUpdate($product: ProductUpdateInput!) {
                    productUpdate(product: $product) {
                        product { id }
                        userErrors { field message }
                    }
                }""",
                {
                    "product": {
                        "id": product_gid,
                        "productCategory": {
                            "productTaxonomyNodeId": taxonomy_id,
                        },
                    }
                },
            )
            print(f"[shopify] Product category set: {taxonomy_id}")
        except Exception as e:
            print(f"[shopify] Product category set failed (non-fatal): {e}")

    # Step 2: Create remaining variants via productVariantsBulkCreate
    # (productCreate only creates the FIRST variant; extra sizes need explicit creation)
    variant_nodes = product.get("variants", {}).get("nodes", [])
    if not variant_nodes:
        print("[shopify] WARNING: No auto-created variants found in productCreate response")

    existing_size = variant_nodes[0]["title"] if variant_nodes else None
    remaining_sizes = [s for s in sizes if s != existing_size]

    if remaining_sizes and product_gid:
        # Resolve the option ID for "Size"
        product_options = product.get("options", [])
        size_option = next((o for o in product_options if o.get("name") == "Size"), None)
        if not size_option:
            # Fallback: query the product for options
            opt_data = _graphql(
                """query getOpts($id: ID!) { product(id: $id) { options { id name } } }""",
                {"id": product_gid},
            )
            product_options = opt_data.get("product", {}).get("options", [])
            size_option = next((o for o in product_options if o.get("name") == "Size"), None)

        if size_option:
            bulk_variants = []
            for s in remaining_sizes:
                bulk_variants.append({
                    "optionValues": [{"optionId": size_option["id"], "name": s}],
                    "price": str(price),
                    "compareAtPrice": str(compare_at_price),
                })

            bulk_create_data = _graphql(
                """mutation variantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
                    productVariantsBulkCreate(productId: $productId, variants: $variants) {
                        productVariants {
                            id
                            title
                            inventoryItem { id }
                        }
                        userErrors { field message }
                    }
                }""",
                {"productId": product_gid, "variants": bulk_variants},
            )
            bulk_result = bulk_create_data.get("productVariantsBulkCreate", {})
            bulk_errors = bulk_result.get("userErrors", [])
            if bulk_errors:
                print(f"[shopify] Variant bulk-create errors: {json.dumps(bulk_errors)}")
            else:
                new_variants = bulk_result.get("productVariants", [])
                variant_nodes.extend(new_variants)
                print(f"[shopify] Created {len(new_variants)} additional variants: {remaining_sizes}")
        else:
            print("[shopify] WARNING: Could not find Size option for bulk variant creation")

    # Step 3: Update first variant with correct price/compareAtPrice
    # (productCreate sets first variant at $0.00)
    if variant_nodes:
        first_variant = variant_nodes[0]
        variants_update_input = [{
            "id": first_variant["id"],
            "price": str(price),
            "compareAtPrice": str(compare_at_price),
        }]

        update_mutation = """
        mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
            productVariantsBulkUpdate(productId: $productId, variants: $variants) {
                productVariants {
                    id
                    title
                    price
                    compareAtPrice
                    inventoryItem {
                        id
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variants_data = _graphql(update_mutation, {
            "productId": product_gid,
            "variants": variants_update_input,
        })
        variant_result = variants_data.get("productVariantsBulkUpdate", {})
        variant_errors = variant_result.get("userErrors", [])
        if variant_errors:
            raise Exception(f"Variant update errors: {json.dumps(variant_errors)}")

        # Use the updated first variant (has correct inventoryItem ID)
        updated_nodes = variant_result.get("productVariants", [])
        if updated_nodes:
            # Replace only the first variant; keep bulk-created ones intact
            variant_nodes[0] = updated_nodes[0]
        print(f"[shopify] Variants updated: {len(variant_nodes)} variants with price={price}, compareAt={compare_at_price}")

    # Step 4: Activate inventory at location + set quantities
    if variant_nodes and inventory_quantity > 0:
        _activate_and_set_inventory(variant_nodes, inventory_quantity)

    # Step 5: Publish to all sales channels
    if product_gid:
        _publish_to_channels(product_gid)

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


# ---- Product Metafields (for Pookie Mirror virtual try-on) ----

def set_product_metafields(product_gid: str, metafields: list[dict]) -> bool:
    """
    Set metafields on a product using metafieldsSet mutation.
    Idempotent — creates or updates.

    Args:
        product_gid: product GID (e.g. "gid://shopify/Product/123")
        metafields: list of dicts with keys: namespace, key, value, type
            Example: [
                {"namespace": "pookie", "key": "garment_brief", "value": "Red cotton kurti...", "type": "single_line_text_field"},
                {"namespace": "pookie", "key": "garment_category", "value": "upper_body", "type": "single_line_text_field"},
            ]

    Returns:
        True if all metafields were set successfully
    """
    mutation = """
    mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
        metafieldsSet(metafields: $metafields) {
            metafields {
                id
                namespace
                key
                value
            }
            userErrors {
                field
                message
            }
        }
    }
    """

    mf_input = []
    for mf in metafields:
        mf_input.append({
            "ownerId": product_gid,
            "namespace": mf.get("namespace", "pookie"),
            "key": mf["key"],
            "value": str(mf["value"]),
            "type": mf.get("type", "single_line_text_field"),
        })

    try:
        data = _graphql(mutation, {"metafields": mf_input})
        result = data.get("metafieldsSet", {})
        errors = result.get("userErrors", [])
        if errors:
            print(f"[shopify] Metafield errors: {json.dumps(errors)}")
            return False
        set_mfs = result.get("metafields", [])
        print(f"[shopify] Metafields set: {len(set_mfs)} on {product_gid}")
        return True
    except Exception as e:
        print(f"[shopify] Metafield set failed (non-fatal): {e}")
        return False


def get_product_metafields(product_gid: str, namespace: str = "pookie") -> dict:
    """
    Read all metafields for a product under a given namespace.

    Returns:
        dict mapping key → value, e.g. {"garment_brief": "Red cotton kurti...", "garment_category": "upper_body"}
    """
    query = """
    query productMetafields($id: ID!, $namespace: String!) {
        product(id: $id) {
            metafields(first: 20, namespace: $namespace) {
                nodes {
                    key
                    value
                }
            }
        }
    }
    """

    try:
        data = _graphql(query, {"id": product_gid, "namespace": namespace})
        nodes = data.get("product", {}).get("metafields", {}).get("nodes", [])
        return {n["key"]: n["value"] for n in nodes}
    except Exception as e:
        print(f"[shopify] Metafield read failed: {e}")
        return {}


def set_customer_metafield(customer_gid: str, key: str, value: str, mf_type: str = "json") -> bool:
    """
    Set a single metafield on a customer (for storing try-on photo URLs).

    Args:
        customer_gid: customer GID (e.g. "gid://shopify/Customer/123")
        key: metafield key (e.g. "tryon_photos")
        value: JSON string (for json type) or plain string
        mf_type: metafield type (default "json")

    Returns:
        True if successful
    """
    mutation = """
    mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
        metafieldsSet(metafields: $metafields) {
            metafields { id key value }
            userErrors { field message }
        }
    }
    """

    try:
        data = _graphql(mutation, {
            "metafields": [{
                "ownerId": customer_gid,
                "namespace": "pookie",
                "key": key,
                "value": value,
                "type": mf_type,
            }]
        })
        errors = data.get("metafieldsSet", {}).get("userErrors", [])
        if errors:
            print(f"[shopify] Customer metafield errors: {json.dumps(errors)}")
            return False
        print(f"[shopify] Customer metafield '{key}' set on {customer_gid}")
        return True
    except Exception as e:
        print(f"[shopify] Customer metafield failed: {e}")
        return False
