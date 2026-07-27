from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.utils.bmw import (
    UNRANKED_BMW_SERIES_PRIORITY,
    bmw_series_priority,
    detect_bmw_chassis_generation,
    is_bmw_make_name,
)
from app.utils.logger import get_logger
from app.utils.normalize import (
    clean_display_text,
    extract_price_aud,
    extract_listing_id,
    extract_year,
    normalize_image_urls,
    normalize_location,
    normalize_text,
    normalize_url,
    parse_odometer_km,
    parse_price_aud,
)


MIN_BMW_MANUFACTURE_YEAR = 2012
BMW_INDICATOR_RE = re.compile(r"\b(bmw|b\s*m\s*w|beemer|bimmer)\b", re.IGNORECASE)
PARTS_TITLE_PATTERNS = (
    r"\bwheels?\b",
    r"\brims?\b",
    r"\btyres?\b",
    r"\btires?\b",
    r"\bparts?\b",
    r"\bbumper\b",
    r"\bheadlights?\b",
    r"\btaillights?\b",
    r"\btail light\b",
    r"\bcar seat\b",
    r"\bfloor mats?\b",
    r"\broof racks?\b",
    r"\baccessories\b",
)
PARTS_COMBINED_PATTERNS = (
    r"\bengine only\b",
    r"\btransmission only\b",
    r"\bwrecking\b",
    r"\bparting out\b",
)

BMW_X_M_MODELS = (
    ("X3M", r"(?<![a-z0-9])(?:x3m|x3\s+m)(?![a-z0-9])"),
    ("X4M", r"(?<![a-z0-9])(?:x4m|x4\s+m)(?![a-z0-9])"),
    ("X5M", r"(?<![a-z0-9])(?:x5m|x5\s+m)(?![a-z0-9])"),
    ("X6M", r"(?<![a-z0-9])(?:x6m|x6\s+m)(?![a-z0-9])"),
)
BMW_M_MODELS = (
    ("M2", r"(?<![a-z0-9])m2(?![a-z0-9])"),
    ("M3", r"(?<![a-z0-9])m3(?![a-z0-9])"),
    ("M4", r"(?<![a-z0-9])m4(?![a-z0-9])"),
    ("M5", r"(?<![a-z0-9])m5(?![a-z0-9])"),
    ("M8", r"(?<![a-z0-9])m8(?![a-z0-9])"),
)
BMW_X_MODELS = (
    ("X1", r"(?<![a-z0-9])x1(?![a-z0-9])"),
    ("X2", r"(?<![a-z0-9])x2(?![a-z0-9])"),
    ("X3", r"(?<![a-z0-9])x3(?![a-z0-9])"),
    ("X4", r"(?<![a-z0-9])x4(?![a-z0-9])"),
    ("X5", r"(?<![a-z0-9])x5(?![a-z0-9])"),
    ("X6", r"(?<![a-z0-9])x6(?![a-z0-9])"),
    ("X7", r"(?<![a-z0-9])x7(?![a-z0-9])"),
)
BMW_SERIES_BADGES = (
    ("1 Series", ("1 series", "116i", "116d", "118i", "118d", "120i", "120d", "123d", "125i", "125d", "128ti", "130i", "135i", "m135i", "m140i")),
    ("2 Series", ("2 series", "218i", "218d", "220i", "220d", "225i", "225d", "228i", "230i", "235i", "m235i", "m240i")),
    ("3 Series", ("3 series", "316i", "316d", "318i", "318d", "320i", "320d", "323i", "323d", "325i", "325d", "328i", "328d", "330i", "330d", "335i", "335d", "340i", "m340i")),
    ("4 Series", ("4 series", "418i", "418d", "420i", "420d", "425i", "425d", "428i", "428d", "430i", "430d", "435i", "435d", "440i", "m440i")),
    ("5 Series", ("5 series", "518i", "518d", "520i", "520d", "523i", "523d", "525i", "525d", "528i", "528d", "530i", "530d", "535i", "535d", "540i", "545i", "550i", "m550i")),
    ("6 Series", ("6 series", "620i", "620d", "630i", "630d", "635i", "635d", "640i", "640d", "645i", "650i")),
    ("7 Series", ("7 series", "728i", "730i", "730d", "735i", "735d", "740i", "740d", "745i", "750i", "750d", "760i")),
)

