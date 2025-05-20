# Maritime Alpha Flow

## Introduction

This is a personal project with the aim of collecting and storing free Maritime AIS data for the purpose of financial modelling and research. This repo contains a dockerized container that serves as a full end-to-end data pipeline. Data is streamed in 1 minute batches every 5 minutes using aisstream.io, which is a free webhook service that streams various maritime data from landbased AIS sensors. The data is then processed into various SQL tables and stored in a PostgreSQL database. All of these tasks are managed using Prefect on an AWS Lightsail VM. Finally, I've constructed a streamlit data to visualize and explore this data in a variety of different ways.

## Set Up

To set up this application on your own device, first add your api keys and connection details to a .env file, and cd into the root directory. Then, activate your venv. Next, run:
>docker-compose up -d --build \
>prefect deploy

Finally, follow prefect's instructions to direct your tasks to whatever storage configuration you prefer.

## ETL

This folder containes a schema.sql file, which is then passed to a file called db.py. This .py file then defines a function to create our data tables given the provided schema when called. It also defines functions to add new data into our tables when called, as well as a function to update an ingestion log with metadata about each batch run. The schema contains four different data tables:
>
>ship_static (Containing static data about each vessel, such as ship_type and destination, PK = ship_id)
>
>ship_position (Containing positional data about each vessel at a given time, such as coordinates, PK = ts [timestamp], FK = ship_id)
>
>ingestion_log (Contains metadata about each ingestion run)
>
>ship_count_agg (Counts the aggregate number of vessels in each batch using unique ship_id's, also has vessel counts based on ship_type, PK = batch_start)

## Ingestion

A prefect flow that streams from aisstream.io for 1 minute, every 5 minutes. After each streaming batch, the data is then passed to data tables using the functions defined in etl/db.py.

## Aggregation

A second prefect flow that runs upon completion of our data ingestion to aggregate vessel counts by vessel type.

## Clean Up

A final prefect flow that clears records from ship_static and ship_position (while preserving ship_count_agg) that are more than 6 months old, to ensure data footprint is well maintained. Runs every 24 hours.

## Dashboard

A streamlit dashboard with the following features:
>
>Map of vessel positions from the previous hour
>
>A dataframe containing the counts of each destination for unique vessels since a selected date
>
>Line chart of historical vessel counts (which can be filtered by vessel type)
>
>Gauge to show overall vessel traffic compared to 72-hour SMA
>
>Backtesting functionality with adjustable vessel count SMA lengths to create simple vessel count SMA crossover strategies (includes a feature to optimize your backtest, to be used with caution)

## Demo

[![IMAGE ALT TEXT](https://img.youtu.be/0FVQYHdnvhg/0.jpg)](https://youtu.be/0FVQYHdnvhg "Maritime Alpha Flow Demo")

## Disclosure

This is not financial advice, nor intended to be used in a live trading environment. The sole purpose of this project is for my own development and entertainment. Past performance of a strategy is not indicative of future performance. 
