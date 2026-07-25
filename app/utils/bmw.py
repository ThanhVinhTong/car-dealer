from __future__ import annotations

import re


BMW_MAKE_NAME = "bmw"
UNRANKED_BMW_SERIES_PRIORITY = 6

BMW_CHASSIS_GENERATION_RE = re.compile(
    r"(?<![a-z0-9])([efg])[\s-]?(\d{2,3})(?![a-z0-9])",
    re.IGNORECASE,
)

BMW_SERIES_PRIORITIES = {
    "3 series": 1,
    "4 series": 1,
    "m3": 1,
    "m4": 1,
    "2 series": 2,
    "m2": 2,
    "5 series": 3,
    "6 series": 3,
    "m5": 3,
    "m6": 3,
    "7 series": 4,
    "1 series": 5,
}


def is_bmw_make_name(value: object) -> bool:
    return str(value or "").strip().casefold() == BMW_MAKE_NAME


def detect_bmw_chassis_generation(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue

        match = BMW_CHASSIS_GENERATION_RE.search(str(value))
        if match:
            return f"{match.group(1).upper()}{match.group(2)}"

    return None


def bmw_series_priority(model_name: object) -> int:
    normalized_name = re.sub(
        r"[^a-z0-9]+",
        " ",
        str(model_name or "").casefold(),
    ).strip()
    return BMW_SERIES_PRIORITIES.get(
        normalized_name,
        UNRANKED_BMW_SERIES_PRIORITY,
    )
