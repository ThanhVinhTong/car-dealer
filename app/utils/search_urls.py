from __future__ import annotations

from urllib.parse import quote

from app.utils.bmw import bmw_series_priority, is_bmw_make_name


SOURCE_FACEBOOK_MARKETPLACE = "facebook_marketplace"


def build_facebook_marketplace_search_url(
    marketplace_location: str,
    min_price: int,
    make_name: str,
    model_name: str,
) -> str:
    location = marketplace_location.strip().strip("/")
    phrase = f'"{make_name.strip()} {model_name.strip()}"'
    encoded_query = quote(phrase, safe="")
    return (
        f"https://www.facebook.com/marketplace/{location}/search"
        f"?minPrice={int(min_price)}&query={encoded_query}&exact=true"
    )


def build_search_targets(
    makes: list[dict],
    models: list[dict],
    marketplace_location: str,
    min_price: int,
) -> list[dict]:
    make_by_id = {make.get("make_id"): make for make in makes}
    joined_rows: list[tuple[int, int, dict, dict]] = []

    for model in models:
        model_name = str(model.get("model_name", "")).strip()
        if not model_name or model_name.casefold() == "unknown":
            continue

        make = make_by_id.get(model.get("make_id"))
        if make is None:
            continue

        make_name = str(make.get("make_name", "")).strip()
        if not is_bmw_make_name(make_name):
            continue

        model_id = int(model.get("model_id"))
        priority = bmw_series_priority(model_name)
        joined_rows.append((priority, model_id, make, model))

    targets = []
    for priority, _, make, model in sorted(
        joined_rows,
        key=lambda row: (row[0], row[1]),
    ):
        make_name = str(make["make_name"]).strip()
        model_name = str(model["model_name"]).strip()
        targets.append(
            {
                "source": SOURCE_FACEBOOK_MARKETPLACE,
                "make_id": make["make_id"],
                "make_name": make_name,
                "model_id": model["model_id"],
                "model_name": model_name,
                "series_priority": priority,
                "marketplace_location": marketplace_location.strip().strip("/"),
                "min_price": int(min_price),
                "search_url": build_facebook_marketplace_search_url(
                    marketplace_location=marketplace_location,
                    min_price=min_price,
                    make_name=make_name,
                    model_name=model_name,
                ),
            }
        )

    return targets
