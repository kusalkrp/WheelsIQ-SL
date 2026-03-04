"""
Prime Wheels SL — HTML parsers for riyasewana.com.
Parses raw HTML from search results and detail pages into structured dicts.
"""

import re
from datetime import datetime

from scraper.config import SPECS_LABEL_MAP
from scraper.location_mapper import map_location
from scraper.validators import (
    extract_riyasewana_id,
    normalize_fuel_type,
    normalize_transmission,
    parse_numeric,
    parse_price,
    validate_engine_cc,
    validate_mileage,
    validate_year,
)
from shared.logging import get_logger

logger = get_logger(__name__)


def parse_search_listing(listing_data: dict) -> dict | None:
    """
    Parse a single search listing card into a structured dict.
    Input is already extracted by Playwright (not raw HTML).

    Args:
        listing_data: Dict with keys from playwright extraction
            {url, title, price_text, location_text, thumbnail_url, is_promoted}

    Returns:
        Normalized dict ready for DB or None if invalid.
    """
    try:
        url = listing_data.get("url", "")
        if not url:
            return None

        riyasewana_id = extract_riyasewana_id(url)
        if not riyasewana_id:
            logger.warning("no_riyasewana_id", url=url)
            return None

        title = (listing_data.get("title") or "").strip()
        if not title:
            return None

        price, is_negotiable = parse_price(listing_data.get("price_text"))
        location_raw = (listing_data.get("location_text") or "").strip()
        district, province = map_location(location_raw)

        # Try to extract year from title
        year = None
        year_match = re.search(r"(19|20)\d{2}", title)
        if year_match:
            year = validate_year(int(year_match.group()))

        # Try to extract make from title (first word often)
        make = None
        title_parts = title.split()
        if title_parts:
            make = title_parts[0]

        return {
            "riyasewana_id": riyasewana_id,
            "url": url,
            "title": title,
            "make": make,
            "year": year,
            "price_lkr": price,
            "is_negotiable": is_negotiable,
            "location_raw": location_raw or None,
            "district": district,
            "province": province,
            "thumbnail_url": listing_data.get("thumbnail_url"),
            "is_premium_ad": listing_data.get("is_promoted", False),
        }
    except Exception as e:
        logger.error("parse_search_listing_error", error=str(e), data=listing_data)
        return None


def parse_detail_page(detail_data: dict) -> dict:
    """
    Parse detail page data into a fully structured vehicle dict.
    Input is already extracted by Playwright.

    Args:
        detail_data: Dict with keys extracted from detail page
            {url, title, price_text, specs (dict), description,
             images, contact, posted_text, view_count, raw_html}

    Returns:
        Normalized dict ready for DB UPSERT.
    """
    result = {
        "url": detail_data.get("url", ""),
        "riyasewana_id": extract_riyasewana_id(detail_data.get("url", "")),
    }

    # Title
    result["title"] = (detail_data.get("title") or "").strip()

    # Price
    price, is_negotiable = parse_price(detail_data.get("price_text"))
    result["price_lkr"] = price
    result["is_negotiable"] = is_negotiable

    # Parse specs table
    specs = detail_data.get("specs", {})
    for label, field_name in SPECS_LABEL_MAP.items():
        raw_value = specs.get(label, "").strip()
        if not raw_value:
            continue

        if field_name == "yom":
            result["yom"] = validate_year(parse_numeric(raw_value))
        elif field_name == "mileage_km":
            result["mileage_km"] = validate_mileage(parse_numeric(raw_value))
        elif field_name == "engine_cc":
            result["engine_cc"] = validate_engine_cc(parse_numeric(raw_value))
        elif field_name == "transmission":
            result["transmission"] = normalize_transmission(raw_value)
        elif field_name == "fuel_type":
            result["fuel_type"] = normalize_fuel_type(raw_value)
        elif field_name == "options":
            result["options"] = [
                opt.strip().upper()
                for opt in raw_value.split(",")
                if opt.strip()
            ]
        elif field_name in ("make", "model", "color", "condition"):
            result[field_name] = raw_value

    # Year fallback: use YOM if present, else parse from title
    if not result.get("yom") and result.get("title"):
        year_match = re.search(r"(19|20)\d{2}", result["title"])
        if year_match:
            result["yom"] = validate_year(int(year_match.group()))
    result["year"] = result.get("yom")

    # Location
    location_raw = (detail_data.get("location") or "").strip()
    result["location_raw"] = location_raw or None
    district, province = map_location(location_raw)
    result["district"] = district
    result["province"] = province

    # Description
    result["description"] = (detail_data.get("description") or "").strip() or None

    # Images
    images = detail_data.get("images", [])
    result["images"] = [img for img in images if img] if images else None

    # Contact
    contact = (detail_data.get("contact") or "").strip()
    # Extract Sri Lankan phone number
    phone_match = re.search(r"0\d{9}", contact.replace(" ", "").replace("-", ""))
    result["contact_phone"] = phone_match.group() if phone_match else contact or None

    # Seller name
    result["seller_name"] = (detail_data.get("seller_name") or "").strip() or None

    # Posted date
    posted_text = detail_data.get("posted_text", "")
    result["posted_at"] = _parse_posted_date(posted_text)

    # View count
    view_text = detail_data.get("view_count", "")
    result["view_count"] = parse_numeric(view_text) or 0

    # Raw data
    result["raw_html"] = detail_data.get("raw_html")
    result["raw_json"] = detail_data

    return result


def _parse_posted_date(text: str) -> datetime | None:
    """Parse the posted date from various formats."""
    if not text:
        return None

    # Try: "2026-02-27 7:16 am"
    date_match = re.search(
        r"(\d{4}-\d{2}-\d{2})\s*(\d{1,2}:\d{2}\s*[ap]m)?",
        text,
        re.IGNORECASE,
    )
    if date_match:
        date_str = date_match.group(1)
        time_str = date_match.group(2)
        try:
            if time_str:
                return datetime.strptime(
                    f"{date_str} {time_str.strip()}", "%Y-%m-%d %I:%M %p"
                )
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass

    # Try: "27 Feb 2026"
    date_match = re.search(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", text)
    if date_match:
        try:
            return datetime.strptime(date_match.group(), "%d %b %Y")
        except ValueError:
            pass

    return None
