from sqlalchemy import create_engine, text
from dotenv import load_dotenv
load_dotenv()
import os

DB_URI = os.getenv("DATABASE_URL")
engine = create_engine(DB_URI, echo=False)

def create_tables():
    ddl = open("etl/schema.sql").read()
    with engine.begin() as conn:
        conn.execute(text(ddl))

def upsert_ship_static(ship_id, ship_type, destination, last_update,
                       dim_a, dim_b, dim_c, dim_d):
    sql = """
    INSERT INTO ship_static
      (ship_id, ship_type, destination, last_update, dim_a, dim_b, dim_c, dim_d)
    VALUES
      (:ship_id, :ship_type, :destination, :last_update,
       :dim_a, :dim_b, :dim_c, :dim_d)
    ON CONFLICT (ship_id) DO UPDATE
      SET ship_type   = EXCLUDED.ship_type,
          destination = EXCLUDED.destination,
          last_update = EXCLUDED.last_update,
          dim_a       = EXCLUDED.dim_a,
          dim_b       = EXCLUDED.dim_b,
          dim_c       = EXCLUDED.dim_c,
          dim_d       = EXCLUDED.dim_d;
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {
            "ship_id": ship_id,
            "ship_type": ship_type,
            "destination": destination,
            "last_update": last_update,
            "dim_a": dim_a,
            "dim_b": dim_b,
            "dim_c": dim_c,
            "dim_d": dim_d
        })

def insert_position(ship_id, ts, latitude, longitude):
    sql = """
    INSERT INTO ship_position (ship_id, ts, latitude, longitude)
    VALUES (:ship_id, :ts, :latitude, :longitude);
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {
            "ship_id": ship_id,
            "ts": ts,
            "latitude": latitude,
            "longitude": longitude
        })

def insert_ingestion_log(window_start, window_end, records_received, errors_encountered):
    sql = """
    INSERT INTO ingestion_log
      (window_start, window_end, records_received, errors_encountered)
    VALUES
      (:window_start, :window_end, :records_received, :errors_encountered);
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {
            "window_start": window_start,
            "window_end": window_end,
            "records_received": records_received,
            "errors_encountered": errors_encountered
        })