"""
Prime Wheels SL — Main Streamlit Dashboard Entry Point.
🚗 Sri Lanka Vehicle Market Intelligence
"""

import streamlit as st

st.set_page_config(
    page_title="Prime Wheels SL — Vehicle Market Intelligence",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for premium look ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }

    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        background: linear-gradient(90deg, #00d2ff, #3a7bd5);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .main-header p {
        font-size: 1.1rem;
        opacity: 0.85;
    }

    .kpi-card {
        background: linear-gradient(135deg, #1e1e2f 0%, #2d2d44 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid #3a7bd5;
        text-align: center;
    }

    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        color: #00d2ff;
    }

    .kpi-label {
        font-size: 0.85rem;
        color: #a0a0b0;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .stMetric {
        background: linear-gradient(135deg, #1e1e2f 0%, #2d2d44 100%);
        padding: 1rem;
        border-radius: 12px;
        border-left: 4px solid #3a7bd5;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.markdown("""
<div class="main-header">
    <h1>🚗 Prime Wheels SL</h1>
    <p>Sri Lanka's Most Intelligent Vehicle Market Dashboard</p>
    <p style="font-size: 0.85rem; opacity: 0.6;">Powered by riyasewana.com data • Updated weekly • RAG-powered insights</p>
</div>
""", unsafe_allow_html=True)


# ── Database Connection ──
@st.cache_resource
def get_db_connection():
    """Get PostgreSQL connection for dashboard queries."""
    import os
    import sqlalchemy
    db_url = os.getenv(
        "SYNC_DATABASE_URL",
        "postgresql://pw_user:changeme@localhost:5432/primewheels"
    )
    return sqlalchemy.create_engine(db_url)


@st.cache_data(ttl=300)
def load_market_stats():
    """Load KPI data from PostgreSQL."""
    import pandas as pd
    engine = get_db_connection()
    try:
        stats = pd.read_sql("""
            SELECT
                COUNT(*) as total_listings,
                ROUND(AVG(price_lkr)::numeric, 0) as avg_price,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mileage_km)::int as median_mileage,
                ROUND(COUNT(*) FILTER (WHERE LOWER(fuel_type) LIKE '%%hybrid%%') * 100.0 / NULLIF(COUNT(*), 0), 1) as pct_hybrid,
                ROUND(COUNT(*) FILTER (WHERE LOWER(transmission) = 'automatic') * 100.0 / NULLIF(COUNT(*), 0), 1) as pct_auto,
                MODE() WITHIN GROUP (ORDER BY make) as top_make
            FROM vehicles
            WHERE is_active = TRUE AND price_lkr IS NOT NULL
        """, engine)
        return stats.iloc[0].to_dict() if not stats.empty else {}
    except Exception as e:
        st.warning(f"Database not available: {e}")
        return {
            "total_listings": 0, "avg_price": 0, "median_mileage": 0,
            "pct_hybrid": 0, "pct_auto": 0, "top_make": "N/A"
        }


# ── KPI Row ──
stats = load_market_stats()
cols = st.columns(6)

kpi_data = [
    ("📊 Total Listings", f"{(stats.get('total_listings') or 0):,}"),
    ("💰 Avg Price", f"Rs. {(stats.get('avg_price') or 0):,.0f}"),
    ("🔧 Median Mileage", f"{(stats.get('median_mileage') or 0):,} km"),
    ("🌿 % Hybrid", f"{(stats.get('pct_hybrid') or 0)}%"),
    ("⚙️ % Automatic", f"{(stats.get('pct_auto') or 0)}%"),
    ("🏆 Top Make", f"{stats.get('top_make') or 'N/A'}"),
]

for col, (label, value) in zip(cols, kpi_data):
    col.metric(label=label, value=value)

st.divider()

# ── Navigation Info ──
st.info(
    "👈 **Navigate** using the sidebar pages: "
    "Market Overview • Pricing Intelligence • Regional Insights • "
    "Best Value Finder • 💬 Chat with Market • 📈 Trends"
)

# ── Quick search ──
st.subheader("🔍 Quick Vehicle Search")
search_cols = st.columns(4)
with search_cols[0]:
    make_filter = st.text_input("Make", placeholder="e.g., Toyota")
with search_cols[1]:
    year_filter = st.slider("Year Range", 1990, 2026, (2015, 2026))
with search_cols[2]:
    price_max = st.number_input("Max Price (Rs.)", value=15_000_000, step=500_000)
with search_cols[3]:
    fuel_filter = st.selectbox("Fuel Type", ["All", "Petrol", "Diesel", "Hybrid", "Electric"])

if st.button("🔍 Search", type="primary"):
    import pandas as pd
    engine = get_db_connection()
    query = """
        SELECT title, make, model, yom, price_lkr, mileage_km, fuel_type, transmission, district
        FROM vehicles
        WHERE is_active = TRUE
    """
    params = {}
    if make_filter:
        query += " AND LOWER(make) = LOWER(%(make)s)"
        params["make"] = make_filter
    query += " AND yom >= %(year_min)s AND yom <= %(year_max)s"
    params["year_min"] = year_filter[0]
    params["year_max"] = year_filter[1]
    query += " AND price_lkr <= %(price_max)s"
    params["price_max"] = price_max
    if fuel_filter != "All":
        query += " AND LOWER(fuel_type) = LOWER(%(fuel)s)"
        params["fuel"] = fuel_filter
    query += " ORDER BY posted_at DESC NULLS LAST LIMIT 50"

    try:
        df = pd.read_sql(query, engine, params=params)
        if not df.empty:
            df["price_lkr"] = df["price_lkr"].apply(
                lambda x: f"Rs. {x:,.0f}" if x else "N/A"
            )
            st.dataframe(df, use_container_width=True, height=400)
            st.caption(f"Showing {len(df)} results")
        else:
            st.info("No vehicles matched your filters.")
    except Exception as e:
        st.error(f"Search error: {e}")
