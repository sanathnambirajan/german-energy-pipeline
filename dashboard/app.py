import os

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(page_title="German Energy Dashboard", layout="wide")


@st.cache_resource
def get_engine():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5433")
    name = os.getenv("DB_NAME", "energy")
    user = os.getenv("DB_USER", "energy")
    password = os.getenv("DB_PASSWORD", "energy")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}")


@st.cache_data(ttl=3600)
def load_data():
    engine = get_engine()
    generation = pd.read_sql("select * from analytics.daily_generation_by_source", engine)
    overview = pd.read_sql("select * from analytics.daily_overview order by day", engine)
    generation["day"] = pd.to_datetime(generation["day"])
    overview["day"] = pd.to_datetime(overview["day"])
    return generation, overview


generation, overview = load_data()

st.title("German Electricity Dashboard")
st.write(
    "How has the share of renewable electricity in Germany changed since 2020, "
    "and what does it do to the price?"
)

min_day = overview["day"].min().date()
max_day = overview["day"].max().date()
period = st.sidebar.date_input("Period", value=(min_day, max_day), min_value=min_day, max_value=max_day)
st.sidebar.caption(f"Data available until {max_day}")
if len(period) != 2:
    st.stop()
start, end = period

generation = generation[(generation["day"].dt.date >= start) & (generation["day"].dt.date <= end)]
overview = overview[(overview["day"].dt.date >= start) & (overview["day"].dt.date <= end)]

col1, col2, col3, col4 = st.columns(4)
last_30 = overview.tail(30)
col1.metric("Renewables, last 30 days", f"{last_30['renewable_share'].mean():.1%}")
col2.metric("Renewables, whole period", f"{overview['renewable_share'].mean():.1%}")
col3.metric("Price, last 30 days", f"{last_30['avg_price'].mean():.0f} €")
col4.metric("Negative price hours", int(overview["negative_price_hours"].sum()))

# 1. generation mix
st.subheader("Generation mix per month")
monthly = generation.copy()
monthly["month"] = monthly["day"].dt.to_period("M").dt.to_timestamp()
monthly = monthly.groupby(["month", "source_label", "category"], as_index=False)["generation_mwh"].sum()
monthly["generation_twh"] = monthly["generation_mwh"] / 1_000_000
monthly = monthly.sort_values(["category", "source_label"], ascending=[False, True])
fig = px.area(monthly, x="month", y="generation_twh", color="source_label",
              labels={"month": "", "generation_twh": "TWh", "source_label": "Source"})
st.plotly_chart(fig, width="stretch")

# 2. renewable share trend
st.subheader("Renewable share of generation")
trend = overview[["day", "renewable_share"]].copy()
trend["30 day average"] = trend["renewable_share"].rolling(30, min_periods=1).mean()
trend = trend.rename(columns={"renewable_share": "daily"})
fig = px.line(trend, x="day", y=["daily", "30 day average"],
              labels={"day": "", "value": "Share", "variable": ""})
fig.update_traces(selector={"name": "daily"}, opacity=0.35)
fig.update_yaxes(tickformat=".0%")
st.plotly_chart(fig, width="stretch")

# 3. price vs renewable share
st.subheader("Day-ahead price vs. renewable share")
prices = overview.dropna(subset=["avg_price"]).copy()
prices["year"] = prices["year"].astype(str)
fig = px.scatter(prices, x="renewable_share", y="avg_price", color="year", opacity=0.6,
                 labels={"renewable_share": "Renewable share of the day", "avg_price": "Average price (€/MWh)"})
fig.update_xaxes(tickformat=".0%")
st.plotly_chart(fig, width="stretch")

if len(prices) > 10:
    corr = prices["renewable_share"].corr(prices["avg_price"])
    st.write(f"Correlation between renewable share and daily price in this period: **{corr:.2f}**")

# 4. seasonal patterns
st.subheader("Seasonal patterns")
left, right = st.columns(2)

season = overview.groupby("month", as_index=False)[["solar_mwh", "wind_mwh"]].mean()
season = season.rename(columns={"solar_mwh": "Solar", "wind_mwh": "Wind"})
season[["Solar", "Wind"]] = season[["Solar", "Wind"]] / 1000
fig = px.bar(season, x="month", y=["Solar", "Wind"], barmode="group",
             labels={"month": "Month", "value": "Avg. GWh per day", "variable": ""})
left.plotly_chart(fig, width="stretch")

heat = overview.pivot_table(index="year", columns="month", values="avg_price", aggfunc="mean")
fig = px.imshow(heat, text_auto=".0f", aspect="auto", color_continuous_scale="RdYlGn_r",
                labels={"x": "Month", "y": "Year", "color": "€/MWh"})
fig.update_yaxes(type="category")
right.plotly_chart(fig, width="stretch")
right.caption("Average day-ahead price per month")

st.divider()
st.caption("Data source: Bundesnetzagentur | SMARD.de, licensed under CC BY 4.0")
