CREATE TABLE IF NOT EXISTS ship_static (
  ship_id BIGINT PRIMARY KEY,
  ship_type VARCHAR(32),
  destination TEXT,
  last_update TIMESTAMP NOT NULL,
  dim_a REAL,
  dim_b REAL,
  dim_c REAL,
  dim_d REAL
);


CREATE TABLE IF NOT EXISTS ship_position (
  id SERIAL PRIMARY KEY,
  ship_id BIGINT NOT NULL,
  ts TIMESTAMP NOT NULL,
  latitude REAL,
  longitude REAL
);

CREATE TABLE IF NOT EXISTS ingestion_log (
  id SERIAL PRIMARY KEY,
  window_start TIMESTAMP NOT NULL,
  window_end   TIMESTAMP NOT NULL,
  records_received INT NOT NULL,
  errors_encountered INT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ship_count_agg (
  batch_start TIMESTAMP WITH TIME ZONE PRIMARY KEY,
  total_vessel_count INT NOT NULL,
  cargo_count INT NOT NULL,
  tanker_count INT NOT NULL,
  passenger_count INT NOT NULL
);