from datetime import datetime, timezone
from typing import Any, Optional
import threading

# Thread-safe counter for unique SKUs
_sku_counter_lock = threading.Lock()
_sku_counter = 900000


def _generate_unique_sku() -> str:
    global _sku_counter
    with _sku_counter_lock:
        _sku_counter += 1
        # Return only the numeric part to comply with 4-8 digit constraint
        return str(_sku_counter)


def deep_update(base_dict: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
            deep_update(base_dict[key], value)
        else:
            base_dict[key] = value


def create_shopify_product_response(
    gid: str = "gid://shopify/Product/123456789",
    title: str = "Test Product",
    description: str = "<p>Test description</p>",
    vendor: str = "Test Vendor",
    product_type: str = "Test Type",
    status: str = "ACTIVE",
    total_inventory: int = 100,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
    variants: Optional[list[dict[str, Any]]] = None,
    media: Optional[list[dict[str, Any]]] = None,
    metafields: Optional[list[dict[str, Any]]] = None,
    **overrides: object,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    created_at = created_at or now
    updated_at = updated_at or now

    if variants is None:
        variants = [
            {
                "id": "gid://shopify/ProductVariant/987654321",
                "price": "99.99",
                "sku": _generate_unique_sku(),
                "barcode": "123456789012",
                "inventoryItem": {
                    "unitCost": {"amount": "50.00", "currencyCode": "USD"},
                    "measurement": {"weight": {"value": 1.5}},
                },
            }
        ]

    if media is None:
        media = [
            {
                "__typename": "MediaImage",
                "id": "gid://shopify/MediaImage/123",
                "alt": "Test image",
                "status": "READY",
                "originalSource": {"url": "https://example.com/image.jpg"},
                "preview": {"image": {"url": "https://example.com/preview.jpg"}},
            }
        ]

    if metafields is None:
        metafields = []

    base_response = {
        "id": gid,
        "title": title,
        "descriptionHtml": description,
        "vendor": vendor,
        "productType": product_type,
        "status": status,
        "totalInventory": total_inventory,
        "createdAt": created_at,
        "updatedAt": updated_at,
        "media": {"nodes": media},
        "variants": {"nodes": variants},
        "metafields": {"nodes": metafields},
    }

    deep_update(base_response, overrides)
    return base_response


def create_shopify_variant_response(
    gid: str = "gid://shopify/ProductVariant/987654321",
    price: str = "99.99",
    sku: Optional[str] = None,
    barcode: Optional[str] = "123456789012",
    weight: float = 1.5,
    unit_cost: str = "50.00",
    currency_code: str = "USD",
    **overrides: object,
) -> dict[str, Any]:
    # Generate unique SKU if not provided
    if sku is None:
        sku = _generate_unique_sku()
    base_response = {
        "id": gid,
        "price": price,
        "sku": sku,
        "barcode": barcode,
        "inventoryItem": {
            "unitCost": {"amount": unit_cost, "currencyCode": currency_code},
            "measurement": {"weight": {"value": weight}},
        },
    }

    deep_update(base_response, overrides)
    return base_response


def create_money_bag(amount: str, currency_code: str = "USD") -> dict[str, Any]:
    return {
        "presentmentMoney": {"amount": amount, "currencyCode": currency_code},
        "shopMoney": {"amount": amount, "currencyCode": currency_code},
    }


def create_shopify_address_response(
    gid: Optional[str] = "gid://shopify/CustomerAddress/123",
    name: Optional[str] = "John Doe",
    company: Optional[str] = None,
    address1: Optional[str] = "123 Main St",
    address2: Optional[str] = None,
    city: Optional[str] = "New York",
    province_code: Optional[str] = "NY",
    province: Optional[str] = "New York",
    country_code: str = "US",
    zip_code: Optional[str] = "10001",
    phone: Optional[str] = "+1-555-123-4567",
    **overrides: object,
) -> dict[str, Any]:
    base_response = {
        "id": gid,
        "name": name,
        "company": company,
        "address1": address1,
        "address2": address2,
        "city": city,
        "provinceCode": province_code,
        "province": province,
        "countryCodeV2": country_code,
        "zip": zip_code,
        "phone": phone,
    }

    deep_update(base_response, overrides)
    return base_response


def create_shopify_customer_response(
    gid: str = "gid://shopify/Customer/123456789",
    first_name: Optional[str] = "John",
    last_name: Optional[str] = "Doe",
    email: Optional[str] = "john.doe@example.com",
    phone: Optional[str] = "+1-555-123-4567",
    tax_exempt: bool = False,
    tags: Optional[list[str]] = None,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
    default_address: Optional[dict[str, Any]] = None,
    addresses: Optional[list[dict[str, Any]]] = None,
    **overrides: object,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    created_at = created_at or now
    updated_at = updated_at or now

    if tags is None:
        tags = []

    if default_address is None:
        default_address = create_shopify_address_response(phone=phone)

    if addresses is None:
        addresses = [default_address]

    base_response = {
        "id": gid,
        "firstName": first_name,
        "lastName": last_name,
        "defaultEmailAddress": (
            {
                "emailAddress": email,
                "marketingState": "NOT_SUBSCRIBED",
                "marketingOptInLevel": None,
                "marketingUpdatedAt": None,
            }
            if email
            else None
        ),
        "defaultPhoneNumber": (
            {
                "phoneNumber": phone,
                "marketingState": "NOT_SUBSCRIBED",
                "marketingOptInLevel": None,
                "marketingUpdatedAt": None,
            }
            if phone
            else None
        ),
        "createdAt": created_at,
        "updatedAt": updated_at,
        "defaultAddress": default_address,
        "addressesV2": {"nodes": addresses},
        "tags": tags,
        "taxExempt": tax_exempt,
    }

    deep_update(base_response, overrides)
    return base_response


def create_shopify_order_line_item_response(
    gid: str = "gid://shopify/LineItem/123456789",
    sku: Optional[str] = "008002",
    quantity: int = 1,
    name: str = "Test Product",
    variant_id: str = "gid://shopify/ProductVariant/987654321",
    unit_price: str = "99.99",
    currency_code: str = "USD",
    custom_attributes: Optional[list[dict[str, Any]]] = None,
    discount_allocations: Optional[list[dict[str, Any]]] = None,
    **overrides: object,
) -> dict[str, Any]:
    if custom_attributes is None:
        custom_attributes = []

    if discount_allocations is None:
        discount_allocations = []

    base_response = {
        "id": gid,
        "sku": sku,
        "quantity": quantity,
        "name": name,
        "variant": {"id": variant_id},
        "originalUnitPriceSet": create_money_bag(unit_price, currency_code),
        "customAttributes": custom_attributes,
        "discountAllocations": discount_allocations,
    }

    deep_update(base_response, overrides)
    return base_response


def create_shopify_shipping_line_response(
    gid: str = "gid://shopify/ShippingLine/123456789",
    title: str = "Standard Shipping",
    price: str = "10.00",
    currency_code: str = "USD",
    carrier_identifier: Optional[str] = "ups",
    code: Optional[str] = "STANDARD",
    **overrides: object,
) -> dict[str, Any]:
    base_response = {
        "id": gid,
        "title": title,
        "originalPriceSet": create_money_bag(price, currency_code),
        "carrierIdentifier": carrier_identifier,
        "code": code,
    }

    deep_update(base_response, overrides)
    return base_response


def create_shopify_order_response(
    gid: str = "gid://shopify/Order/123456789",
    name: str = "#1001",
    currency_code: str = "USD",
    total_price: str = "109.99",
    subtotal_price: str = "99.99",
    shipping_price: str = "10.00",
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
    processed_at: Optional[str] = None,
    closed_at: Optional[str] = None,
    cancelled_at: Optional[str] = None,
    customer: Optional[dict[str, Any]] = None,
    shipping_address: Optional[dict[str, Any]] = None,
    billing_address: Optional[dict[str, Any]] = None,
    line_items: Optional[list[dict[str, Any]]] = None,
    shipping_lines: Optional[list[dict[str, Any]]] = None,
    discount_applications: Optional[list[dict[str, Any]]] = None,
    tax_lines: Optional[list[dict[str, Any]]] = None,
    metafields: Optional[list[dict[str, Any]]] = None,
    **overrides: object,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    created_at = created_at or now
    updated_at = updated_at or now
    processed_at = processed_at or now

    if line_items is None:
        line_items = [create_shopify_order_line_item_response()]

    if shipping_lines is None:
        shipping_lines = [create_shopify_shipping_line_response()]

    if discount_applications is None:
        discount_applications = []

    if tax_lines is None:
        tax_lines = []

    if metafields is None:
        metafields = []

    base_response = {
        "id": gid,
        "name": name,
        "createdAt": created_at,
        "updatedAt": updated_at,
        "processedAt": processed_at,
        "closedAt": closed_at,
        "cancelledAt": cancelled_at,
        "currencyCode": currency_code,
        "totalPriceSet": create_money_bag(total_price, currency_code),
        "subtotalPriceSet": create_money_bag(subtotal_price, currency_code),
        "totalShippingPriceSet": create_money_bag(shipping_price, currency_code),
        "customer": customer,
        "shippingAddress": shipping_address,
        "billingAddress": billing_address,
        "lineItems": {"nodes": line_items},
        "shippingLines": {"nodes": shipping_lines},
        "fulfillments": [],
        "discountApplications": {"nodes": discount_applications},
        "totalDiscountsSet": create_money_bag("0.00", currency_code),
        "taxLines": tax_lines,
        "metafields": {"nodes": metafields},
    }

    deep_update(base_response, overrides)
    return base_response


def create_bulk_operation_response(
    gid: str = "gid://shopify/BulkOperation/123456789",
    status: str = "COMPLETED",
    error_code: Optional[str] = None,
    created_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    url: Optional[str] = "https://storage.googleapis.com/shopify-bulk-data/test.jsonl",
    **overrides: object,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    created_at = created_at or now
    completed_at = completed_at or now if status == "COMPLETED" else None

    base_response = {
        "id": gid,
        "status": status,
        "errorCode": error_code,
        "createdAt": created_at,
        "completedAt": completed_at,
        "url": url,
    }

    deep_update(base_response, overrides)
    return base_response


def create_shopify_page_info(has_next_page: bool = False, has_previous_page: bool = False) -> dict[str, Any]:
    return {"hasNextPage": has_next_page, "hasPreviousPage": has_previous_page}


def create_shopify_metafield(
    gid: str = "gid://shopify/Metafield/123",
    key: str = "test_key",
    value: str = "test_value",
    namespace: str = "custom",
) -> dict[str, Any]:
    return {
        "id": gid,
        "key": key,
        "value": value,
        "namespace": namespace,
    }


def create_shopify_product_image(
    gid: str = "gid://shopify/MediaImage/123456789",
    alt: Optional[str] = None,
    status: str = "READY",
    url: str = "https://example.com/image.jpg",
) -> dict[str, Any]:
    return {
        "__typename": "MediaImage",
        "id": gid,
        "alt": alt,
        "status": status,
        "originalSource": {"url": url},
        "preview": {
            "image": {
                "url": url,
            }
        },
    }


def create_shopify_customer(
    gid: str = "gid://shopify/Customer/123456789",
    first_name: Optional[str] = "John",
    last_name: Optional[str] = "Doe",
    email: Optional[str] = "john.doe@example.com",
    phone: Optional[str] = None,
    note: Optional[str] = None,
    tags: Optional[list[str]] = None,
    tax_exempt: bool = False,
    email_marketing_consent: Optional[dict[str, Any]] = None,
    sms_marketing_consent: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return {
        "id": gid,
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
        "phone": phone,
        "note": note,
        "tags": tags or [],
        "taxExempt": tax_exempt,
        "emailMarketingConsent": email_marketing_consent or {"marketingState": "NOT_SUBSCRIBED"},
        "smsMarketingConsent": sms_marketing_consent or {"marketingState": "NOT_SUBSCRIBED"},
    }


def create_shopify_motor_metafields(
    year: Optional[str] = "2023",
    make: Optional[str] = "Yamaha",
    model: Optional[str] = "F150",
    horsepower: Optional[str] = "150",
    serial_start: Optional[str] = "1000",
    serial_end: Optional[str] = "9999",
) -> list[dict[str, Any]]:
    metafields = []

    if year:
        metafields.append({"id": f"gid://shopify/Metafield/{len(metafields) + 1}", "key": "motor_year", "value": year})

    if make:
        metafields.append({"id": f"gid://shopify/Metafield/{len(metafields) + 1}", "key": "motor_make", "value": make})

    if model:
        metafields.append({"id": f"gid://shopify/Metafield/{len(metafields) + 1}", "key": "motor_model", "value": model})

    if horsepower:
        metafields.append({"id": f"gid://shopify/Metafield/{len(metafields) + 1}", "key": "motor_horsepower", "value": horsepower})

    if serial_start:
        metafields.append(
            {"id": f"gid://shopify/Metafield/{len(metafields) + 1}", "key": "motor_serial_start", "value": serial_start}
        )

    if serial_end:
        metafields.append({"id": f"gid://shopify/Metafield/{len(metafields) + 1}", "key": "motor_serial_end", "value": serial_end})

    return metafields
