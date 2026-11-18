"""
Practical 10 - Web Application (Streamlit)

Sales dashboard that reads a CSV, Excel or JSON file, validates and cleans it,
and reports five KPIs and four charts that respond to the sidebar filters.
"""

from __future__ import annotations

import io
import json
import re

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

REQUIRED_COLUMNS = [
    "Order ID", "Order Date", "Ship Date", "Ship Mode", "Customer ID",
    "Segment", "Country", "City", "State", "Region", "Product ID",
    "Category", "Sub-Category", "Product Name",
    "Sales", "Quantity", "Discount", "Profit",
]

NUMERIC_COLUMNS = ["Sales", "Quantity", "Discount", "Profit"]
TEXT_COLUMNS = [
    "Order ID", "Ship Mode", "Customer ID", "Segment", "Country", "City",
    "State", "Region", "Product ID", "Category", "Sub-Category", "Product Name",
]
DATE_COLUMNS = ["Order Date", "Ship Date"]

# Categorical columns whose inconsistent spellings get collapsed to one value.
CATEGORY_COLUMNS = ["Ship Mode", "Segment", "Category", "Region", "Country", "State", "City"]

# Text that means "no value" in the raw file.
NULL_TOKENS = {"", "na", "n/a", "nan", "none", "null", "unknown", "-", "?", "not available"}

# Physically impossible or obviously mistyped figures.
MAX_QUANTITY = 100
MAX_DISCOUNT = 1.0
MAX_SALES = 1_000_000

SUPPORTED_TYPES = ["csv", "xlsx", "json"]


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def read_uploaded_file(uploaded) -> pd.DataFrame:
    """Read an uploaded CSV, Excel or JSON file into a string DataFrame."""
    name = uploaded.name.lower()
    raw = uploaded.getvalue()

    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False)

    if name.endswith((".xlsx", ".xls")):
        frame = pd.read_excel(io.BytesIO(raw), dtype=str, keep_default_na=False)
        return frame.fillna("").astype(str)

    if name.endswith(".json"):
        payload = json.loads(raw.decode("utf-8"))
        # Accept a bare list of records, or {"records"/"data": [...]}.
        if isinstance(payload, dict):
            for key in ("records", "data", "rows"):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break
            else:
                raise ValueError(
                    "JSON object found, but it has no 'records', 'data' or 'rows' list."
                )
        if not isinstance(payload, list):
            raise ValueError("JSON must be a list of records or an object holding one.")
        return pd.DataFrame(payload).astype(str)

    raise ValueError(f"Unsupported file type: {uploaded.name}. Use .csv, .xlsx or .json.")


def load_sample() -> pd.DataFrame:
    """The bundled sample dataset, used when nobody uploads a file."""
    candidates = ["sample_sales_data.csv", "experiment10_raw_dataset.csv"]
    for path in candidates:
        try:
            return pd.read_csv(path, dtype=str, keep_default_na=False)
        except FileNotFoundError:
            continue
    return pd.DataFrame()


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def missing_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in REQUIRED_COLUMNS if c not in df.columns]


