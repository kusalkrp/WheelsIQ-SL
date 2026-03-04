"""
Prime Wheels SL — Lightweight query constraint extractor.
Extracts structured Qdrant filters from natural language without any LLM call.
Also provides a human-readable formatter for injecting constraints into prompts.
"""

import re

# Sri Lankan districts — lower-case keys, canonical casing as values
_DISTRICTS: dict[str, str] = {
    "colombo": "Colombo",
    "gampaha": "Gampaha",
    "kalutara": "Kalutara",
    "kandy": "Kandy",
    "matale": "Matale",
    "nuwara eliya": "Nuwara Eliya",
    "galle": "Galle",
    "matara": "Matara",
    "hambantota": "Hambantota",
    "jaffna": "Jaffna",
    "kilinochchi": "Kilinochchi",
    "mannar": "Mannar",
    "vavuniya": "Vavuniya",
    "mullaitivu": "Mullaitivu",
    "batticaloa": "Batticaloa",
    "ampara": "Ampara",
    "trincomalee": "Trincomalee",
    "kurunegala": "Kurunegala",
    "puttalam": "Puttalam",
    "anuradhapura": "Anuradhapura",
    "polonnaruwa": "Polonnaruwa",
    "badulla": "Badulla",
    "monaragala": "Monaragala",
    "ratnapura": "Ratnapura",
    "kegalle": "Kegalle",
}

# Longer phrases first to avoid partial matches (e.g. "plug-in hybrid" before "hybrid")
_FUEL_KEYWORDS: list[tuple[str, str]] = [
    ("plug-in hybrid", "Hybrid"),
    ("phev", "Hybrid"),
    ("mild hybrid", "Hybrid"),
    ("full hybrid", "Hybrid"),
    ("hybrid", "Hybrid"),
    ("electric vehicle", "Electric"),
    (" bev ", "Electric"),
    (" ev ", "Electric"),
    ("electric", "Electric"),
    ("diesel", "Diesel"),
    ("petrol", "Petrol"),
    ("gasoline", "Petrol"),
]

# Transmission — longer/more specific first
_TRANSMISSION_KEYWORDS: list[tuple[str, str]] = [
    ("tiptronic", "Automatic"),
    (" cvt ", "Automatic"),
    ("automatic", "Automatic"),
    (" auto ", "Automatic"),
    ("manual", "Manual"),
]

# Vehicle category (Qdrant `category` field values)
_CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    ("three wheeler", "three-wheels"),
    ("three-wheeler", "three-wheels"),
    ("three wheel", "three-wheels"),
    ("trishaw", "three-wheels"),
    ("tuk tuk", "three-wheels"),
    ("tuktuk", "three-wheels"),
    ("heavy duty", "heavy-duties"),
    ("heavy-duty", "heavy-duties"),
    ("pickup truck", "pickups"),
    ("pick-up", "pickups"),
    ("pickup", "pickups"),
    ("lorry", "lorries"),
    ("lorries", "lorries"),
    ("motorcycle", "motorcycles"),
    ("motorbike", "motorcycles"),
    ("motor bike", "motorcycles"),
    (" bike ", "motorcycles"),
    ("minibus", "vans"),
    ("minivan", "vans"),
    (" van ", "vans"),
    (" suv ", "suvs"),
    ("4x4", "suvs"),
    ("4wd", "suvs"),
]

# Popular makes in Sri Lanka — longest first to avoid partial matches
_MAKES: list[str] = sorted([
    "Mercedes-Benz", "Land Rover", "Volkswagen", "Mitsubishi",
    "Toyota", "Suzuki", "Honda", "Nissan", "Hyundai", "Mazda",
    "Daihatsu", "Subaru", "Isuzu", "Peugeot", "Lexus",
    "Ford", "Kia", "BMW", "Audi", "Jeep", "Tata", "Bajaj",
    "Yamaha", "Hero", "TVS", "Micro",
], key=len, reverse=True)

_UPPER_QUALIFIERS = r"(?:under|below|less than|max|maximum|up to|within|no more than)"
_LOWER_QUALIFIERS = r"(?:above|over|more than|minimum|min|at least)"
_UNITS = r"(million|mil|mn|m|lakh|laks|lakhs|lak|l)"