PROBLEM_ISSUE_RULES = (
    {
        "issue_type": "engine_failure",
        "confidence": "high",
        "patterns": (
            r"\bengine blown\b",
            r"\bengine seized\b",
            r"\bengine gone\b",
            r"\bneeds new engine\b",
            r"\bneeds engine\b",
        ),
    },
    {
        "issue_type": "transmission_failure",
        "confidence": "high",
        "patterns": (
            r"\btransmission (?:issue|problem|fault)\b",
            r"\bgearbox (?:issue|problem|fault)\b",
            r"\bnot shifting\b",
        ),
    },
    {
        "issue_type": "accident_damage",
        "confidence": "high",
        "patterns": (
            r"\baccident damaged\b",
            r"\bsalvage\b",
            r"\bcrash(?:ed)?\b",
            r"\bwritten off\b",
        ),
    },
    {
        "issue_type": "mechanical_failure",
        "confidence": "high",
        "patterns": (
            r"\bnot running\b",
            r"\bwon['’]?t start\b",
            r"\bdoesn['’]?t start\b",
            r"\bno start\b",
            r"\bnot driveable\b",
        ),
    },
    {
        "issue_type": "unknown_problem",
        "confidence": "low",
        "patterns": (
            r"\bneeds tlc\b",
            r"\bneeds work\b",
            r"\bproject car\b",
            r"\brepair required\b",
            r"\bminor issues?\b",
            r"\bproblem\b",
        ),
    },
)

ISSUE_EXCLUSION_PATTERNS = (
    r"\bengine recently replaced\b",
    r"\bnew engine\b",
    r"\bfresh engine\b",
    r"\bengine rebuilt\b",
)


