"""
Prime Wheels SL — Document builder.
Transforms PostgreSQL vehicle rows into LlamaIndex Documents for RAG ingestion.
"""

from llama_index.core import Document
from sqlalchemy import text

from shared.database import SyncSessionLocal
from shared.logging import get_logger

logger = get_logger(__name__)


def build_vehicle_document(row: dict) -> Document:
    """
    Build a LlamaIndex Document from a vehicle database row.
    The text is structured for optimal retrieval and synthesis.
    """
    # Build structured header
    parts = []

    # Identity line — Make | Model | Year | Condition
    make = row.get("make", "Unknown")
    model = row.get("model", "")
    yom = row.get("yom", "")
    identity = f"{make} {model} {yom}".strip()
    if row.get("condition"):
        identity += f" ({row['condition']})"
    parts.append(identity)

    # Price line with tier label
    price = row.get("price_lkr")
    if price:
        price_str = f"Price: Rs. {price:,.0f}"
        if row.get("is_negotiable"):
            price_str += " (Negotiable)"
        if price < 2_000_000:
            price_str += " [Budget]"
        elif price < 6_000_000:
            price_str += " [Mid-Range]"
        elif price < 15_000_000:
            price_str += " [Premium]"
        else:
            price_str += " [Luxury]"
        parts.append(price_str)
    else:
        parts.append("Price: Contact seller")

    # Fuel type on its own line — critical for constraint matching
    if row.get("fuel_type"):
        parts.append(f"Fuel: {row['fuel_type']}")

    # Transmission on its own line
    if row.get("transmission"):
        parts.append(f"Transmission: {row['transmission']}")

    # Year of manufacture explicit label
    if yom:
        parts.append(f"Year: {yom}")

    # Remaining specs
    specs = []
    if row.get("engine_cc"):
        specs.append(f"{row['engine_cc']}cc")
    if row.get("mileage_km"):
        specs.append(f"{row['mileage_km']:,} km")
    if row.get("color"):
        specs.append(row["color"])
    if specs:
        parts.append(f"Specs: {' | '.join(specs)}")

    # Location
    location_parts = []
    if row.get("location_raw"):
        location_parts.append(row["location_raw"])
    if row.get("district"):
        location_parts.append(row["district"])
    if row.get("province"):
        location_parts.append(f"{row['province']} Province")
    if location_parts:
        parts.append(f"Location: {', '.join(location_parts)}")

    # Category / Body type
    if row.get("body_type"):
        parts.append(f"Type: {row['body_type']}")
    elif row.get("category"):
        parts.append(f"Category: {row['category']}")

    # Options / Features
    options = row.get("options")
    if options and isinstance(options, list):
        parts.append(f"Features: {', '.join(options)}")

    # Listing URL — so the synthesizer can include it for the user
    if row.get("url"):
        parts.append(f"Listing URL: {row['url']}")

    # Separator
    parts.append("---")

    # Description (seller notes)
    if row.get("description"):
        parts.append(row["description"])

    text_content = "\n".join(parts)

    # Metadata for Qdrant payload filtering
    metadata = {
        "vehicle_id": row.get("id"),
        "riyasewana_id": row.get("riyasewana_id"),
        "category": row.get("category"),
        "make": row.get("make"),
        "model": row.get("model"),
        "yom": row.get("yom"),
        "year": row.get("year"),
        "price_lkr": float(row["price_lkr"]) if row.get("price_lkr") else None,
        "mileage_km": row.get("mileage_km"),
        "fuel_type": row.get("fuel_type"),
        "transmission": row.get("transmission"),
        "engine_cc": row.get("engine_cc"),
        "color": row.get("color"),
        "condition": row.get("condition"),
        "district": row.get("district"),
        "province": row.get("province"),
        "is_negotiable": row.get("is_negotiable", False),
        "is_active": row.get("is_active", True),
        "url": row.get("url"),
    }

    # Remove None values from metadata
    metadata = {k: v for k, v in metadata.items() if v is not None}

    return Document(
        text=text_content,
        metadata=metadata,
        doc_id=f"vehicle_{row.get('riyasewana_id', row.get('id'))}",
    )


def load_vehicles_as_documents(
    category: str | None = None,
    active_only: bool = True,
    limit: int | None = None,
) -> list[Document]:
    """
    Load vehicles from PostgreSQL and convert to LlamaIndex Documents.

    Args:
        category: Filter by category (None = all)
        active_only: Only active listings
        limit: Max number of vehicles

    Returns:
        List of LlamaIndex Documents
    """
    session = SyncSessionLocal()
    try:
        query = "SELECT * FROM vehicles WHERE 1=1"
        params = {}

        if active_only:
            query += " AND is_active = TRUE"
        if category:
            query += " AND category = :category"
            params["category"] = category
        query += " ORDER BY posted_at DESC NULLS LAST"
        if limit:
            query += " LIMIT :limit"
            params["limit"] = limit

        result = session.execute(text(query), params)
        rows = [dict(row._mapping) for row in result]

        documents = []
        for row in rows:
            try:
                doc = build_vehicle_document(row)
                documents.append(doc)
            except Exception as e:
                logger.error("document_build_error", vehicle_id=row.get("id"), error=str(e))

        logger.info("documents_loaded", count=len(documents), category=category)
        return documents
    finally:
        session.close()
