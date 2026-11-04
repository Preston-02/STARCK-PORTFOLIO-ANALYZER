import io

import streamlit as st
import pandas as pd
from PIL import Image

# Import Python Files
from charts import (
    portfolio_charts_allocation,
    sector_charts_allocation,
    portfolio_beta_gauge,
    portfolio_vs_sp500_chart
)
from data_cleaning import clean_data
from market_data import (
    fetch_live_market_data,
    generate_fundamental_analysis,
    fetch_historical_performance
)
from portfolio_utils import COLUMNS_TO_DROP, color_negative_red

LOGO_PATH = "assets/starck_logo.png"

st.set_page_config(
    page_title="STARCK",
    page_icon=LOGO_PATH,
    layout= "wide"
)

st.markdown(
    """
    <style>
    [data-testid="stFileUploaderDropzone"] button {
        font-size: 24px;
        height: 80px; 
        width: 250px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_logo():
    # The logo file is 1.2 MB; shrink it once instead of sending it on every rerun
    img = Image.open(LOGO_PATH)
    img.thumbnail((500, 500))
    return img


@st.cache_data(show_spinner="Reading positions...")
def load_positions(file_bytes, choice):
    # Cached on the file's contents, so the CSV is only parsed once per upload
    return clean_data(io.BytesIO(file_bytes), choice)


@st.fragment
def performance_section(df_clean):
    # Runs as a fragment: changing the period reruns only this block, not the whole page
    st.subheader("Portfolio Performance")

    performance_period = st.selectbox(
        "Performance Period",
        ["1 Year", "3 Years", "5 Years"]
    )

    period_map = {
        "1 Year": "1y",
        "3 Years": "3y",
        "5 Years": "5y"
    }

    df_performance = fetch_historical_performance(
        df_clean,
        period=period_map[performance_period]
    )

    if not df_performance.empty:
        performance_fig = portfolio_vs_sp500_chart(df_performance)

        st.plotly_chart(
            performance_fig,
            width="stretch"
        )

        st.caption(
            "Hypothetical performance based on current portfolio weights. "
            "This does not represent actual historical portfolio returns."
        )
    else:
        st.warning(
            "Historical performance data could not be calculated."
        )


st.image(load_logo(), width=250)

st.title("STARCK-Portfolio Analyzer")


# Prompting User for Uploading
positions = st.file_uploader("Upload your positions(csv)", type=["csv"])
if positions is not None:

    # Prompt user to select which brokerage
    choice = st.selectbox("Pick one", ["Select Brokerage...","TradingView", "Merrill Lynch", "Fidelity", "Charles Schwab"])
    if choice == "Select Brokerage...":
        st.write("Please select your brokerage...")
    else:
        try:
            df = load_positions(positions.getvalue(), choice)

            # Validate that the cleaned dataframe has the required columns
            expected_columns = ["Symbol", "Market value", "Trade value", "Unrealized PnL (value)"]
            missing_cols = [col for col in expected_columns if col not in df.columns]

            if missing_cols:
                st.error(f"Invalid file format. The uploaded CSV is not a valid {choice} portfolio.")
                st.stop()

            # Prevent empty dataframes from breaking functions
            if df.empty:
                st.error("The uploaded CSV contains no valid portfolio positions.")
                st.stop()

        except ValueError as e:
            st.error(str(e))
            st.stop()
        except Exception as e:
            # Catch generic Pandas parsing errors
            st.error(f"Could not read this file. Please ensure it is a valid {choice} CSV export.")
            st.stop()

        # Downloading current data (cached, so reruns don't hit Yahoo again)
        unique_tickers = df["Symbol"].unique().tolist()
        df_clean = fetch_live_market_data(df, unique_tickers, COLUMNS_TO_DROP)
        df_analysis = generate_fundamental_analysis(unique_tickers)

        # Save styler object
        styled_df = df_clean.style.map(color_negative_red, subset=["Unrealized PnL (value)", "Unrealized PnL %"])
        styled_df.format({
            "Market value" : "${:,.2f}",
            "Trade value": "${:,.2f}",
            "Unrealized PnL (value)": "${:,.2f}",
            "Cost Basis": "${:,.2f}",
            "Last Price": "${:,.2f}",
            "Unrealized PnL %": "{:,.2f}%",
            "Quantity": "{:,}",
        })
        # Display of Portfolio Summary
        st.subheader("Portfolio Summary")

        # Portfolio Metrics
        total_market_value = df_clean["Market value"].sum()
        total_trade_value = df_clean["Trade value"].sum()
        total_pnl_value = df_clean["Unrealized PnL (value)"].sum()
        total_pnl_percent = (total_pnl_value / total_trade_value) * 100 if total_trade_value != 0 else 0.0

        # format Metrics
        str_market_value = f"${total_market_value:,.2f}"
        str_trade_value = f"${total_trade_value:,.2f}"
        str_pnl_value = f"${total_pnl_value:,.2f}"
        str_pnl_percent = f"{total_pnl_percent:,.2f} %"

        # 3 different columns
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                label="Total Market Value",
                value=str_market_value,
            )
        with col2:
            st.metric(
                label="Total Trade Value",
                value=str_trade_value,
            )
        with col3:
            st.metric(
                label="Total Unrealized PnL",
                value=str_pnl_value,
                delta=str_pnl_percent
            )

        st.divider()

        # Portfolio Performance vs. S&P 500
        performance_section(df_clean)

        st.divider()

        # Portfolio Beta
        st.subheader("Risk & Volatility Analysis")
        beta_df =df_analysis[["Symbol","Beta"]].copy()
        df_beta_merge = df_clean.merge(beta_df,on="Symbol", how="left")
        df_beta_merge["Beta"] = pd.to_numeric(df_beta_merge["Beta"], errors="coerce").fillna(1.0)

        # Weighted Allocation
        df_beta_merge["Weighted_Beta"] = (df_beta_merge["Market value"] / total_market_value) *df_beta_merge["Beta"]
        portfolio_beta = float(df_beta_merge["Weighted_Beta"].sum())

        # Display Portfolio Beta
        beta_gauge_fig = portfolio_beta_gauge(portfolio_beta)
        st.plotly_chart(beta_gauge_fig, width="stretch")

        st.divider()

        # Display Charts
        fig = portfolio_charts_allocation(df_clean)
        st.plotly_chart(fig, width="stretch")

        sector_fig = sector_charts_allocation(df_analysis, df_clean, total_market_value)
        st.plotly_chart(sector_fig, width="stretch")

        st.divider()

        # Displaying Positions from csv file
        st.subheader("Positions")
        st.dataframe(styled_df)

        # Displaying Analysis of each stock
        st.subheader("Stock Analysis")
        # Columns mixing numbers and text (e.g. P/E "Unprofitable") are shown as
        # text so Streamlit's table converter doesn't error on them
        st.dataframe(df_analysis.map(lambda v: "N/A" if v is None else str(v)))
else:
    st.write("Positions CSV file not uploaded!")