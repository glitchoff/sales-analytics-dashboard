# Sales Analytics Dashboard

A Streamlit app for exploring retail order data. It accepts CSV, Excel and JSON uploads,
checks and cleans them, and shows five KPIs and four interactive charts that respond to
four filters.

Built for Practical 10 (Web Application) of the Data Science lab course.

## What it does

- Reads `.csv`, `.xlsx` and `.json` files. With no upload it opens the bundled sample.
- Validates the upload: dimensions, per-column data types, missing values, duplicates.
- Cleans the data: mixed date formats, text stored in numeric columns, inconsistent
  category spellings, impossible quantities, discounts and sales figures, duplicate rows.
- Shows the five required KPIs: Total Sales, Total Profit, Total Orders, Total Quantity
  and Profit Margin.
- Four filters (date range, category, region, segment) drive everything at once.
- Four Plotly charts plus a top-10 products bar chart, all interactive.
- Bad files produce a readable message instead of a traceback.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501.

## Files

| File | Purpose |
|---|---|
| `app.py` | The whole application |
| `requirements.txt` | Dependencies installed by Streamlit Cloud |
| `sample_sales_data.csv` | Bundled sample, loaded when nothing is uploaded |
| `.streamlit/config.toml` | Server settings for headless hosting |

## Deploy on Streamlit Community Cloud

1. Sign in at https://share.streamlit.io with GitHub.
2. Choose **New app**, pick this repository and branch, and set the main file to `app.py`.
3. Click **Deploy**. The first build takes a minute or two.

No secrets or external services are needed.
