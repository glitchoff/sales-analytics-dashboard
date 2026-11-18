# Sales Analytics Dashboard

A Streamlit app for exploring retail order data. You upload a CSV, Excel or JSON file, the
app checks and cleans it, then five KPIs and four charts follow whatever you filter on.

I built it for Practical 10 (Web Application) of my Data Science lab course.

Live app: https://sales-analytics-dashboard-abhay.streamlit.app

## What it does

- Reads `.csv`, `.xlsx` and `.json` files. If you upload nothing, it opens the bundled
  sample so the page is not empty.
- Validates the upload and shows the dimensions, each column's data type, missing counts
  and duplicate counts.
- Cleans what it finds: mixed date formats, words sitting in numeric columns, category
  names spelled several ways, impossible quantities and discounts, duplicate rows.
- Reports the five KPIs the practical asks for: Total Sales, Total Profit, Total Orders,
  Total Quantity and Profit Margin.
- Four filters (date range, category, region, segment) drive every number on the page.
- Four Plotly charts plus a top-10 products bar chart.
- A bad file gets a readable message instead of a traceback.

The sample data is deliberately messy, with junk values and duplicate rows, so the
cleaning step has something to do.

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

## Deployment

The app is already deployed at https://sales-analytics-dashboard-abhay.streamlit.app.

Streamlit Cloud watches the `main` branch, so any push redeploys it. To run your own copy:

1. Sign in at https://share.streamlit.io with GitHub.
2. Choose New app, pick the repository and branch, and set the main file to `app.py`.
3. Click Deploy. The first build takes a minute or two.

No secrets or external services are needed.
