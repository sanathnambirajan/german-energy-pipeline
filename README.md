# German Energy Data Pipeline

A small data pipeline that downloads German electricity data from SMARD every day, stores it in PostgreSQL, models it with dbt and shows the results in a Streamlit dashboard.

The question I wanted to answer with it:

> How has the share of renewable electricity in Germany changed since 2020, and how does it affect prices?

## Architecture

```
 SMARD API (smard.de)
        |
        |  ingestion/smard_ingest.py   (Python, requests)
        v
 data/raw/*.json  +  PostgreSQL  raw.smard_hourly
        |
        |  dbt  (staging views -> mart tables)
        v
 PostgreSQL  analytics.daily_generation_by_source
             analytics.daily_renewable_share
             analytics.daily_price_stats
             analytics.daily_overview
        |
        v
 Streamlit dashboard (dashboard/app.py)

 GitHub Actions runs ingestion + dbt every morning (.github/workflows/daily.yml)
```

## Data

All data comes from [SMARD](https://www.smard.de), the electricity market platform of the Bundesnetzagentur. The API is public and needs no key. I use hourly values for:

- generation by source: lignite, hard coal, natural gas, nuclear, pumped storage, other conventional, wind onshore, wind offshore, solar, biomass, hydro, other renewables
- total consumption (grid load) for Germany
- day-ahead price for the bidding zone Germany/Luxembourg

The filter IDs are listed at the top of `ingestion/smard_ingest.py`.

Data source: **Bundesnetzagentur | SMARD.de**, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Project structure

```
german-energy-pipeline/
├── ingestion/          smard_ingest.py, downloads data and loads it into the raw schema
├── dbt/                dbt project (staging and mart models, seed, tests)
├── dashboard/          Streamlit app
├── docker-compose.yml  PostgreSQL 16
├── .github/workflows/daily.yml
└── requirements.txt
```

## How it works

**Ingestion.** SMARD stores hourly data in weekly JSON files. The script first reads the index of available weeks for each series, then downloads the weeks it still needs. Every file is saved to `data/raw/` and the values go into `raw.smard_hourly`.

**Incremental loading.** Before downloading, the script checks the latest timestamp that is already in the database for each series and only fetches weeks from that point on. The last week is always downloaded again, because it is usually not complete yet. Rows are inserted with `on conflict ... do update`, so running the script twice does not create duplicates. The first load (2020 until today) takes about 45 minutes; a normal daily run only downloads one file per series.

**Transformation.** The dbt staging models convert the timestamps to German local time and split the raw table into generation, consumption and prices. A small seed file (`energy_sources.csv`) says which source is renewable and which is conventional. The mart models aggregate everything to one row per day. Tests check for nulls, duplicate days and that the renewable share is between 0 and 1.

**Automation.** The GitHub Actions workflow runs every day at 07:00 UTC (and can be started by hand). It installs the requirements, runs the ingestion script and then `dbt seed`, `dbt run` and `dbt test`.

## How to run it locally

You need Docker and Python 3.10 or newer.

1. Start the database (it runs on port 5433 so it does not clash with a local Postgres):

   ```
   docker compose up -d
   ```

2. Install the Python packages:

   ```
   python -m venv .venv
   .venv\Scripts\activate        (Windows)
   source .venv/bin/activate     (Mac/Linux)
   pip install -r requirements.txt
   ```

3. Load the data:

   ```
   python ingestion/smard_ingest.py
   ```

4. Build the dbt models:

   ```
   cd dbt
   dbt seed --profiles-dir .
   dbt run --profiles-dir .
   dbt test --profiles-dir .
   cd ..
   ```

5. Start the dashboard:

   ```
   streamlit run dashboard/app.py
   ```

The database connection is read from the environment variables `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` and `DB_PASSWORD`. If they are not set, the defaults from `docker-compose.yml` are used. `START_DATE` changes where the first load begins (default `2020-01-01`).

### Running it on GitHub Actions

A GitHub runner is deleted after every run, so the data has to live in a database that is reachable from the internet (for example a free Postgres on Neon or Supabase). Add `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` and `DB_PASSWORD` as repository secrets under *Settings → Secrets and variables → Actions*. Until those secrets exist the workflow stops at the "Check database secrets" step.

## Dashboard

The dashboard has four charts:

1. **Generation mix** per month, stacked by source
2. **Renewable share** per day with a 30 day average
3. **Price vs. renewable share**, one dot per day, coloured by year
4. **Seasonal patterns**: average solar and wind per calendar month, and a heatmap of the average price per month and year

You can pick the time period in the sidebar.

## Key findings

Numbers are from my local run with data from 1 January 2020 to 13 November 2026.

| Year | Renewable share of generation | Avg. day-ahead price (€/MWh) | Hours with negative price |
|------|------|------|------|
| 2020 | 46.3 % | 30 | 298 |
| 2021 | 41.9 % | 97 | 139 |
| 2022 | 46.7 % | 235 | 69 |
| 2023 | 55.5 % | 95 | 301 |
| 2024 | 58.5 % | 79 | 457 |
| 2025 | 58.9 % | 89 | 573 |
| 2026 (until Nov 13) | 60.3 % | 120 | 462 |

- The renewable share went from about 46 % in 2020 to around 60 % in 2026. 2021 was a dip because it was a weak wind year. Solar grew the most, from about 46 TWh in 2020 to more than 80 TWh in 2026 (and the year is not even over).
- Prices are mostly driven by other things on a yearly level. 2022 stands out because of the gas crisis, even though the renewable share was not low.
- Day by day the relationship is very clear: days with more renewables are cheaper. Within each year the correlation between daily renewable share and daily average price is between -0.5 and -0.9. Since 2024, days with less than 30 % renewables cost about 179 €/MWh on average, days with more than 70 % about 55 €/MWh.
- Negative prices are getting much more common, from 69 hours in 2022 to 573 hours in 2025. Most of these hours are between April and July, and a weekend day has about four times as many negative hours as a weekday, because solar production is high while demand is low.
- Solar and wind complement each other over the year. Solar peaks in June (about 290 GWh per day), wind is strongest from November to February (more than 500 GWh per day in January and February).

## Limitations and ideas

- Generation is the net generation reported on SMARD, imports and exports are not included, so "renewable share of generation" is not exactly the same as the official share of gross consumption.
- Since October 2025 the day-ahead market works in 15 minute steps. I use the hourly values that SMARD provides, so some detail is lost.
- Possible next step: a simple model that forecasts tomorrow's price or solar output and compares it against a naive baseline (for example "same as yesterday").
