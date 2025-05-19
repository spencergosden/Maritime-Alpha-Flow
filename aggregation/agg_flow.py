from datetime import datetime, timedelta, timezone
from prefect import flow, task, get_run_logger
from sqlalchemy import text
from etl.db import engine

@task(retries=2, retry_delay_seconds=5)
def compute_counts(batch_start: datetime, batch_end: datetime) -> dict:
    sql = """
    SELECT
      COUNT(DISTINCT p.ship_id) AS total_vessel_count,
      COUNT(DISTINCT CASE
          WHEN CAST(s.ship_type AS INT) BETWEEN 70 AND 79 THEN p.ship_id
        END) AS cargo_count,
      COUNT(DISTINCT CASE
          WHEN CAST(s.ship_type AS INT) BETWEEN 80 AND 89 THEN p.ship_id
        END) AS tanker_count,
      COUNT(DISTINCT CASE
          WHEN CAST(s.ship_type AS INT) BETWEEN 60 AND 69 THEN p.ship_id
        END) AS passenger_count
    FROM ship_position p
    JOIN ship_static   s ON p.ship_id = s.ship_id
    WHERE p.ts >= :start_ts
      AND p.ts <  :end_ts;
    """
    with engine.begin() as conn:
        row = conn.execute(
            text(sql),
            {"start_ts": batch_start, "end_ts": batch_end}
        ).one()
    return {
      "total":     row.total_vessel_count,
      "cargo":     row.cargo_count,
      "tanker":    row.tanker_count,
      "passenger": row.passenger_count,
    }

@task
def upsert_agg(batch_start: datetime, counts: dict):
    sql = """
    INSERT INTO ship_count_agg (
      batch_start,
      total_vessel_count,
      cargo_count,
      tanker_count,
      passenger_count
    ) VALUES (
      :batch_start,
      :total,
      :cargo,
      :tanker,
      :passenger
    )
    ON CONFLICT (batch_start) DO UPDATE
      SET total_vessel_count = EXCLUDED.total_vessel_count,
          cargo_count        = EXCLUDED.cargo_count,
          tanker_count       = EXCLUDED.tanker_count,
          passenger_count    = EXCLUDED.passenger_count;
    """
    params = {
      "batch_start": batch_start,
      "total":       counts["total"],
      "cargo":       counts["cargo"],
      "tanker":      counts["tanker"],
      "passenger":   counts["passenger"],
    }
    with engine.begin() as conn:
        conn.execute(text(sql), params)
    logger = get_run_logger()
    logger.info(f"Writing to database at {engine.url}")


@flow(name="Aggregate Ship Counts")
def agg_flow(batch_start: datetime, batch_end: datetime):
    logger = get_run_logger()
    logger.info(f"Aggregating window {batch_start} -> {batch_end}")
    counts = compute_counts(batch_start, batch_end)
    logger.info(f"Counts: {counts!r}")
    upsert_agg(batch_start, counts)
    logger.info("Upserted into ship_count_agg")

if __name__ == "__main__":
    agg_flow()