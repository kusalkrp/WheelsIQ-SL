"""
Prime Wheels SL — 📈 Trends Dashboard Tab.
Weekly price movements, new listings volume, make popularity shifts.
(Available after 2+ weeks of data collection)
"""

import os

import pandas as pd
import plotly.express as px
import sqlalchemy
import streamlit as st

st.set_page_config(page_title="Trends — Prime Wheels SL", page_icon="📈", layout="wide")
st.title("📈 Market Trends")
st.caption("Track how the Sri Lankan vehicle market evolves over time")


@st.cache_resource
def get_engine():
    db_url = os.getenv("SYNC_DATABASE_URL", "postgresql://pw_user:changeme@localhost:5432/primewheels")
    return sqlalchemy.create_engine(db_url)


@st.cache_data(ttl=600)
def load_data():
    engine = get_engine()
    return pd.read_sql("""
        SELECT make, model, yom, price_lkr, mileage_km, fuel_type,
               scraped_at, posted_at, district, category
        FROM vehicles
        WHERE price_lkr IS NOT NULL AND scraped_at IS NOT NULL
    """, engine)


try:
    df = load_data()
except Exception:
    st.error("Database not available.")
    st.stop()

if df.empty:
    st.info("No trend data available yet. Trends will appear after 2+ weeks of scraping.")
    st.stop()

# Convert timestamps
df["scraped_week"] = pd.to_datetime(df["scraped_at"]).dt.to_period("W").dt.start_time
df["posted_week"] = pd.to_datetime(df["posted_at"]).dt.to_period("W").dt.start_time

# ── Row 1: New Listings Trend ──
st.subheader("📊 New Listings Over Time")
weekly_listings = df.groupby("scraped_week").size().reset_index(name="new_listings")
fig_listings = px.line(
    weekly_listings, x="scraped_week", y="new_listings",
    markers=True,
    color_discrete_sequence=["#3a7bd5"],
)
fig_listings.update_layout(
    height=350,
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    xaxis_title="Week", yaxis_title="New Listings Scraped",
)
st.plotly_chart(fig_listings, use_container_width=True)

# ── Row 2: Avg Price Trend by Top Makes ──
st.subheader("💰 Average Price Trend by Make")
top_makes = df["make"].value_counts().head(5).index.tolist()
if top_makes:
    make_filtered = df[df["make"].isin(top_makes)]
    weekly_price = make_filtered.groupby(["scraped_week", "make"])["price_lkr"].mean().reset_index()
    fig_price = px.line(
        weekly_price, x="scraped_week", y="price_lkr", color="make",
        markers=True,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_price.update_layout(
        height=400,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Week", yaxis_title="Avg Price (Rs.)",
    )
    fig_price.update_yaxes(tickformat=",")
    st.plotly_chart(fig_price, use_container_width=True)

# ── Row 3: Fuel Type Trend ──
st.subheader("🌿 Fuel Type Popularity Trend")
fuel_weekly = df.groupby(["scraped_week", "fuel_type"]).size().reset_index(name="count")
fig_fuel = px.area(
    fuel_weekly, x="scraped_week", y="count", color="fuel_type",
    color_discrete_sequence=px.colors.qualitative.Set2,
)
fig_fuel.update_layout(
    height=350,
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_fuel, use_container_width=True)

# ── Row 4: Category Breakdown Trend ──
st.subheader("📂 Category Volume Trend")
cat_weekly = df.groupby(["scraped_week", "category"]).size().reset_index(name="count")
fig_cat = px.bar(
    cat_weekly, x="scraped_week", y="count", color="category",
    barmode="stack",
    color_discrete_sequence=px.colors.qualitative.Pastel,
)
fig_cat.update_layout(
    height=350,
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_cat, use_container_width=True)
