"""
Prime Wheels SL — Location mapper.
Maps raw location strings from riyasewana to district/province.
Falls back to fuzzy matching then stores new mappings.
"""

from shared.logging import get_logger

logger = get_logger(__name__)

# ── District → Province (full Sri Lanka) ──
DISTRICT_TO_PROVINCE = {
    "Colombo": "Western", "Gampaha": "Western", "Kalutara": "Western",
    "Kandy": "Central", "Matale": "Central", "Nuwara Eliya": "Central",
    "Galle": "Southern", "Matara": "Southern", "Hambantota": "Southern",
    "Jaffna": "Northern", "Kilinochchi": "Northern", "Mullaitivu": "Northern",
    "Mannar": "Northern", "Vavuniya": "Northern",
    "Batticaloa": "Eastern", "Ampara": "Eastern", "Trincomalee": "Eastern",
    "Kurunegala": "North Western", "Puttalam": "North Western",
    "Anuradhapura": "North Central", "Polonnaruwa": "North Central",
    "Badulla": "Uva", "Monaragala": "Uva",
    "Ratnapura": "Sabaragamuwa", "Kegalle": "Sabaragamuwa",
}

# ── Known location → district (extend as scraper encounters new ones) ──
LOCATION_TO_DISTRICT = {
    # Western - Colombo
    "Colombo": "Colombo", "Battaramulla": "Colombo", "Nugegoda": "Colombo",
    "Dehiwala": "Colombo", "Maharagama": "Colombo", "Piliyandala": "Colombo",
    "Moratuwa": "Colombo", "Kottawa": "Colombo", "Kaduwela": "Colombo",
    "Rajagiriya": "Colombo", "Boralesgamuwa": "Colombo", "Malabe": "Colombo",
    "Athurugiriya": "Colombo", "Homagama": "Colombo", "Nawala": "Colombo",
    "Wellampitiya": "Colombo", "Kotikawatta": "Colombo", "Mulleriyawa": "Colombo",
    "Mount Lavinia": "Colombo", "Ratmalana": "Colombo", "Kotte": "Colombo",
    "Sri Jayawardenepura": "Colombo", "Thalawathugoda": "Colombo",
    "Pannipitiya": "Colombo", "Padukka": "Colombo", "Avissawella": "Colombo",
    # Western - Gampaha
    "Gampaha": "Gampaha", "Kadawatha": "Gampaha", "Wattala": "Gampaha",
    "Negombo": "Gampaha", "Ja-Ela": "Gampaha", "Kiribathgoda": "Gampaha",
    "Kelaniya": "Gampaha", "Minuwangoda": "Gampaha", "Nittambuwa": "Gampaha",
    "Delgoda": "Gampaha", "Ragama": "Gampaha", "Kandana": "Gampaha",
    "Ganemulla": "Gampaha", "Seeduwa": "Gampaha", "Katunayake": "Gampaha",
    # Western - Kalutara
    "Kalutara": "Kalutara", "Panadura": "Kalutara", "Horana": "Kalutara",
    "Bandaragama": "Kalutara", "Beruwala": "Kalutara", "Aluthgama": "Kalutara",
    # Central
    "Kandy": "Kandy", "Peradeniya": "Kandy", "Katugastota": "Kandy",
    "Matale": "Matale", "Nuwara Eliya": "Nuwara Eliya",
    # Southern
    "Galle": "Galle", "Matara": "Matara", "Hambantota": "Hambantota",
    "Weligama": "Matara", "Ambalangoda": "Galle", "Hikkaduwa": "Galle",
    "Tangalle": "Hambantota",
    # Northern
    "Jaffna": "Jaffna", "Kilinochchi": "Kilinochchi", "Vavuniya": "Vavuniya",
    # Eastern
    "Batticaloa": "Batticaloa", "Trincomalee": "Trincomalee", "Ampara": "Ampara",
    # North Western
    "Kurunegala": "Kurunegala", "Puttalam": "Puttalam", "Chilaw": "Puttalam",
    # North Central
    "Anuradhapura": "Anuradhapura", "Polonnaruwa": "Polonnaruwa",
    # Uva
    "Badulla": "Badulla", "Monaragala": "Monaragala",
    # Sabaragamuwa
    "Ratnapura": "Ratnapura", "Kegalle": "Kegalle",
}

# Case-insensitive lookup
_LOCATION_LOOKUP = {k.lower(): v for k, v in LOCATION_TO_DISTRICT.items()}


def map_location(raw_location: str | None) -> tuple[str | None, str | None]:
    """
    Map a raw location string to (district, province).

    Args:
        raw_location: Raw location text from riyasewana (e.g., "Battaramulla", "Colombo 5")

    Returns:
        Tuple of (district, province) or (None, None) if unmappable
    """
    if not raw_location:
        return None, None

    location = raw_location.strip()

    # Direct lookup (case-insensitive)
    district = _LOCATION_LOOKUP.get(location.lower())
    if district:
        province = DISTRICT_TO_PROVINCE.get(district)
        return district, province

    # Try stripping numbers (e.g., "Colombo 5" → "Colombo")
    base_location = "".join(c for c in location if not c.isdigit()).strip()
    district = _LOCATION_LOOKUP.get(base_location.lower())
    if district:
        province = DISTRICT_TO_PROVINCE.get(district)
        return district, province

    # Try matching district names directly
    for district_name, province_name in DISTRICT_TO_PROVINCE.items():
        if district_name.lower() in location.lower():
            return district_name, province_name

    logger.warning("unmapped_location", location=raw_location)
    return None, None
