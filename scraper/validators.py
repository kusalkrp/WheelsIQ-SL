"""
Prime Wheels SL — Data validators.
Ensures scraped data is within sane ranges before DB insertion.
"""

import re
from datetime import datetime

from shared.logging import get_logger

logger = get_logger(__name__)

# ── Validation constants ──
MIN_YEAR = 1970
MAX_YEAR = datetime.now().year + 1
MIN_PRICE_LKR = 50_000          # Rs. 50k (even a three-wheeler costs more)
MAX_PRICE_LKR = 500_000_000     # Rs. 500M (ultra-luxury)
MIN_MILEAGE = 0
MAX_MILEAGE = 1_000_000         # 1M km
MIN_ENGINE_CC = 49              # 50cc minimum (mopeds)
MAX_ENGINE_CC = 15_000          # 15,000cc (trucks)

VALID_TRANSMISSIONS = {
    "manual", "automatic", "tiptronic", "cvt",
    "semi-automatic", "dual clutch", "amt",
}

VALID_FUEL_TYPES = {
    "petrol", "diesel", "hybrid", "electric",
    "cng", "lpg", "plug-in hybrid", "flex fuel",
}

VALID_CONDITIONS = {
    "registered", "reconditioned", "brand new", "used", "unregistered",
}


def validate_year(year: int | None) -> int | None:
    """Validate year is in sane range."""
    if year is None:
        return None
    if MIN_YEAR <= year <= MAX_YEAR:
        return year
    logger.warning("invalid_year", year=year)
    return None


def validate_price(price: float | None) -> float | None:
    """Validate price is in sane range."""
    if price is None:
        return None
    if MIN_PRICE_LKR <= price <= MAX_PRICE_LKR:
        return price
    logger.warning("invalid_price", price=price)
    return None


def validate_mileage(mileage: int | None) -> int | None:
    """Validate mileage is in sane range."""
    if mileage is None:
        return None
    if MIN_MILEAGE <= mileage <= MAX_MILEAGE:
        return mileage
    logger.warning("invalid_mileage", mileage=mileage)
    return None


def validate_engine_cc(cc: int | None) -> int | None:
    """Validate engine CC is in sane range."""
    if cc is None:
        return None
    if MIN_ENGINE_CC <= cc <= MAX_ENGINE_CC:
        return cc
    logger.warning("invalid_engine_cc", cc=cc)
    return None


def normalize_transmission(value: str | None) -> str | None:
    """Normalize transmission to standard values."""
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in VALID_TRANSMISSIONS:
        return value.strip().title()
    # Try common aliases
    aliases = {
        "auto": "Automatic",
        "man": "Manual",
        "tip": "Tiptronic",
    }
    for alias, standard in aliases.items():
        if alias in normalized:
            return standard
    return value.strip().title()


def normalize_fuel_type(value: str | None) -> str | None:
    """Normalize fuel type to standard values."""
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in VALID_FUEL_TYPES:
        return value.strip().title()
    # Common aliases
    aliases = {
        "gas": "Petrol",
        "ev": "Electric",
        "phev": "Plug-in Hybrid",
    }
    for alias, standard in aliases.items():
        if alias in normalized:
            return standard
    return value.strip().title()


def parse_numeric(text: str | None) -> int | None:
    """Extract first integer from text, stripping non-numeric chars."""
    if not text:
        return None
    # Remove commas, spaces, and extract digits
    cleaned = re.sub(r"[^\d]", "", text)
    if cleaned:
        try:
            return int(cleaned)
        except ValueError:
            return None
    return None


def parse_price(text: str | None) -> tuple[float | None, bool]:
    """
    Parse price text. Returns (price, is_negotiable).
    Handles: "Rs.8,500,000", "Rs 8.5M", "Negotiable", "Call for price"
    """
    if not text:
        return None, False

    is_negotiable = any(kw in text.lower() for kw in ["negotiable", "neg", "ono"])

    # Remove currency symbols and normalize
    cleaned = text.replace("Rs.", "").replace("Rs", "").replace(",", "").strip()

    # Handle "X.XM" or "X.Xm" (millions shorthand)
    m_match = re.search(r"(\d+\.?\d*)\s*[mM]", cleaned)
    if m_match:
        price = float(m_match.group(1)) * 1_000_000
        return validate_price(price), is_negotiable

    # Standard numeric
    price_match = re.search(r"[\d.]+", cleaned)
    if price_match:
        try:
            price = float(price_match.group())
            return validate_price(price), is_negotiable
        except ValueError:
            pass

    return None, is_negotiable


def extract_riyasewana_id(url: str) -> int | None:
    """Extract the numeric ad ID from a riyasewana URL."""
    match = re.search(r"-(\d+)$", url)
    if match:
        return int(match.group(1))
    # Fallback: try any number at the end
    match = re.search(r"(\d+)\.html?$", url)
    if match:
        return int(match.group(1))
    return None