class CarParser:
    def __init__(self, makes: list[dict], models: list[dict]) -> None:
        self.logger = get_logger(self.__class__.__name__)
        self.makes = makes
        self.models = models
        self.bmw_make = self._find_bmw_make()
        self.bmw_models_by_name = self._build_bmw_models_by_name()
        self.unknown_model = self.bmw_models_by_name.get("unknown") or {
            "model_id": 49,
            "model_name": "unknown",
            "make_id": self.bmw_make.get("make_id") if self.bmw_make else 1,
        }

    def parse(self, raw_listing: dict) -> dict | None:
        title = clean_display_text(raw_listing.get("title"))
        description = clean_display_text(raw_listing.get("description"))
        title_text = normalize_text(title)
        description_text = normalize_text(description)
        combined_text = f"{title_text} {description_text}".strip()

        if self._is_parts_listing(title_text, combined_text):
            return None

        if not self._is_bmw(raw_listing, title_text, description_text):
            return None

        manufacture_year = extract_year(title, description)
        if (
            manufacture_year is not None
            and manufacture_year < MIN_BMW_MANUFACTURE_YEAR
        ):
            return None

        chassis_generation = detect_bmw_chassis_generation(title, description)
        if chassis_generation and chassis_generation.startswith("E"):
            return None

        model = self._resolve_bmw_model(raw_listing, title_text, description_text)
        series_priority = bmw_series_priority(model.get("model_name"))
        make = self.bmw_make or {"make_id": 1, "make_name": "BMW"}
        normalized_url = normalize_url(
            raw_listing.get("url"),
            listing_id=raw_listing.get("listing_id"),
            source=raw_listing.get("source") or "facebook_marketplace",
        )
        listing_id = self._resolve_listing_id(raw_listing, normalized_url)
        scraped_at = raw_listing.get("scraped_at") or datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
        odometer_km = parse_odometer_km(raw_listing.get("odometer_text"))
        if odometer_km is None:
            odometer_km = parse_odometer_km(description, require_unit=True)

        problem_detected, issue_types, issue_type, issue_confidence = (
            self._detect_listing_issues(combined_text)
        )

        return {
            "car_id": None,
            "source": raw_listing.get("source") or "facebook_marketplace",
            "listing_id": listing_id,
            "normalized_url": normalized_url,
            "title": title,
            "make_id": make.get("make_id"),
            "make_name": make.get("make_name"),
            "model_id": model.get("model_id"),
            "model_name": model.get("model_name"),
            "manufacture_year": manufacture_year,
            "current_price_aud": self._parse_current_price(raw_listing, title, description),
            "sell_location": normalize_location(raw_listing.get("location_text")),
            "status": "active",
            "first_seen_at": scraped_at,
            "last_seen_at": scraped_at,
            "created_at": scraped_at,
            "updated_at": scraped_at,
            "odometer_km": odometer_km,
            "description": description,
            "image_urls": normalize_image_urls(raw_listing.get("image_urls")),
            "seller_name": clean_display_text(raw_listing.get("seller_name")),
            "seller_type": self._normalize_seller_type(raw_listing.get("seller_type")),
            "search_make_name": raw_listing.get("search_make_name"),
            "search_model_name": raw_listing.get("search_model_name"),
            "search_url": raw_listing.get("search_url"),
            "scraped_at": scraped_at,
            "year_filter_status": (
                "eligible" if manufacture_year is not None else "unknown"
            ),
            "chassis_generation": chassis_generation,
            "generation_filter_status": (
                "eligible" if chassis_generation is not None else "unknown"
            ),
            "series_priority": series_priority,
            "requires_review": manufacture_year is None,
            "problem_detected": problem_detected,
            "issue_type": issue_type,
            "issue_confidence": issue_confidence,
            "issue_types": issue_types,
            "raw_payload": raw_listing,
        }

    def parse_many(self, raw_listings: list[dict]) -> list[dict]:
        parsed: list[dict] = []
        seen_keys: set[tuple[str, str]] = set()

        for raw_listing in raw_listings:
            try:
                car = self.parse(raw_listing)
            except Exception:
                self.logger.exception("Failed to parse listing")
                continue

            if car is None:
                continue

            key = self._dedupe_key(car)
            if key and key in seen_keys:
                continue

            if key:
                seen_keys.add(key)
            parsed.append(car)

        return sorted(
            parsed,
            key=lambda car: car.get(
                "series_priority",
                UNRANKED_BMW_SERIES_PRIORITY,
            ),
        )

    def _find_bmw_make(self) -> dict | None:
        for make in self.makes:
            if is_bmw_make_name(make.get("make_name")):
                return make
        for make in self.makes:
            if make.get("make_id") == 1:
                return make
        return None

    def _build_bmw_models_by_name(self) -> dict[str, dict]:
        if not self.bmw_make:
            return {}

        bmw_make_id = self.bmw_make.get("make_id")
        return {
            str(model.get("model_name", "")).casefold(): model
            for model in self.models
            if model.get("make_id") == bmw_make_id
        }

    def _model(self, model_name: str) -> dict:
        return self.bmw_models_by_name.get(model_name.casefold()) or self.unknown_model

    def _is_parts_listing(self, title_text: str, combined_text: str) -> bool:
        for pattern in PARTS_TITLE_PATTERNS:
            if re.search(pattern, title_text):
                return True

        for pattern in PARTS_COMBINED_PATTERNS:
            if re.search(pattern, combined_text):
                return True

        return False

    def _is_bmw(
        self,
        raw_listing: dict,
        title_text: str,
        description_text: str,
    ) -> bool:
        if BMW_INDICATOR_RE.search(title_text):
            return True

        title_model_name = self._match_bmw_model_name(title_text)
        if is_bmw_make_name(raw_listing.get("search_make_name")) and title_model_name:
            return True

        return bool(
            BMW_INDICATOR_RE.search(description_text)
            and (
                title_model_name
                or self._match_bmw_model_name(description_text)
            )
        )

    def _resolve_bmw_model(
        self,
        raw_listing: dict,
        title_text: str,
        description_text: str,
    ) -> dict:
        title_model_name = self._match_bmw_model_name(title_text)
        if title_model_name:
            return self._model(title_model_name)

        description_model_name = self._match_bmw_model_name(description_text)
        if description_model_name:
            return self._model(description_model_name)

        search_model_name = raw_listing.get("search_model_name")
        if search_model_name and str(search_model_name).casefold() != "unknown":
            return self._model(str(search_model_name))

        return self.unknown_model

    def _match_bmw_model_name(self, text: str) -> str | None:
        if not text:
            return None

        for model_name, pattern in BMW_X_M_MODELS:
            if re.search(pattern, text):
                return model_name

        for model_name, pattern in BMW_M_MODELS:
            if re.search(pattern, text):
                return model_name

        for model_name, pattern in BMW_X_MODELS:
            if re.search(pattern, text):
                return model_name

        if re.search(r"(?<![a-z0-9])z4(?![a-z0-9])", text):
            return "Z4"

        for model_name, badges in BMW_SERIES_BADGES:
            for badge in badges:
                if " " in badge:
                    if badge in text:
                        return model_name
                elif self._has_token(text, badge):
                    return model_name

        return None

    def _has_token(self, text: str, token: str) -> bool:
        return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text) is not None

    def _normalize_seller_type(self, seller_type: Any) -> str | None:
        if seller_type is None:
            return None
        value = str(seller_type).strip().casefold()
        return value if value in {"private", "dealer", "unknown"} else None

    def _detect_listing_issues(self, text: str) -> tuple[bool, list[str], str | None, str | None]:
        if not text:
            return False, [], None, None

        detected: list[tuple[str, str]] = []
        for rule in PROBLEM_ISSUE_RULES:
            if rule["issue_type"] == "engine_failure" and self._has_exclusion_phrase(text):
                continue

            for pattern in rule["patterns"]:
                if re.search(pattern, text):
                    detected.append((rule["issue_type"], rule["confidence"]))
                    break

        if not detected:
            return False, [], None, None

        issue_types: list[str] = []
        issue_type: str | None = None
        issue_confidence = "low"

        for issue, confidence in detected:
            if issue not in issue_types:
                issue_types.append(issue)

            if confidence == "high" and issue_type is None:
                issue_type = issue
                issue_confidence = "high"

        if issue_type is None:
            issue_type, issue_confidence = detected[0]

        return True, issue_types, issue_type, issue_confidence

    def _has_exclusion_phrase(self, text: str) -> bool:
        for pattern in ISSUE_EXCLUSION_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    def _resolve_listing_id(self, raw_listing: dict, normalized_url: str | None) -> str | None:
        listing_id = extract_listing_id(normalized_url)
        if listing_id:
            return str(listing_id)

        raw_listing_id = raw_listing.get("listing_id")
        if raw_listing_id:
            return str(raw_listing_id)

        return None

    def _parse_current_price(
        self,
        raw_listing: dict,
        title: str | None,
        description: str | None,
    ) -> int | None:
        price = parse_price_aud(raw_listing.get("price_text"))
        if price is not None:
            return price

        for value in self._price_candidate_texts(raw_listing, title, description):
            price = extract_price_aud(value)
            if price is not None:
                return price

        return None

    def _price_candidate_texts(
        self,
        raw_listing: dict,
        title: str | None,
        description: str | None,
    ) -> list[str]:
        candidates = [title, description]
        raw_payload = raw_listing.get("raw_payload")
        if isinstance(raw_payload, dict):
            card_text = raw_payload.get("card_text")
            if card_text:
                candidates.append(str(card_text))

            lines = raw_payload.get("lines")
            if isinstance(lines, list):
                candidates.extend(str(line) for line in lines if line)

        return [candidate for candidate in candidates if candidate]

    def _dedupe_key(self, car: dict) -> tuple[str, str] | None:
        source = str(car.get("source") or "")
        listing_id = car.get("listing_id")
        if listing_id:
            return source, str(listing_id)

        normalized_url = car.get("normalized_url")
        if normalized_url:
            return source, str(normalized_url)

        return None