def column_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Dimensions, types, missing values and duplicates for each column."""
    rows = []
    for col in df.columns:
        blanks = df[col].astype(str).str.strip().str.lower().isin(NULL_TOKENS).sum()
        rows.append({
            "Column": col,
            "Dtype": str(df[col].dtype),
            "Missing": int(blanks),
            "Missing %": round(100 * blanks / max(len(df), 1), 1),
            "Unique": int(df[col].astype(str).str.strip().nunique()),
            "Example": str(df[col].iloc[0]) if len(df) else "",
        })
    return pd.DataFrame(rows)


def duplicate_report(df: pd.DataFrame) -> dict:
    """Count exact duplicate rows and repeated order/product pairs."""
    exact = int(df.duplicated().sum())
    if {"Order ID", "Product ID"}.issubset(df.columns):
        pairs = int(df.duplicated(subset=["Order ID", "Product ID"]).sum())
    else:
        pairs = 0
    return {"exact": exact, "pairs": pairs}


# --------------------------------------------------------------------------
# Cleaning
# --------------------------------------------------------------------------

def blank_to_null(df: pd.DataFrame) -> pd.DataFrame:
    """Turn '', 'N/A', 'unknown' and similar tokens into real NaN."""
    out = df.copy()
    for col in out.columns:
        cleaned = out[col].astype(str).str.strip()
        out[col] = cleaned.mask(cleaned.str.lower().isin(NULL_TOKENS))
    return out


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Parse every date format in the file into datetime64."""
    out = df.copy()
    for col in DATE_COLUMNS:
        if col not in out.columns:
            continue
        # format="mixed" lets pandas try each value on its own, which handles
        # 2025-09-07, 26/12/2024 and 21-Mar-2025 in the same column.
        out[col] = pd.to_datetime(out[col], format="mixed", dayfirst=True, errors="coerce")
    return out


def to_number(series: pd.Series) -> pd.Series:
    """Coerce a text column to float, dropping commas and stray symbols."""
    text = series.astype(str).str.replace(",", "", regex=False).str.strip()
    text = text.str.replace(r"[^\d.\-+eE]", "", regex=True)
    return pd.to_numeric(text, errors="coerce")


def to_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in NUMERIC_COLUMNS:
        if col in out.columns:
            out[col] = to_number(out[col])
    return out


