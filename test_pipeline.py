import asyncio
from datetime import datetime, timezone
from shared.database import SyncSessionLocal
from shared.models import Vehicle
from sqlalchemy import text
from rag.crag_workflow import run_crag_pipeline

def seed_test_vehicle():
    session = SyncSessionLocal()
    # Insert a dummy vehicle if none exist to test metrics
    session.execute(text("""
        INSERT INTO vehicles (riyasewana_id, url, category, title, make, model, yom, price_lkr, mileage_km, fuel_type, transmission, is_active, posted_at, last_seen_at)
        VALUES (
            898989, 'https://example.com/sl', 'cars', 'Toyota Corolla 2018', 'Toyota', 'Corolla', 2018, 8500000, 45000, 'Petrol', 'Automatic', true, NOW(), NOW()
        ) ON CONFLICT (riyasewana_id) DO NOTHING;
    """))
    session.commit()
    session.close()

async def test_embed_pipeline():
    print('Testing query execution...')
    response = await run_crag_pipeline("Show me automatic Toyota cars.")
    print(f"Pipeline executed. Result size: {len(response.get('answer'))}")
    return response

if __name__ == '__main__':
    seed_test_vehicle()
    asyncio.run(test_embed_pipeline())
