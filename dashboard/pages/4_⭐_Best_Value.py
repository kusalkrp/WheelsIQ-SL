"""
Prime Wheels SL — ⭐ Best Value Finder Dashboard Tab.
Value score calculation and sortable table.
"""

import os

import pandas as pd
import plotly.express as px
import numpy as np
import sqlalchemy
import streamlit as st

st.set_page_config(page_title="Best Value Finder — Prime Wheels SL", page_icon="⭐", layout="wide")
st.title("⭐ Best Value Finder")
st.caption("Find the best deals in the Sri Lankan vehicle market")


@st.cache_resource
def get_engine():
    db_url = os.getenv("SYNC_DATABASE_URL", "postgresql://pw_user:changeme@localhost:5432/primewheels")
    return sqlalchemy.create_engine(db_url)


@st.cache_data(ttl=300)
def load_data():
    engine = get_engine()
    return pd.read_sql("""
        SELECT id, title, make, model, yom, price_lkr, mileage_km, fuel_type,
               transmission, engine_cc, condition, district, url, is_negotiable
        FROM vehicles
        WHERE is_active = TRUE AND price_lkr IS NOT NULL
          AND price_lkr > 100000 AND yom >= 2005
          AND mileage_km IS NOT NULL AND mileage_km > 0
    """, engine)


try:
    df = load_data()
except Exception:
    st.error("Database not available.")
    st.stop()

if df.empty:
    st.info("No vehicle data available for value analysis.")
    st.stop()

# ── Filters ──
with st.sidebar:
    st.header("🔍 Value Filters")
    budget_max = st.number_input("Max Budget (Rs.)", value=10_000_000, step=500_000)
    year_min = st.slider("Min Year", 2005, 2026, 2015)
    mileage_max = st.number_input("Max Mileage (km)", value=150_000, step=10_000)
    fuel_pref = st.selectbox("Fuel Preference", ["All", "Petrol", "Diesel", "Hybrid", "Electric"])

# Apply filters
filtered = df[
    (df["price_lkr"] <= budget_max) &
    (df["yom"] >= year_min) &
    (df["mileage_km"] <= mileage_max)
]
if fuel_pref != "All":
    filtered = filtered[filtered["fuel_type"].str.lower() == fuel_pref.lower()]

if filtered.empty:
    st.info("No vehicles match your filters. Try adjusting the criteria.")
    st.stop()

# ── Calculate Value Score ──
# Score formula: higher is better
# Factors: newer year (+), lower price (+), lower mileage (+), hybrid bonus (+)
def calculate_value_score(row):
    year_score = (row["yom"] - 2000) / 26 * 30  # 0-30 points for year
    price_score = max(0, (1 - row["price_lkr"] / 20_000_000)) * 30  # 0-30 points
    mileage_score = max(0, (1 - row["mileage_km"] / 300_000)) * 25  # 0-25 points
    fuel_bonus = 10 if "hybrid" in str(row.get("fuel_type", "")).lower() else 0
    negotiable_bonus = 5 if row.get("is_negotiable", False) else 0
    return round(year_score + price_score + mileage_score + fuel_bonus + negotiable_bonus, 1)


filtered = filtered.copy()
filtered["value_score"] = filtered.apply(calculate_value_score, axis=1)
filtered = filtered.sort_values("value_score", ascending=False)

# ── KPI Row ──
st.subheader(f"🎯 Found {len(filtered)} vehicles in your budget")
mcols = st.columns(4)
mcols[0].metric("Best Score", f"{filtered['value_score'].max():.0f}/100")
mcols[1].metric("Avg Value Score", f"{filtered['value_score'].mean():.0f}/100")
mcols[2].metric("Best Price", f"Rs. {filtered['price_lkr'].min():,.0f}")
mcols[3].metric("Lowest Mileage", f"{filtered['mileage_km'].min():,} km")

# ── Top Deals Table ──
st.subheader("🏅 Top 30 Best Value Vehicles")
display_df = filtered.head(30)[[
    "value_score", "title", "make", "model", "yom", "price_lkr",
    "mileage_km", "fuel_type", "transmission", "district", "url"
]].copy()
display_df["price_lkr"] = display_df["price_lkr"].apply(lambda x: f"Rs. {x:,.0f}")
display_df["mileage_km"] = display_df["mileage_km"].apply(lambda x: f"{x:,} km")
display_df = display_df.rename(columns={
    "value_score": "💎 Score",
    "title": "Vehicle",
    "make": "Make",
    "model": "Model",
    "yom": "Year",
    "price_lkr": "Price",
    "mileage_km": "Mileage",
    "fuel_type": "Fuel",
    "transmission": "Trans.",
    "district": "District",
    "url": "🔗 Link",
})
st.dataframe(display_df, use_container_width=True, height=600)

# ── Value Score Distribution ──
st.subheader("Value Score Distribution")
fig = px.histogram(
    filtered, x="value_score", nbins=30,
    color_discrete_sequence=["#3a7bd5"],
    title="Distribution of Value Scores",
)
fig.update_layout(
    height=300,
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    xaxis_title="Value Score", yaxis_title="Count",
)
st.plotly_chart(fig, use_container_width=True)
