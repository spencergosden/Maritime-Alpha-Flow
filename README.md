# Maritime Alpha Flow

## Introduction

This is a personal project with the aim of collecting and storing free Maritime AIS data for the purpose of financial modelling and research. This repo contains a dockerized container that serves as a full end-to-end digital pipeline. Data is streamed in 1 minute batches every 5 minutes using aisstream.io, which is a free webhook service that streams various maritime data from landbased AIS sensors. The data is then processed into various SQL tables and stored in a PostgreSQL database. All of these tasks are managed using Prefect on an Amazon Lightsail VM. Finally, I've constructed a streamlit data to visualize and explore this data in a variety of different ways.

## Set Up

To set up this application on your own device, first cd into the root directory. Then, activate your venv. Next, run:
>docker-compose up -d --build \
>prefect deploy

Finally, follow prefect's instructions to direct your tasks to whatever storage configuration you prefer.

##