def normalise_text(df: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace and collapse casing/spelling variants to one label."""
    out = df.copy()

    for col in TEXT_COLUMNS:
        if col in out.columns:
            out[col] = out[col].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
            out[col] = out[col].replace({"nan": np.nan})

    for col in CATEGORY_COLUMNS:
        if col not in out.columns:
            continue
        # Lowercase keys map every spelling of a value to one canonical label.
        lookup = {}
        for value in out[col].dropna().unique():
            lookup.setdefault(str(value).lower(), str(value).title())
        out[col] = out[col].map(lambda v: lookup.get(str(v).lower(), v) if pd.notna(v) else v)

    # A few spellings survive title-casing because they are run together.
    if "Ship Mode" in out.columns:
        out["Ship Mode"] = out["Ship Mode"].replace({"Sameday": "Same Day"})
    if "Category" in out.columns:
        out["Category"] = out["Category"].replace({"Office Supply": "Office Supplies"})

    return out


def remove_bad_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Drop rows that cannot be analysed, and record why."""
    out = df.copy()
    log = {}

    before = len(out)
    out = out.dropna(subset=["Order ID", "Sales"])
    log["no_order_id_or_sales"] = before - len(out)

    before = len(out)
    out = out.drop_duplicates()
    log["exact_duplicates"] = before - len(out)

    before = len(out)
    out = out[out["Quantity"].isna() | out["Quantity"].between(0, MAX_QUANTITY)]
    log["impossible_quantity"] = before - len(out)

    before = len(out)
    out = out[out["Discount"].isna() | out["Discount"].between(0, MAX_DISCOUNT)]
    log["impossible_discount"] = before - len(out)

    before = len(out)
    out = out[out["Sales"] <= MAX_SALES]
    log["impossible_sales"] = before - len(out)

    before = len(out)
    out = out.replace([np.inf, -np.inf], np.nan)
    out = out.dropna(subset=["Profit"])
    log["infinite_or_missing_profit"] = before - len(out)

    return out.reset_index(drop=True), log


def fill_remaining_gaps(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Fill what can be inferred and report what had to be dropped."""
    out = df.copy()
    notes = []

    # Profit is normally reported with Sales, so it cannot be estimated safely.
    before = len(out)
    out = out.dropna(subset=["Order Date"])
    if before - len(out):
        notes.append(f"Dropped {before - len(out)} row(s) with an unreadable Order Date.")

    out["Quantity"] = out["Quantity"].fillna(out["Quantity"].median()).astype(int)
    out["Discount"] = out["Discount"].fillna(0.0)
    out["Ship Mode"] = out["Ship Mode"].fillna("Unknown")
    out["Category"] = out["Category"].fillna("Unknown")
    out["Region"] = out["Region"].fillna("Unknown")
    out["State"] = out["State"].fillna("Unknown")
    out["City"] = out["City"].fillna("Unknown")
    out["Segment"] = out["Segment"].fillna("Unknown")

    # Ship date can be inferred from the ship mode when it is missing.
    out["Ship Date"] = out["Ship Date"].fillna(out["Order Date"])

    out["Year"] = out["Order Date"].dt.year
    out["Month"] = out["Order Date"].dt.to_period("M").astype(str)
    out["Profit Margin"] = (out["Profit"] / out["Sales"]).replace([np.inf, -np.inf], np.nan)
    return out, notes


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Run the full cleaning sequence and collect a summary of what changed."""
    before_shape = raw.shape
    frame = blank_to_null(raw)
    frame = parse_dates(frame)
    frame = to_numeric_columns(frame)
    frame = normalise_text(frame)
    frame, dropped = remove_bad_rows(frame)
    frame, notes = fill_remaining_gaps(frame)
    summary = {
        "before": before_shape,
        "after": frame.shape,
        "dropped": dropped,
        "notes": notes,
    }
    return frame, summary


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------

def kpis(df: pd.DataFrame) -> dict:
    """The five KPIs required by the practical."""
    total_sales = df["Sales"].sum()
    total_profit = df["Profit"].sum()
    margin = (total_profit / total_sales * 100) if total_sales else 0.0
    return {
        "Total Sales": total_sales,
        "Total Profit": total_profit,
        "Total Orders": df["Order ID"].nunique(),
        "Total Quantity": int(df["Quantity"].sum()),
        "Profit Margin": margin,
    }


def numeric_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Describe() for the four money and quantity columns."""
    cols = [c for c in NUMERIC_COLUMNS if c in df.columns]
    return df[cols].describe().T.round(2)


def group_summary(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Sales, profit, orders and margin for one grouping column."""
    grouped = df.groupby(by).agg(
        Sales=("Sales", "sum"),
        Profit=("Profit", "sum"),
        Orders=("Order ID", "nunique"),
        Quantity=("Quantity", "sum"),
    )
    grouped["Margin %"] = (grouped["Profit"] / grouped["Sales"] * 100).round(1)
    return grouped.sort_values("Sales", ascending=False).round(2)


def monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    trend = df.groupby("Month").agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"))
    trend["Margin %"] = (trend["Profit"] / trend["Sales"] * 100).round(1)
    return trend.reset_index()


# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------

def apply_filters(df: pd.DataFrame, date_range, categories, regions, segments) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    mask &= df["Order Date"].between(start, end)
    if categories:
        mask &= df["Category"].isin(categories)
    if regions:
        mask &= df["Region"].isin(regions)
    if segments:
        mask &= df["Segment"].isin(segments)
    return df[mask]


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------

def chart_monthly(df: pd.DataFrame):
    trend = monthly_trend(df)
    fig = px.line(
        trend, x="Month", y=["Sales", "Profit"], markers=True,
        title="Monthly sales and profit",
        labels={"value": "Amount", "variable": "Measure"},
    )
    fig.update_layout(legend_title_text="", margin=dict(l=10, r=10, t=50, b=10))
    return fig


def chart_category(df: pd.DataFrame):
    grouped = group_summary(df, "Category").reset_index()
    fig = px.bar(
        grouped, x="Category", y="Sales", color="Category", text_auto=".3s",
        title="Sales by category",
    )
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=50, b=10))
    return fig


def chart_region(df: pd.DataFrame):
    grouped = group_summary(df, "Region").reset_index()
    fig = px.pie(
        grouped, names="Region", values="Sales", hole=0.45,
        title="Share of sales by region",
    )
    fig.update_traces(textinfo="label+percent")
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10))
    return fig


