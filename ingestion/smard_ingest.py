import json
import os
import time
from datetime import datetime
from pathlib import Path

import psycopg2
import requests
from psycopg2.extras import execute_values

BASE_URL = "https://www.smard.de/app/chart_data"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
START_DATE = os.getenv("START_DATE", "2020-01-01")

# SMARD filter ids, see https://github.com/bundesAPI/smard-api
SERIES = {
    1223: ("lignite", "DE"),
    1224: ("nuclear", "DE"),
    1225: ("wind_offshore", "DE"),
    1226: ("hydro", "DE"),
    1227: ("other_conventional", "DE"),
    1228: ("other_renewables", "DE"),
    4066: ("biomass", "DE"),
    4067: ("wind_onshore", "DE"),
    4068: ("solar", "DE"),
    4069: ("hard_coal", "DE"),
    4070: ("pumped_storage", "DE"),
    4071: ("natural_gas", "DE"),
    410: ("consumption", "DE"),
    4169: ("day_ahead_price", "DE-LU"),
}

OVERLAP_MS = 8 * 24 * 60 * 60 * 1000


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5433"),
        dbname=os.getenv("DB_NAME", "energy"),
        user=os.getenv("DB_USER", "energy"),
        password=os.getenv("DB_PASSWORD", "energy"),
    )


def create_tables(conn):
    with conn.cursor() as cur:
        cur.execute("create schema if not exists raw")
        cur.execute("""
            create table if not exists raw.smard_hourly (
                filter_id integer not null,
                series_name text not null,
                region text not null,
                ts_ms bigint not null,
                value double precision,
                loaded_at timestamp default now(),
                primary key (filter_id, region, ts_ms)
            )
        """)
    conn.commit()


def get_last_timestamp(conn, filter_id, region):
    with conn.cursor() as cur:
        cur.execute(
            "select max(ts_ms) from raw.smard_hourly where filter_id = %s and region = %s",
            (filter_id, region),
        )
        return cur.fetchone()[0]


def get_json(url):
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"  request failed ({e}), retrying...")
            time.sleep(5)
    raise RuntimeError(f"could not download {url}")


def download_week(filter_id, name, region, week_ts):
    url = f"{BASE_URL}/{filter_id}/{region}/{filter_id}_{region}_hour_{week_ts}.json"
    data = get_json(url)

    folder = RAW_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / f"{week_ts}.json", "w") as f:
        json.dump(data, f)

    return data["series"]


def save_rows(conn, filter_id, name, region, series):
    rows = [(filter_id, name, region, ts, value) for ts, value in series if value is not None]
    if not rows:
        return 0

    with conn.cursor() as cur:
        execute_values(cur, """
            insert into raw.smard_hourly (filter_id, series_name, region, ts_ms, value)
            values %s
            on conflict (filter_id, region, ts_ms)
            do update set value = excluded.value, loaded_at = now()
        """, rows)
    conn.commit()
    return len(rows)


def load_series(conn, filter_id, name, region):
    last_ts = get_last_timestamp(conn, filter_id, region)
    if last_ts is None:
        start_ms = int(datetime.strptime(START_DATE, "%Y-%m-%d").timestamp() * 1000)
        print(f"{name}: first load, starting from {START_DATE}")
    else:
        start_ms = last_ts
        print(f"{name}: last value in db is {datetime.fromtimestamp(last_ts / 1000)}")

    # SMARD splits hourly data into weekly files. We take every file that could
    # still contain new values, so the last week gets downloaded again.
    index = get_json(f"{BASE_URL}/{filter_id}/{region}/index_hour.json")
    weeks = [ts for ts in index["timestamps"] if ts > start_ms - OVERLAP_MS]

    total = 0
    for week_ts in weeks:
        series = download_week(filter_id, name, region, week_ts)
        total += save_rows(conn, filter_id, name, region, series)
        time.sleep(0.2)

    print(f"  {len(weeks)} files, {total} rows inserted/updated")


def main():
    conn = get_connection()
    create_tables(conn)

    for filter_id, (name, region) in SERIES.items():
        load_series(conn, filter_id, name, region)

    conn.close()
    print("done")


if __name__ == "__main__":
    main()
