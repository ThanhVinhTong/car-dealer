"""
================================================================================
CLOUDFLARE PYTHON WORKER: FACEBOOK MARKETPLACE RAW DATA NORMALIZER
================================================================================
DISCLAIMER & PURPOSE:
This worker script is SPECIFICALLY DESIGNED FOR CLOUDFLARE WORKERS (Python runtime / Pyodide).
It acts as an edge endpoint to receive HTTP POST webhook requests containing raw 
scraped listing data specifically originating from FACEBOOK MARKETPLACE.

RESPONSIBILITIES:
1. Receive raw HTTP POST JSON payload from scrapers (e.g. Apify / Playwright).
2. Apply normalization & filtering rules tailored for Facebook Marketplace:
   - Extract listing ID and clean normalized URLs.
   - Extract numeric AUD prices from raw text ("AU$19,985" -> 19985).
   - Parse manufacture year and enforce eligibility rules (e.g. Min year >= 2012, no E-chassis).
   - Resolve Make and Model IDs for database reference tables (`makes`, `models`).
   - Format seller location, timestamps, status ("active").
3. Return a clean, DB-ready JSON array formatted specifically for database insertion 
   into `cars`, `makes`, `models`, and `price_history`.
================================================================================
"""

import json
import re
from datetime import datetime, timezone
from js import Response

# Standard CORS headers for edge responses
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}

# Filtering constants
MIN_MANUFACTURE_YEAR = 2012
DEFAULT_MAKE_NAME = "BMW"
DEFAULT_MAKE_ID = 1

# Pre-compiled regex patterns for edge processing
YEAR_RE = re.compile(r"\b(20[0-9]{2}|19[9][0-9])\b")
PRICE_AUD_RE = re.compile(r"(?:AU\s*\$|\$)\s*([\d,]+)", re.IGNORECASE)
GENERIC_DIGITS_RE = re.compile(r"\b\d{4,6}\b")
E_CHASSIS_RE = re.compile(r"\b(E81|E82|E87|E88|E90|E91|E92|E93|E60|E61|E63|E64|E65|E66|E70|E71|E84|E89|E-series|E\s*generation)\b", re.IGNORECASE)

# BMW Model patterns
BMW_MODELS_MAP = [
    ("M2", r"\bm2\b"),
    ("M3", r"\bm3\b"),
    ("M4", r"\bm4\b"),
    ("M5", r"\bm5\b"),
    ("M8", r"\bm8\b"),
    ("X1", r"\bx1\b"),
    ("X2", r"\bx2\b"),
    ("X3", r"\bx3\b"),
    ("X4", r"\bx4\b"),
    ("X5", r"\bx5\b"),
    ("X6", r"\bx6\b"),
    ("X7", r"\bx7\b"),
    ("Z4", r"\bz4\b"),
    ("1 Series", r"\b(1\s*series|116i|118i|120i|125i|130i|135i|m135i|m140i)\b"),
    ("2 Series", r"\b(2\s*series|218i|220i|228i|230i|235i|m235i|m240i)\b"),
    ("3 Series", r"\b(3\s*series|316i|318i|320i|328i|330i|335i|340i|m340i)\b"),
    ("4 Series", r"\b(4\s*series|420i|428i|430i|435i|440i|m440i)\b"),
    ("5 Series", r"\b(5\s*series|520i|528i|530i|535i|540i|550i|m550i)\b"),
    ("6 Series", r"\b(6\s*series|630i|640i|650i)\b"),
    ("7 Series", r"\b(7\s*series|730i|740i|750i|760i)\b"),
]


def extract_price(price_text: str | None, text_content: str) -> int | None:
    """Extract AUD numeric integer price from Facebook Marketplace price strings."""
    if price_text:
        match = PRICE_AUD_RE.search(price_text)
        if match:
            cleaned = match.group(1).replace(",", "")
            if cleaned.isdigit():
                return int(cleaned)
        
        # Fallback to direct digits in price_text
        cleaned = re.sub(r"[^\d]", "", price_text)
        if cleaned and cleaned.isdigit():
            val = int(cleaned)
            if 1000 <= val <= 300000:
                return val

    # Search in title/description fallback
    match = PRICE_AUD_RE.search(text_content)
    if match:
        cleaned = match.group(1).replace(",", "")
        if cleaned.isdigit():
            return int(cleaned)

    return None


def extract_manufacture_year(title: str | None, description: str | None) -> int | None:
    """Extract manufacture year from title or description."""
    text = f"{title or ''} {description or ''}"
    matches = YEAR_RE.findall(text)
    if matches:
        # Prefer earliest plausible year found in title, or first match
        for year_str in matches:
            year = int(year_str)
            if 1990 <= year <= 2030:
                return year
    return None


def match_model_name(title: str, description: str, search_model_name: str | None) -> str:
    """Resolve BMW model name from listing text."""
    combined = f"{title} {description}".lower()
    
    for model_name, pattern in BMW_MODELS_MAP:
        if re.search(pattern, combined, re.IGNORECASE):
            return model_name

    if search_model_name and search_model_name.lower() != "unknown":
        return search_model_name

    return "unknown"


