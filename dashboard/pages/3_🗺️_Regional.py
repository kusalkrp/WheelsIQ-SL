"""
Prime Wheels SL — 🗺️ Regional Insights Dashboard Tab.
Listings per district, avg price by province.
"""

import os

import pandas as pd
import plotly.express as px
import sqlalchemy
import streamlit as st

st.set_page_config(page_title="Regional Insights — Prime Wheels SL", page_icon="🗺️", layout="wide")
st.title("🗺️ Regional Insights")


@st.cache_resource
def get_engine():
    db_url = os.getenv("SYNC_DATABASE_URL", "postgresql://pw_user:changeme@localhost:5432/primewheels")
    return sqlalchemy.create_engine(db_url)


@st.cache_data(ttl=300)
def load_data():
    engine = get_engine()
    return pd.read_sql("""
        SELECT make, model, yom, price_lkr, mileage_km, fuel_type, district, province
        FROM vehicles
        WHERE is_active = TRUE AND district IS NOT NULL
    """, engine)


try:
    df = load_data()
except Exception:
    st.error("Database not available.")
    st.stop()

if df.empty:
    st.info("No regional data available.")
    st.stop()

# ── Row 1: Top Districts ──
col1, col2 = st.columns(2)

with col1:
    st.subheader("Listings by District")
    district_counts = df["district"].value_counts().head(15).reset_index()
    district_counts.columns = ["district", "count"]
    fig = px.bar(
        district_counts, x="count", y="district",
        orientation="h",
        color="count", color_continuous_scale="Blues",
    )
    fig.update_layout(
        height=500, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Average Price by Province")
    province_price = df.groupby("province")["price_lkr"].agg(["mean", "count"]).reset_index()
    province_price.columns = ["province", "avg_price", "count"]
    province_price = province_price[province_price["count"] >= 5]
    province_price = province_price.sort_values("avg_price", ascending=False)

    fig2 = px.bar(
        province_price, x="avg_price", y="province",
        orientation="h",
        color="avg_price", color_continuous_scale="YlOrRd",
        text=province_price["avg_price"].apply(lambda x: f"Rs.{x:,.0f}"),
    )
    fig2.update_layout(
        height=500, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(autorange="reversed"),
        xaxis_title="Avg Price (Rs.)",
    )
    st.plotly_chart(fig2, use_container_width=True)

# ── Row 2: Make popularity by district ──
st.subheader("Top Makes by District")
district_makes = df.groupby(["district", "make"]).size().reset_index(name="count")
top_districts = df["district"].value_counts().head(10).index
district_makes_filtered = district_makes[district_makes["district"].isin(top_districts)]

# Get top make per district
top_make_per_district = (
    district_makes_filtered
    .sort_values("count", ascending=False)
    .drop_duplicates(subset="district")
    .sort_values("count", ascending=False)
)
st.dataframe(top_make_per_district, use_container_width=True, height=300)

# ── Row 3: Fuel type by province ──
st.subheader("Fuel Type Distribution by Province")
fuel_province = df.groupby(["province", "fuel_type"]).size().reset_index(name="count")
fig3 = px.bar(
    fuel_province, x="province", y="count", color="fuel_type",
    barmode="group",
    color_discrete_sequence=px.colors.qualitative.Set2,
)
fig3.update_layout(
    height=400,
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig3, use_container_width=True)