# Ranking/sorting intent — detected as `_ranking` (not a Qdrant filter; stripped before search)
# Order: most specific patterns first
_RANKING_PATTERNS: list[tuple[str, str, str]] = [
    # Mileage
    (r"(?:top|highest?|most|maximum|max|high).{0,25}(?:mileage|km|kilometers?)", "mileage_km", "desc"),
    (r"(?:mileage|km|kilometers?).{0,25}(?:top|highest?|most|maximum)", "mileage_km", "desc"),
    (r"(?:lowest?|least|minimum|min|low).{0,25}(?:mileage|km|kilometers?)", "mileage_km", "asc"),
    (r"(?:mileage|km|kilometers?).{0,25}(?:lowest?|least|minimum|min)", "mileage_km", "asc"),
    # Price
    (r"(?:most expensive|highest? price|priciest?|costliest?)", "price_lkr", "desc"),
    (r"(?:cheapest?|most affordable|lowest? price|best value)", "price_lkr", "asc"),
    # Year
    (r"(?:newest?|latest?|most recent|recent|youngest?)", "yom", "desc"),
    (r"(?:oldest?|earliest?|vintage|classic)", "yom", "asc"),
]


def _parse_price(amount: str, unit: str) -> float:
    value = float(amount.replace(",", ""))
    unit = unit.lower().strip()
    if unit in ("million", "mil", "mn", "m"):
        return value * 1_000_000
    if unit in ("lakh", "laks", "lakhs", "lak", "l"):
        return value * 100_000
    return value


def extract_constraints(query: str) -> dict:
    """
    Extract Qdrant-compatible payload filters from a natural language query.

    Covers:
    - Price: upper/lower/range in million or lakh
    - Year (yom): "2018 or newer", "from 2018", "2015-2020", "before 2020"
    - Mileage: "under 50,000 km"
    - District (all 25 Sri Lankan districts)
    - Fuel type: Hybrid, Electric, Diesel, Petrol
    - Transmission: Automatic, Manual
    - Category: SUV, Van, Motorcycle, Three-wheel, Pickup, Lorry
    - Make: Toyota, Suzuki, Honda, and 20+ more brands

    Returns:
        dict with Qdrant filter fields — may be empty if nothing detected.
    """
    q = " " + query.lower().strip() + " "
    filters: dict = {}

    # ── Price upper bound ──
    upper = re.search(
        _UPPER_QUALIFIERS + r"\s*(?:rs\.?\s*)?([\d,]+(?:\.\d+)?)\s*" + _UNITS, q
    )
    if upper:
        filters["price_lkr"] = {"lte": _parse_price(upper.group(1), upper.group(2))}

    # ── Price lower bound ──
    lower = re.search(
        _LOWER_QUALIFIERS + r"\s*(?:rs\.?\s*)?([\d,]+(?:\.\d+)?)\s*" + _UNITS, q
    )
    if lower:
        lb = _parse_price(lower.group(1), lower.group(2))
        if "price_lkr" in filters:
            filters["price_lkr"]["gte"] = lb
        else:
            filters["price_lkr"] = {"gte": lb}

    # ── Price range: "X to Y million" / "X - Y million" ──
    if "price_lkr" not in filters:
        rng = re.search(
            r"(?:rs\.?\s*)?([\d,]+(?:\.\d+)?)\s*(?:to|-)\s*([\d,]+(?:\.\d+)?)\s*" + _UNITS,
            q,
        )
        if rng:
            filters["price_lkr"] = {
                "gte": _parse_price(rng.group(1), rng.group(3)),
                "lte": _parse_price(rng.group(2), rng.group(3)),
            }

    # ── Year of manufacture — minimum ("2018 or newer", "from 2018", "after 2018") ──
    year_min = re.search(
        r"(20\d{2})\s*(?:or\s*)?(?:newer|above|and above|\+|onwards|onward)|"
        r"(?:from|since|after)\s+(20\d{2})",
        q,
    )
    if year_min:
        yr = int(year_min.group(1) or year_min.group(2))
        filters["yom"] = {"gte": yr}

    # ── Year range: "2015 to 2020" / "2015-2020" ──
    if "yom" not in filters:
        year_rng = re.search(r"(20\d{2})\s*[-–to]+\s*(20\d{2})", q)
        if year_rng:
            filters["yom"] = {
                "gte": int(year_rng.group(1)),
                "lte": int(year_rng.group(2)),
            }

    # ── Year maximum ("before 2020", "older than 2018") ──
    if "yom" not in filters:
        year_max = re.search(r"(?:before|older than|pre[-\s])(20\d{2})", q)
        if year_max:
            filters["yom"] = {"lte": int(year_max.group(1))}

    # ── Mileage upper bound ("under 50,000 km", "below 80k km") ──
    mileage = re.search(
        _UPPER_QUALIFIERS + r"\s*([\d,]+)\s*(?:km|k\b|kilometers?)", q
    )
    if mileage:
        filters["mileage_km"] = {"lte": int(mileage.group(1).replace(",", ""))}

    # ── Location: longest district name first ──
    for keyword in sorted(_DISTRICTS, key=len, reverse=True):
        if keyword in q:
            filters["district"] = _DISTRICTS[keyword]
            break

    # ── Fuel type ──
    for keyword, fuel in _FUEL_KEYWORDS:
        if keyword in q:
            filters["fuel_type"] = fuel
            break

    # ── Transmission ──
    for keyword, trans in _TRANSMISSION_KEYWORDS:
        if keyword in q:
            filters["transmission"] = trans
            break

    # ── Vehicle category ──
    for keyword, category in _CATEGORY_KEYWORDS:
        if keyword in q:
            filters["category"] = category
            break

    # ── Make (brand) ──
    for make in _MAKES:
        if make.lower() in q:
            filters["make"] = make
            break

    # ── Ranking intent (stored as _ranking — NOT a Qdrant filter) ──
    for pattern, field, order in _RANKING_PATTERNS:
        if re.search(pattern, q):
            filters["_ranking"] = {"field": field, "order": order}
            break

    return filters


