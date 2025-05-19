from prefect import flow, task, get_run_logger
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
load_dotenv()
import os

DB_URI = os.environ.get("DATABASE_URL")
if not DB_URI:
    raise RuntimeError("DATABASE_URL environment variable must be set")

engine = create_engine(DB_URI, echo=False)

@task
def delete_old_records(table_name: str, timestamp_column: str, days: int = 180):
    """
    Deletes rows older than 180 days based on the given timestamp column.
    """
    logger = get_run_logger()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = text(
        f"DELETE FROM {table_name} "
        f"WHERE {timestamp_column} < :cutoff"
    )
    with engine.begin() as conn:
        result = conn.execute(stmt, {"cutoff": cutoff})
    logger.info(
        f"Deleted {result.rowcount} rows from {table_name} "
        f"older than {days} days (cutoff: {cutoff.isoformat()})"
    )

@flow(name="cleanup-old-data")
def cleanup_old_data_flow(days: int = 180):
    """
    Cleans up two tables in parallel:
      - ship_position (uses `ts` column)
      - ship_static   (uses `last_update` column)
    """
    delete_old_records.submit("ship_position", "ts", days=days)
    delete_old_records.submit("ship_static",   "last_update", days=days)

if __name__ == "__main__":
    cleanup_old_data_flow()