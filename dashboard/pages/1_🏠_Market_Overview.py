"""
Prime Wheels SL — 🏠 Market Overview Dashboard Tab.
Treemap of makes, fuel type pie, year distribution, category breakdown.
"""

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlalchemy
import streamlit as st

st.set_page_config(page_title="Market Overview — Prime Wheels SL", page_icon="🏠", layout="wide")
st.title("🏠 Market Overview")


@st.cache_resource
def get_engine():
    db_url = os.getenv("SYNC_DATABASE_URL", "postgresql://pw_user:changeme@localhost:5432/primewheels")
    return sqlalchemy.create_engine(db_url)


@st.cache_data(ttl=300)
def load_data():
    engine = get_engine()
    return pd.read_sql("""
        SELECT make, model, yom, price_lkr, fuel_type, transmission, category, district, province
        FROM vehicles WHERE is_active = TRUE AND make IS NOT NULL
    """, engine)


try:
    df = load_data()
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

if df.empty:
    st.info("No vehicle data available. Run the scraper first.")
    st.stop()

# ── Row 1: Treemap + Fuel Pie ──
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Vehicle Makes Distribution")
    make_counts = df["make"].value_counts().head(20).reset_index()
    make_counts.columns = ["make", "count"]
    fig_treemap = px.treemap(
        make_counts, path=["make"], values="count",
        color="count", color_continuous_scale="Blues",
        title="Top 20 Makes (by listing count)",
    )
    fig_treemap.update_layout(
        height=450, margin=dict(t=40, l=0, r=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_treemap, use_container_width=True)

with col2:
    st.subheader("Fuel Type Breakdown")
    fuel_counts = df["fuel_type"].value_counts().reset_index()
    fuel_counts.columns = ["fuel_type", "count"]
    fig_pie = px.pie(
        fuel_counts, values="count", names="fuel_type",
        color_discrete_sequence=px.colors.qualitative.Set2,
        hole=0.4,
    )
    fig_pie.update_layout(
        height=450, margin=dict(t=20, l=0, r=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# ── Row 2: Year Distribution + Category Breakdown ──
col3, col4 = st.columns(2)

with col3:
    st.subheader("Year of Manufacture Distribution")
    year_df = df[df["yom"].between(2000, 2026)]
    year_fuel = year_df.groupby(["yom", "fuel_type"]).size().reset_index(name="count")
    fig_bar = px.bar(
        year_fuel, x="yom", y="count", color="fuel_type",
        title="Listings by Year × Fuel Type",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_bar.update_layout(
        height=400, barmode="stack",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Year of Manufacture", yaxis_title="Listings",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col4:
    st.subheader("Transmission Split")
    trans_counts = df["transmission"].value_counts().reset_index()
    trans_counts.columns = ["transmission", "count"]
    fig_trans = px.bar(
        trans_counts, x="transmission", y="count",
        color="transmission",
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig_trans.update_layout(
        height=400, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_trans, use_container_width=True)

# ── Row 3: Category Breakdown ──
st.subheader("Vehicle Categories")
cat_counts = df["category"].value_counts().reset_index()
cat_counts.columns = ["category", "count"]
fig_cat = px.bar(
    cat_counts, x="category", y="count",
    color="count", color_continuous_scale="Viridis",
    title="Listings by Vehicle Category",
)
fig_cat.update_layout(
    height=350,
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_cat, use_container_width=True)