def format_constraints_text(constraints: dict) -> str:
    """
    Return a human-readable block describing the active constraints.
    Used to inject into grading and synthesis prompts.
    Returns empty string if no constraints.
    """
    if not constraints:
        return ""

    lines = []

    if "price_lkr" in constraints:
        p = constraints["price_lkr"]
        if "gte" in p and "lte" in p:
            lines.append(f"Price: Rs. {p['gte']:,.0f} – Rs. {p['lte']:,.0f}")
        elif "lte" in p:
            lines.append(f"Price: under Rs. {p['lte']:,.0f}")
        elif "gte" in p:
            lines.append(f"Price: above Rs. {p['gte']:,.0f}")

    if "yom" in constraints:
        y = constraints["yom"]
        if "gte" in y and "lte" in y:
            lines.append(f"Year: {y['gte']}–{y['lte']}")
        elif "gte" in y:
            lines.append(f"Year: {y['gte']} or newer")
        elif "lte" in y:
            lines.append(f"Year: {y['lte']} or older")

    if "mileage_km" in constraints:
        m = constraints["mileage_km"]
        if "lte" in m:
            lines.append(f"Mileage: under {m['lte']:,} km")

    if "fuel_type" in constraints:
        lines.append(f"Fuel type: {constraints['fuel_type']}")

    if "transmission" in constraints:
        lines.append(f"Transmission: {constraints['transmission']}")

    if "make" in constraints:
        lines.append(f"Make: {constraints['make']}")

    if "category" in constraints:
        lines.append(f"Vehicle type: {constraints['category']}")

    if "district" in constraints:
        lines.append(f"Location: {constraints['district']} district")

    if "_ranking" in constraints:
        r = constraints["_ranking"]
        field_label = {"mileage_km": "mileage", "price_lkr": "price", "yom": "year"}.get(r["field"], r["field"])
        order_label = "highest first" if r["order"] == "desc" else "lowest first"
        lines.append(f"Sort by: {field_label} ({order_label})")

    if not lines:
        return ""

    block = "\n".join(f"  • {l}" for l in lines)
    return f"\n**Active constraints (ALL must be satisfied):**\n{block}\n"
