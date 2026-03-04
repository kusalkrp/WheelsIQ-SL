"""
Prime Wheels SL — 💰 Pricing Intelligence Dashboard Tab.
Boxplots, scatter, heatmap, depreciation curves.
"""

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import sqlalchemy
import streamlit as st

st.set_page_config(page_title="Pricing Intelligence — Prime Wheels SL", page_icon="💰", layout="wide")
st.title("💰 Pricing Intelligence")


@st.cache_resource
def get_engine():
    db_url = os.getenv("SYNC_DATABASE_URL", "postgresql://pw_user:changeme@localhost:5432/primewheels")
    return sqlalchemy.create_engine(db_url)


@st.cache_data(ttl=300)
def load_data():
    engine = get_engine()
    return pd.read_sql("""
        SELECT make, model, yom, price_lkr, mileage_km, fuel_type, transmission, district
        FROM vehicles
        WHERE is_active = TRUE AND price_lkr IS NOT NULL AND price_lkr > 100000
    """, engine)


try:
    df = load_data()
except Exception:
    st.error("Database not available.")
    st.stop()

if df.empty:
    st.info("No pricing data available.")
    st.stop()

# ── Filters ──
with st.sidebar:
    st.header("🔍 Filters")
    top_makes = df["make"].value_counts().head(15).index.tolist()
    selected_makes = st.multiselect("Makes", top_makes, default=top_makes[:5])
    year_range = st.slider("Year Range", 2000, 2026, (2015, 2026))

filtered = df[
    df["make"].isin(selected_makes) &
    df["yom"].between(year_range[0], year_range[1])
]

# ── Row 1: Price Box Plot + Scatter ──
col1, col2 = st.columns(2)

with col1:
    st.subheader("Price Distribution by Make")
    fig_box = px.box(
        filtered, x="make", y="price_lkr",
        color="make",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_box.update_layout(
        height=450, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Price (Rs.)", xaxis_title="",
    )
    fig_box.update_yaxes(tickformat=",")
    st.plotly_chart(fig_box, use_container_width=True)

with col2:
    st.subheader("Price vs Mileage")
    scatter_df = filtered.dropna(subset=["mileage_km"])
    if not scatter_df.empty:
        fig_scatter = px.scatter(
            scatter_df, x="mileage_km", y="price_lkr",
            color="make", opacity=0.6,
            trendline="ols",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_scatter.update_layout(
            height=450,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Mileage (km)", yaxis_title="Price (Rs.)",
        )
        fig_scatter.update_yaxes(tickformat=",")
        fig_scatter.update_xaxes(tickformat=",")
        st.plotly_chart(fig_scatter, use_container_width=True)

# ── Row 2: Price Heatmap (Make × Year) ──
st.subheader("Average Price Heatmap: Make × Year")
pivot = filtered.pivot_table(
    values="price_lkr", index="make", columns="yom", aggfunc="mean"
).round(0)

if not pivot.empty:
    fig_heat = px.imshow(
        pivot,
        color_continuous_scale="YlOrRd",
        aspect="auto",
        labels=dict(x="Year", y="Make", color="Avg Price (Rs.)"),
    )
    fig_heat.update_layout(
        height=400,
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_heat, use_container_width=True)

# ── Row 3: Depreciation Curves ──
st.subheader("Depreciation Curves (Top 5 Models)")
top_models = filtered.groupby(["make", "model"]).size().nlargest(5).index.tolist()
if top_models:
    dep_data = []
    for make, model in top_models:
        model_df = filtered[(filtered["make"] == make) & (filtered["model"] == model)]
        avg_by_year = model_df.groupby("yom")["price_lkr"].mean().reset_index()
        avg_by_year["label"] = f"{make} {model}"
        dep_data.append(avg_by_year)

    if dep_data:
        dep_df = pd.concat(dep_data)
        fig_dep = px.line(
            dep_df, x="yom", y="price_lkr", color="label",
            markers=True,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_dep.update_layout(
            height=400,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Year", yaxis_title="Avg Price (Rs.)",
            legend_title="Model",
        )
        fig_dep.update_yaxes(tickformat=",")
        st.plotly_chart(fig_dep, use_container_width=True)
