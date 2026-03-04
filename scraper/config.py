"""
Prime Wheels SL — Scraper configuration.
All CSS selectors, URLs, and parsing constants in one place.
"""

# ── Site URLs ──
BASE_URL = "https://riyasewana.com"
SEARCH_URL_TEMPLATE = f"{BASE_URL}/search/{{category}}?page={{page}}"

CATEGORIES = {
    "cars": {"url_slug": "cars", "body_type": "Car"},
    "suvs": {"url_slug": "suvs", "body_type": "SUV"},
    "vans": {"url_slug": "vans", "body_type": "Van"},
    "motorcycles": {"url_slug": "motorcycles", "body_type": "Motorcycle"},
    "lorries": {"url_slug": "lorries", "body_type": "Lorry"},
    "three-wheels": {"url_slug": "three-wheels", "body_type": "Three Wheeler"},
    "pickups": {"url_slug": "pickups", "body_type": "Pickup"},
    "heavy-duties": {"url_slug": "heavy-duties", "body_type": "Heavy-Duty"},
}

# ── Search Page Selectors ──
SEARCH_LISTING_SELECTOR = "li.item.round"
SEARCH_TITLE_SELECTOR = "h2 a"
SEARCH_PRICE_SELECTOR = ".boxtext .boxintxt.b"
SEARCH_BOXINTXT_SELECTOR = ".boxtext .boxintxt"
SEARCH_THUMBNAIL_SELECTOR = ".imgbox img"
SEARCH_LINK_SELECTOR = "h2 a"
SEARCH_PROMOTED_CLASS = "promoted"

# ── Detail Page Selectors ──
DETAIL_SPECS_TABLE = "table.moret"
DETAIL_TITLE_SELECTOR = "h1, h2"
DETAIL_MAIN_IMAGE = "div#imgp img"
DETAIL_THUMBNAILS = ".thumbnails img"
DETAIL_DESCRIPTION = "td.usel.aleft"
DETAIL_PRICE_TD = "td.tfiv"

# ── Specs Table Label Mapping ──
# Maps the text label in the first <td> to our field name
SPECS_LABEL_MAP = {
    "Make": "make",
    "Model": "model",
    "YOM": "yom",
    "Mileage (km)": "mileage_km",
    "Gear": "transmission",
    "Fuel Type": "fuel_type",
    "Engine (cc)": "engine_cc",
    "Options": "options",
    "Colour": "color",
    "Color": "color",
    "Condition": "condition",
}

# ── Browser Settings ──
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
]

VIEWPORT_WIDTH = 1366
VIEWPORT_HEIGHT = 768
LISTINGS_PER_PAGE = 40
