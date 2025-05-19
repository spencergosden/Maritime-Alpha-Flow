import asyncio, json
from datetime import datetime, timezone, timedelta
import websockets
from dotenv import load_dotenv
load_dotenv()
import os
from prefect import task, flow
import logging
logger = logging.getLogger(__name__)
from etl.db import create_tables, upsert_ship_static, insert_position, insert_ingestion_log
from aggregation.agg_flow import agg_flow

API_KEY = os.getenv("AISSTREAM_API_KEY")
if not API_KEY:
    raise ValueError("API_KEY not found in environment")

@task
def ensure_schema():
    create_tables()

@task(retries=3, retry_delay_seconds=5, timeout_seconds=300)
async def stream_and_persist(duration_sec: int = 60):
    batch_start = datetime.now(timezone.utc)
    records = 0
    errors = 0
    uri = "wss://stream.aisstream.io/v0/stream"
    subscribe = {"APIKey": API_KEY, "BoundingBoxes": [[[-90, -180], [ 90,  180]]]}
    try:
        async with websockets.connect(uri, ping_timeout=10) as ws:
            await ws.send(json.dumps(subscribe))
            start = datetime.now(timezone.utc)
            while True:
                elapsed = (datetime.now(timezone.utc) - start).total_seconds()
                remaining = duration_sec - elapsed
                if remaining <= 0:
                    break
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                data = json.loads(msg)
                ts = datetime.now(timezone.utc)
                if data["MessageType"] == "PositionReport":
                    r = data["Message"]["PositionReport"]
                    insert_position(r["UserID"], ts, r["Latitude"], r["Longitude"])
                elif data["MessageType"] == "ShipStaticData":
                    s = data["Message"]["ShipStaticData"]
                    dims = s.get("Dimensions", {})
                    upsert_ship_static(
                        s["UserID"], s["Type"], s["Destination"], ts,
                        dims.get("A"), dims.get("B"), dims.get("C"), dims.get("D")
                    )
                records += 1

    except (websockets.ConnectionClosedError, OSError) as e:
        logger.warning(f"Connection closed: {e}.")
        errors += 1

    finally:
        end = datetime.now(timezone.utc)
        insert_ingestion_log(batch_start, end, records, errors)



@flow(name='AIS Ingest')
def ingestion_flow():
    ensure_schema()
    stream_and_persist.submit(duration_sec=60).result()
    now = datetime.now(timezone.utc)
    batch_start = now.replace(
        minute=(now.minute // 5) * 5,
        second=0,
        microsecond=0
    )
    batch_end = batch_start + timedelta(minutes=5)
    logger.info(f"Batch start: {batch_start}, Batch end: {batch_end}")
    agg_flow(batch_start, batch_end)

if __name__ == "__main__":
    ingestion_flow()