def clean_url(url: str | None, listing_id: str | None) -> str:
    """Normalize Facebook Marketplace item URL."""
    if listing_id:
        return f"https://www.facebook.com/marketplace/item/{listing_id}"
    if url:
        return url.split("?")[0]
    return ""


def normalize_facebook_listing(raw_item: dict) -> dict | None:
    """
    Normalizes a single raw Facebook Marketplace listing dictionary into 
    the exact target PostgreSQL database schema format for `cars`, `makes`, `models`, 
    and `price_history`.
    """
    title = str(raw_item.get("title") or "").strip()
    description = str(raw_item.get("description") or "").strip()
    listing_id = str(raw_item.get("listing_id") or "").strip()
    
    if not listing_id and not title:
        return None

    # Check E-chassis exclusion filter
    if E_CHASSIS_RE.search(f"{title} {description}"):
        return None

    # Extract & validate manufacture year
    manufacture_year = extract_manufacture_year(title, description)
    if manufacture_year is not None and manufacture_year < MIN_MANUFACTURE_YEAR:
        return None

    # Extract price
    price_aud = extract_price(raw_item.get("price_text"), f"{title} {description}")

    # Resolve Model
    search_model_name = raw_item.get("search_model_name")
    resolved_model_name = match_model_name(title, description, search_model_name)

    # Timestamps
    now_iso = datetime.now(timezone.utc).isoformat()
    scraped_at = raw_item.get("scraped_at") or now_iso

    normalized_url = clean_url(raw_item.get("url"), listing_id)

    # Target Normalized Structure matching database schema
    return {
        "car_id": None,  # Will be populated upon DB insertion
        "source": "facebook_marketplace",
        "listing_id": listing_id,
        "normalized_url": normalized_url,
        "title": title,
        "make_id": DEFAULT_MAKE_ID,
        "make_name": DEFAULT_MAKE_NAME,
        "model_id": None,  # Matched by backend on model_name
        "model_name": resolved_model_name,
        "manufacture_year": manufacture_year,
        "current_price_aud": price_aud,
        "sell_location": raw_item.get("location_text") or "Perth, WA",
        "status": "active",
        "first_seen_at": scraped_at,
        "last_seen_at": scraped_at,
        "created_at": scraped_at,
        "updated_at": scraped_at,
        # Additional fields for price_history population
        "price_history": [
            {
                "price_aud": price_aud,
                "observed_at": scraped_at
            }
        ] if price_aud is not None else []
    }


def normalize_facebook_marketplace_batch(raw_listings: list[dict]) -> list[dict]:
    """Process a batch of raw Facebook Marketplace listings."""
    normalized_cars = []
    seen_ids = set()

    for item in raw_listings:
        if not isinstance(item, dict):
            continue
        
        car = normalize_facebook_listing(item)
        if car and car["listing_id"] not in seen_ids:
            seen_ids.add(car["listing_id"])
            normalized_cars.append(car)

    return normalized_cars


# ==============================================================================
# CLOUDFLARE WORKER ENTRY POINT (Pyodide / Python Runtime)
# ==============================================================================
async def on_fetch(request, env):
    """
    Standard Cloudflare Python Worker fetch event handler.
    Receives HTTP POST requests, normalizes Facebook Marketplace raw data,
    and returns a clean JSON response.
    """
    # Handle CORS preflight OPTIONS request
    method = getattr(request, "method", "GET")
    if method == "OPTIONS":
        return Response(json.dumps({"status": "ok"}), status=200, headers=CORS_HEADERS)

    if method != "POST":
        return Response(
            json.dumps({"error": "Method not allowed. Send a POST request."}),
            status=405,
            headers=CORS_HEADERS
        )

    try:
        # Read JSON body from Cloudflare request
        body_text = await request.text()
        raw_payload = json.loads(body_text) if body_text else []

        # Handle various list / wrapped object formats
        if isinstance(raw_payload, dict):
            if "items" in raw_payload and isinstance(raw_payload["items"], list):
                raw_listings = raw_payload["items"]
            elif "data" in raw_payload and isinstance(raw_payload["data"], list):
                raw_listings = raw_payload["data"]
            else:
                raw_listings = [raw_payload]
        elif isinstance(raw_payload, list):
            raw_listings = raw_payload
        else:
            raw_listings = []

        # Execute Facebook Marketplace edge normalization
        normalized_cars = normalize_facebook_marketplace_batch(raw_listings)

        result_payload = {
            "status": "success",
            "source_platform": "facebook_marketplace",
            "received_count": len(raw_listings),
            "normalized_count": len(normalized_cars),
            "normalized_cars": normalized_cars
        }

        return Response(
            json.dumps(result_payload, indent=2),
            status=200,
            headers=CORS_HEADERS
        )

    except Exception as err:
        error_response = {
            "status": "error",
            "message": f"Cloudflare Worker Normalization Error: {str(err)}"
        }
        return Response(
            json.dumps(error_response),
            status=500,
            headers=CORS_HEADERS
        )