def chart_scatter(df: pd.DataFrame):
    # Bubble size cannot be negative, so a return line is shown at a fixed size.
    plot = df.assign(Bubble=df["Sales"].clip(lower=1))
    fig = px.scatter(
        plot, x="Discount", y="Profit Margin", color="Category",
        size="Bubble", hover_name="Product Name", size_max=28,
        title="Discount against profit margin",
        labels={"Discount": "Discount", "Profit Margin": "Profit margin"},
    )
    # Margin is stored as a fraction here, so 0.12 renders as 12%.
    fig.update_yaxes(tickformat=".1%")
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10))
    return fig


def chart_products(df: pd.DataFrame):
    top = (
        df.groupby("Product Name")["Sales"].sum()
        .nlargest(10).sort_values().reset_index()
    )
    fig = px.bar(
        top, x="Sales", y="Product Name", orientation="h",
        title="Top 10 products by sales",
    )
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10))
    return fig


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------

def page_header():
    st.set_page_config(page_title="Sales Dashboard", page_icon="📊", layout="wide")
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.6rem; padding-bottom: 3rem;}
        [data-testid="stSkillsNudge"], [data-testid="stSkillsNudgeAnchor"] {display: none !important;}
        div[data-testid="stMetric"] {
            background-color: rgba(148, 163, 184, 0.08);
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 10px;
            padding: 12px 16px;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.45rem;
            white-space: normal;
            overflow-wrap: break-word;
            line-height: 1.2;
        }
        .app-title {font-size: 2rem; font-weight: 800; margin-bottom: 2px;}
        .app-sub {opacity: 0.72; margin-bottom: 18px;}
        .section {font-size: 1.22rem; font-weight: 700; margin: 22px 0 10px 0;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="app-title">Sales Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="app-sub">Upload a CSV, Excel or JSON file, check it, then filter '
        'and explore the numbers.</div>',
        unsafe_allow_html=True,
    )


def section(title: str):
    st.markdown(f'<div class="section">{title}</div>', unsafe_allow_html=True)


