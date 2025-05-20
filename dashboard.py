from io import StringIO, BytesIO
import numpy as np
import pandas as pd
import streamlit as st
import pydeck as pdk
import plotly.graph_objects as go
import vectorbt as vbt
from sqlalchemy import text, create_engine
from dotenv import load_dotenv
load_dotenv()
import os


DB_URI = os.getenv("DB_URI")
engine = create_engine(DB_URI, echo=False)                              

st.set_page_config(
    page_title="Maritime Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_data(show_spinner=False)
def load_df(query: str, params: dict | None = None) -> pd.DataFrame:
    return pd.read_sql_query(text(query), engine, params=params)


type_filters = {
    "All":       "",  
    "Cargo":     "AND CAST(s.ship_type AS INT) BETWEEN 70 AND 79",
    "Tanker":    "AND CAST(s.ship_type AS INT) BETWEEN 80 AND 89",
    "Passenger": "AND CAST(s.ship_type AS INT) BETWEEN 60 AND 69",
    "Fishing": "AND CAST(s.ship_type AS INT) = 30",
    "Other":     """
      AND (
        s.ship_type !~ '^[0-9]+$'
        OR
        CAST(s.ship_type AS INT) NOT BETWEEN 60 AND 89
      )
    """
}


tabs = st.tabs([
    "Overview",  
    "Backtesting",      
    "Data Export"
])


# Overview Tab

with tabs[0]:
    st.header("Global Ship Positions (Last Hour)")
    ship_type = st.selectbox(
    "Ship Type",
    ["All", "Cargo", "Tanker", "Passenger", "Fishing", "Other"]
    )
    filter_sql = type_filters[ship_type]
    q_pos = f"""
    SELECT
        p.latitude  AS lat,
        p.longitude AS lon
    FROM ship_position p
    JOIN ship_static   s ON p.ship_id = s.ship_id
    WHERE
        p.ts >= now() AT TIME ZONE 'UTC' - INTERVAL '1 hour'
        {filter_sql}
    """

    df_pos = load_df(q_pos)
    st.map(df_pos)

    st.subheader("Top Destinations (since selected date)")
    date_cutoff = st.date_input(
    "Only show data since", value=pd.Timestamp.now().normalize()
    )
    df_dest = load_df(
        """
        SELECT destination, COUNT(*) AS cnt
        FROM ship_static
        WHERE 
            last_update >= :dt
            AND destination IS NOT NULL
            AND destination !~ '^\s*$'
        GROUP BY destination
        ORDER BY cnt DESC
        """,
        params={"dt": date_cutoff}
    )
    st.dataframe(df_dest)

    st.subheader("Vessel Counts Over Time")
    df_counts = load_df("SELECT * FROM ship_count_agg ORDER BY batch_start")  
    df_counts = df_counts.set_index("batch_start")
    type_map = {
        "Total":       "total_vessel_count",
        "Cargo":       "cargo_count",
        "Tanker":      "tanker_count",
        "Passenger":   "passenger_count",
    }
    options = st.multiselect(
        "Show ship types",
        options=list(type_map.keys()),
        default=["Total"]
    )
    if options:
        cols = [ type_map[o] for o in options ]
        st.line_chart(df_counts[cols])
    else:
        st.info("Pick at least one ship type above to see it plotted.")

    st.subheader("Current Intensity vs 72-hr SMA")
    latest = df_counts["total_vessel_count"].iloc[-1]
    sma72  = df_counts["total_vessel_count"].rolling(72).mean().iloc[-1]
    gauge = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=latest,
            delta={"reference": sma72},
            title={"text": "Vessel Count"},
            gauge={
                "axis": {"range": [0, df_counts["total_vessel_count"].max() * 1.1]}
            }
        )
    )
    st.plotly_chart(gauge, use_container_width=True)


# Backtesting Tab


@st.cache_data(show_spinner=False)
def get_price(sym, start, end, tf):
    data  = vbt.AlpacaData.download(sym, start=start.isoformat(), end=end, timeframe=tf)
    close = data.get("Close")
    if isinstance(close, pd.DataFrame):
        ser = close[sym]
    else:
        ser = close 
    ser.index = pd.to_datetime(ser.index.get_level_values(1)
                            if isinstance(ser.index, pd.MultiIndex)
                            else ser.index)

    return ser

