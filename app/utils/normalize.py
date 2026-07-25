from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse, urlunparse


FACEBOOK_ITEM_RE = re.compile(r"/marketplace/item/([^/?#]+)")
YEAR_RE = re.compile(r"\b(19[8-9]\d|20\d{2})\b")
ODOMETER_RE = re.compile(
    r"(?<![a-z0-9])(\d{1,3}(?:,\d{3})+|\d{4,6}|\d{1,3}(?:\.\d+)?)\s*(k|km|kms|kilometres|kilometers)?\b",
    re.IGNORECASE,
)
MARKED_PRICE_RE = re.compile(
    r"(?i)(?:aud|a\$|\$a|\$)\s*([0-9][0-9,]*(?:\.[0-9]{2})?)|(?<![a-z0-9])([0-9][0-9,]*(?:\.[0-9]{2})?)\s*(?:aud|a\$|\$a|\$)"
)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    text = value.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_display_text(value: str | None) -> str | None:
    if value is None:
        return None

    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def parse_price_aud(price_text: str | None) -> int | None:
    if price_text is None:
        return None

    text = str(price_text).strip()
    if not text:
        return None

    lowered = text.lower()
    if any(
        phrase in lowered
        for phrase in ("free", "contact seller", "please ask", "negotiable")
    ):
        return None

    if re.search(r"\b(km|kms|kilometres|kilometers)\b", lowered):
        return None

    cleaned = re.sub(r"(?i)\b(aud)\b", "", text)
    cleaned = cleaned.replace("A$", "").replace("a$", "")
    cleaned = cleaned.replace("$A", "").replace("$a", "")
    cleaned = cleaned.replace("$", "")
    cleaned = cleaned.replace(",", "")
    cleaned = re.sub(r"\s+", "", cleaned)

    if not re.fullmatch(r"\d+", cleaned):
        return None

    return int(cleaned)


def extract_price_aud(text: str | None) -> int | None:
    if text is None:
        return None

    lowered = str(text).lower()
    if any(
        phrase in lowered
        for phrase in ("free", "contact seller", "please ask", "negotiable")
    ):
        return None

    for match in MARKED_PRICE_RE.finditer(str(text)):
        price_text = match.group(1) or match.group(2)
        price = _parse_price_number(price_text)
        if price is not None:
            return price

    return None


def parse_odometer_km(
    odometer_text: str | None,
    *,
    require_unit: bool = False,
) -> int | None:
    if odometer_text is None:
        return None

    text = str(odometer_text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    if not text or text in {"unknown", "low kilometres", "low kilometers"}:
        return None

    for match in ODOMETER_RE.finditer(text):
        number_text, unit = match.groups()
        if require_unit and not unit:
            continue

        value = _parse_odometer_number(number_text, unit)
        if value is None:
            continue

        if 1_000 <= value <= 999_999:
            return value

    return None


def _parse_odometer_number(number_text: str, unit: str | None) -> int | None:
    compact = number_text.replace(",", "")
    try:
        value = float(compact)
    except ValueError:
        return None

    if unit and unit.lower() == "k":
        value *= 1000

    return int(value)


def _parse_price_number(number_text: str) -> int | None:
    compact = number_text.replace(",", "").strip()
    if not compact:
        return None

    try:
        return int(float(compact))
    except ValueError:
        return None


def extract_year(
    title_text: str | None,
    description_text: str | None = None,
    *,
    current_year: int | None = None,
) -> int | None:
    max_year = (current_year or datetime.now().year) + 1
    for text in (title_text, description_text):
        if not text:
            continue

        for match in YEAR_RE.finditer(str(text)):
            year = int(match.group(1))
            if 1980 <= year <= max_year:
                return year

    return None


def normalize_url(
    url: str | None,
    *,
    listing_id: str | None = None,
    source: str = "facebook_marketplace",
) -> str | None:
    if not url and listing_id and source == "facebook_marketplace":
        return f"https://www.facebook.com/marketplace/item/{listing_id}"

    if not url:
        return None

    raw_url = str(url).strip()
    if raw_url.startswith("/"):
        raw_url = f"https://www.facebook.com{raw_url}"

    parsed = urlparse(raw_url)
    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc,
            parsed.path.rstrip("/"),
            "",
            "",
            "",
        )
    )


def extract_listing_id(url: str | None) -> str | None:
    if not url:
        return None

    match = FACEBOOK_ITEM_RE.search(str(url))
    if not match:
        return None

    return match.group(1).strip("/") or None


def normalize_location(location_text: str | None) -> str | None:
    text = clean_display_text(location_text)
    if text is None:
        return None

    text = re.sub(r"\bWestern Australia\b", "WA", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s+WA$", ", WA", text)
    text = re.sub(r",\s*,", ",", text)
    return text.strip()


def normalize_image_urls(image_urls: object) -> list[str]:
    if not isinstance(image_urls, list):
        return []

    seen: set[str] = set()
    normalized: list[str] = []
    for image_url in image_urls:
        if not image_url:
            continue

        value = str(image_url).strip()
        if not value or value in seen:
            continue

        seen.add(value)
        normalized.append(value)

    return normalized