def main():
    page_header()

    # ---------------- upload ----------------
    with st.sidebar:
        st.header("Data source")
        uploaded = st.file_uploader("Upload a file", type=SUPPORTED_TYPES)
        st.caption("With no upload, the bundled dataset is used.")

    if uploaded is not None:
        try:
            raw = read_uploaded_file(uploaded)
        except Exception as exc:
            st.error(f"Could not read {uploaded.name}: {exc}")
            st.stop()
        source = uploaded.name
    else:
        raw = load_sample()
        source = "sample_sales_data.csv (bundled)"
        if raw.empty:
            st.error("No file uploaded and the bundled dataset could not be found.")
            st.stop()

    if raw.empty:
        st.error("The file loaded but contains no rows.")
        st.stop()

    missing = missing_columns(raw)
    if missing:
        st.error(
            "The file is missing required columns: " + ", ".join(missing)
            + ". Download the sample below to see the expected layout."
        )
        st.download_button(
            "Download sample CSV",
            data=pd.read_csv("experiment10_raw_dataset.csv").to_csv(index=False),
            file_name="sales_sample.csv",
        )
        st.stop()

    st.caption(f"Source: {source}")

    # ---------------- validation ----------------
    section("1. Data upload and validation")
    dups = duplicate_report(raw)
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("Rows", f"{raw.shape[0]:,}")
    v2.metric("Columns", raw.shape[1])
    v3.metric("Missing cells", f"{column_profile(raw)['Missing'].sum():,}")
    v4.metric("Duplicate rows", dups["exact"])

    with st.expander("Column names, data types and missing values", expanded=True):
        st.dataframe(column_profile(raw), width="stretch", hide_index=True)

    with st.expander("Raw preview (first 10 rows)"):
        st.dataframe(raw.head(10), width="stretch", hide_index=True)

    if dups["exact"] or dups["pairs"]:
        st.info(
            f"Found {dups['exact']} exact duplicate row(s) and "
            f"{dups['pairs']} repeated order/product pair(s)."
        )

    # ---------------- cleaning ----------------
    clean, summary = clean_data(raw)

    section("2. Preprocessing")
    c1, c2, c3 = st.columns(3)
    c1.metric("Before", f"{summary['before'][0]:,} x {summary['before'][1]}")
    c2.metric("After", f"{summary['after'][0]:,} x {summary['after'][1]}")
    c3.metric("Rows removed", summary["before"][0] - summary["after"][0])

    with st.expander("What the cleaning step changed"):
        labels = {
            "no_order_id_or_sales": "Missing Order ID or Sales",
            "exact_duplicates": "Exact duplicate rows",
            "impossible_quantity": "Quantity outside 0 to 100",
            "impossible_discount": "Discount outside 0 to 1",
            "impossible_sales": "Sales above 1,000,000",
            "infinite_or_missing_profit": "Infinite or missing Profit",
        }
        changes = pd.DataFrame(
            [{"Issue": labels[k], "Rows removed": v} for k, v in summary["dropped"].items()]
        )
        st.dataframe(changes, width="stretch", hide_index=True)
        for note in summary["notes"]:
            st.caption(note)
        st.caption(
            "Dates were parsed with mixed formats, numbers were coerced from text, "
            "categorical spellings were merged, and empty Quantity, Discount and "
            "Ship Date cells were filled. One row with negative Sales is kept "
            "because it is a return, not a typo."
        )

    section("Statistical summary")
    st.dataframe(numeric_summary(clean), width="stretch")
    st.dataframe(group_summary(clean, "Category"), width="stretch")

    # ---------------- filters ----------------
    with st.sidebar:
        st.header("Filters")
        lo, hi = clean["Order Date"].min(), clean["Order Date"].max()
        date_range = st.date_input(
            "Order date range",
            value=(lo.date(), hi.date()),
            min_value=lo.date(),
            max_value=hi.date(),
        )
        categories = st.multiselect(
            "Category", sorted(clean["Category"].unique()), default=[]
        )
        regions = st.multiselect(
            "Region", sorted(clean["Region"].unique()), default=[]
        )
        segments = st.multiselect(
            "Segment", sorted(clean["Segment"].unique()), default=[]
        )
        st.caption("Empty selections mean all values.")

    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        filtered = apply_filters(clean, date_range, categories, regions, segments)
    else:
        filtered = clean

    if filtered.empty:
        st.warning("No rows match these filters. Widen the date range or clear a filter.")
        st.stop()

    # ---------------- KPIs ----------------
    section("3. Key performance indicators")
    values = kpis(filtered)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Sales", f"${values['Total Sales']:,.0f}")
    k2.metric("Total Profit", f"${values['Total Profit']:,.0f}")
    k3.metric("Total Orders", f"{values['Total Orders']:,}")
    k4.metric("Total Quantity", f"{values['Total Quantity']:,}")
    k5.metric("Profit Margin", f"{values['Profit Margin']:.1f}%")
    st.caption(
        f"{len(filtered):,} of {len(clean):,} rows match the current filters."
    )

    # ---------------- charts ----------------
    section("4. Interactive visualisation")
    left, right = st.columns(2)
    left.plotly_chart(chart_monthly(filtered), width="stretch")
    right.plotly_chart(chart_category(filtered), width="stretch")

    left, right = st.columns(2)
    left.plotly_chart(chart_region(filtered), width="stretch")
    right.plotly_chart(chart_scatter(filtered), width="stretch")

    st.plotly_chart(chart_products(filtered), width="stretch")

    # ---------------- table ----------------
    section("5. Filtered records")
    show = filtered.drop(columns=["Year", "Month", "Profit Margin"]).copy()
    show["Order Date"] = show["Order Date"].dt.date
    show["Ship Date"] = show["Ship Date"].dt.date
    st.dataframe(show, width="stretch", hide_index=True, height=340)

    st.download_button(
        "Download filtered data as CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="filtered_sales.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