with tabs[1]:
    symbols = [
        "BDRY",
        "SEA", 
        "IYT", 
        "XTN", 
        "USO"
    ]
    symbol = st.selectbox("Select instrument", symbols)

    vbt.settings.data['alpaca']['api_key']     = os.getenv("ALPACA_API_KEY")
    vbt.settings.data['alpaca']['secret_key'] = os.getenv("ALPACA_API_SECRET")

    start_date = st.date_input("Start date", value=(pd.Timestamp.now() - pd.Timedelta(days=2)).date())
    end_input  = st.text_input("End (e.g. '15 minutes ago UTC')", value="15 minutes ago UTC")
    timeframe  = st.selectbox("Timeframe", ["1m", "5m", "1H", "1D"], index=1)

    price = get_price(symbol, start_date, end_input, timeframe)

    vessel_types = {
        "All":         "total_vessel_count",
        "Cargo":       "cargo_count",
        "Tanker":      "tanker_count",
        "Passenger":   "passenger_count"
    }
    sel_type = st.selectbox("Vessel Type for Signal", list(vessel_types))
    count_col = vessel_types[sel_type]

    counts = df_counts[count_col].reindex(price.index, method="ffill") 

    cnt_fast = st.number_input("Count SMA fast window", min_value=1, value=6)
    cnt_slow = st.number_input("Count SMA slow window", min_value=1, value=24)

    enable_short = st.checkbox('Enable Shorting')
    run_bt = st.button("Run Backtest", key="run_bt")
    opt   = st.button("Optimize SMA lengths", key="opt_bt")

    sma_cnt_fast = counts.rolling(cnt_fast).mean()
    sma_cnt_slow = counts.rolling(cnt_slow).mean()

    if run_bt:
        sma_cnt_fast = counts.rolling(cnt_fast).mean()
        sma_cnt_slow = counts.rolling(cnt_slow).mean()

        cnt_entries = sma_cnt_fast > sma_cnt_slow
        cnt_exits   = sma_cnt_fast < sma_cnt_slow
        if enable_short:
            pf = vbt.Portfolio.from_signals(
                price,
                cnt_entries,
                cnt_exits,
                init_cash=100_000,
                fees=0.001,
                slippage=0.001,
                short_entries=cnt_exits,
                short_exits=cnt_entries,
                freq=pd.to_timedelta(timeframe).seconds // 60 and f"{int(pd.to_timedelta(timeframe).seconds/60)}T" or timeframe
            )
        else:
            pf = vbt.Portfolio.from_signals(
                price,
                cnt_entries,
                cnt_exits,
                init_cash=100_000,
                fees=0.001,
                slippage=0.001,
                freq=pd.to_timedelta(timeframe).seconds // 60 and f"{int(pd.to_timedelta(timeframe).seconds/60)}T" or timeframe
            )

        fig = pf.plot()
        st.subheader("Trade Signals on Price")
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("Performance Summary")
        st.write(pf.stats())

    if opt:
        with st.spinner("Optimizing..."):
            fast_values = list(range(3, 25, 1))
            slow_values = list(range(10, min(len(counts), 60), 1))
            results = []
            for f in fast_values:
                for s in slow_values:
                    if f >= s/2: 
                        continue
                    sf = counts.rolling(f).mean()
                    ss = counts.rolling(s).mean()
                    e = sf > ss
                    x = sf < ss
                    if enable_short:
                        p = vbt.Portfolio.from_signals(price, e, x, init_cash=100_000, fees=0.001, slippage=0.001, short_entries=x, short_exits=e, freq=pd.to_timedelta(timeframe).seconds // 60 and f"{int(pd.to_timedelta(timeframe).seconds/60)}T" or timeframe)
                    else:
                        p = vbt.Portfolio.from_signals(price, e, x, init_cash=100_000, fees=0.001, slippage=0.001, freq=pd.to_timedelta(timeframe).seconds // 60 and f"{int(pd.to_timedelta(timeframe).seconds/60)}T" or timeframe)
                    stats = p.stats()
                    results.append({
                        "Fast": f,
                        "Slow": s,
                        "Total Return": stats["Total Return [%]"],
                        "Sharpe":     stats["Sharpe Ratio"]
                    })
            df_opt = pd.DataFrame(results)
            df_opt = df_opt[~np.isinf(df_opt).any(axis=1)]
            best = df_opt.sort_values("Sharpe", ascending=False).iloc[0]
            st.write(">>> Best parameters:", best[["Fast","Slow","Sharpe"]])
            st.dataframe(df_opt.sort_values("Sharpe", ascending=False).head(10))
            with st.expander("Show full table", expanded=False):
                st.dataframe(df_opt.sort_values("Sharpe", ascending=False))

    st.subheader("Vessel-Count SMAs")
    df_count = (
        pd.DataFrame({
            f"Count SMA {cnt_fast}": sma_cnt_fast,
            f"Count SMA {cnt_slow}": sma_cnt_slow
        })
        .reset_index()
        .rename(columns={"index": "timestamp"})
    )
    st.line_chart(df_count, x="timestamp", y=[f"Count SMA {cnt_fast}", f"Count SMA {cnt_slow}"])



# Data Export Tab

with tabs[2]:
    st.header("Download Raw Data")
    st.write("Export tables as CSV or Parquet:")

    for name, df in [
        ("ship_position", load_df("SELECT * FROM ship_position")),
        ("ship_static",   load_df("SELECT * FROM ship_static")),
        ("ship_count_agg",load_df("SELECT * FROM ship_count_agg")),
    ]:
        st.subheader(name)
        csv_buf = StringIO()
        df.to_csv(csv_buf, index=False)
        st.download_button(
            label=f"Download {name} as CSV",
            data=csv_buf.getvalue(),
            file_name=f"{name}.csv",
            mime="text/csv"
        )

        pq_buf = BytesIO()
        df.to_parquet(pq_buf, index=False)
        st.download_button(
            label=f"Download {name} as Parquet",
            data=pq_buf.getvalue(),
            file_name=f"{name}.parquet",
            mime="application/octet-stream"
        )
