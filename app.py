import streamlit as st
import pandas as pd

# Import Python Files
from charts import portfolio_charts_allocation, sector_charts_allocation, portfolio_beta_gauge
from data_cleaning import clean_data
from market_data import fetch_live_market_data, generate_fundamental_analysis
from portfolio_utils import COLUMNS_TO_DROP, color_negative_red

st.title("STARCK PORTFOLIO ANALYZER")

# Prompting User for Uploading
positions = st.file_uploader("Upload your positions(csv)", type=["csv"])
if positions is not None:

    # Prompt user to select which brokerage
    choice = st.selectbox("Pick one", ["Select Brokerage...","TradingView", "Merrill Lynch", "Fidelity", "Charles Schwab"])
    if choice == "Select Brokerage...":
        st.write("Please select your brokerage...")
    else:

        df = clean_data(positions, choice)

        # Downloading current data
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
        st.plotly_chart(beta_gauge_fig, use_container_width=True)

        st.divider()

        # Display Charts
        fig = portfolio_charts_allocation(df_clean)
        st.plotly_chart(fig, use_container_width=True)

        sector_fig = sector_charts_allocation(df_analysis, df_clean, total_market_value)
        st.plotly_chart(sector_fig, use_container_width=True)

        st.divider()

        # Displaying Positions from csv file
        st.subheader("Positions")
        st.write(styled_df)

        # Displaying Analysis of each stock
        st.subheader("Stock Analysis")
        st.write(df_analysis)
else:
    st.write("Please upload your positions(csv)!")