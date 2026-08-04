import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

st.title("STARCK PORTFOLIO ANALYZER")

TRADINGVIEW_MAP = {
        "Symbol" : "Symbol",
        "Side" : "Side",
        "Quantity" : "Quantity",
        "Avg fill price" : "Cost Basis",
        "Last price" : "Last price",
        "Unrealized PnL (value)" : "Unrealized PnL (value)",
        "Unrealized PnL %" : "Unrealized PnL %",
        "Trade value" : "Trade value",
        "Market value" : "Market value",
    }

MERRILL_MAP = {
        "Symbol" : "Symbol",
        "Quantity" : "Quantity",
        "Price ($)" : "Last Price",
        "Unrealized Gain/Loss (%)" : "Unrealized PnL %",
        "Value ($)" : "Market value",
        "Unrealized Gain/Loss ($)" : "Unrealized PnL (value)",

    }
# Columns to drop any Broker
COLUMNS_TO_DROP = ["Margin", "Leverage","Unrealized PnL (currency)", "COB Date"]
# Prompting User for Uploading
positions = st.file_uploader("Upload your positions(csv)", type=["csv"])
if positions is not None:

    # Uploading CSV file
    df = pd.read_csv(positions)

    # Prompt user to select which brokerage
    choice = st.selectbox("Pick one", ["Select Brokerage...","TradingView", "Merrill"])
    if choice == "Select Brokerage...":
        st.write("Please select your brokerage...")
    else:
        if choice == "TradingView":
            df= df.rename(columns = TRADINGVIEW_MAP)
        else:
            df= df.rename(columns = MERRILL_MAP)

            #Format Cleaning
            for col in ["Market value", "Unrealized PnL (value)", "Quantity"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()
                    df[col] = df[col].str.replace(r'^\((.*)\)$', r'-\1', regex=True)  # Converts (42.12) to -42.12
                    df[col] = df[col].str.replace(",", "").str.replace("$", "")
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

            # Removing Unnecessary information Merrill
            df = df[~df["Symbol"].str.contains(r"\--", na=False)]
            df.drop(columns=["Last Price"], inplace=True)
            df.drop(columns=["Cumulative Investment Return ($)"], inplace=True)
            df.drop(columns=["Cumulative Investment Return (%)"], inplace=True)
            df.drop(columns=["Accrued Interest ($)"], inplace=True)
            df.drop(columns=["Security #"], inplace=True)
            df.drop(columns=["CUSIP #"], inplace=True)
            df.drop(columns=["Account Nickname"], inplace=True)
            df.drop(columns=["Account Registration"], inplace=True)
            df.drop(columns=["Account #"], inplace=True)

            #Fixing missed data
            df["Trade value"] = df["Market value"] - df["Unrealized PnL (value)"]
            df["Cost Basis"] = df.apply(lambda row: row["Trade value"] / row["Quantity"] if row["Quantity"] != 0 else 0, axis=1)

        if "Side" not in df.columns:
                df["Side"]= "Long"
        cost_basis_col = "Cost Basis"

        # Organizing data frame
        symbols_list = df["Symbol"].tolist()
        clean_symbols_list = [s.split(":", 1)[1] if ":" in s else s for s in symbols_list]
        df["Symbol"] = clean_symbols_list
        df = df.sort_values(by=["Symbol"])

        df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0.0)
        df["Cost Basis"] = pd.to_numeric(df["Cost Basis"], errors="coerce").fillna(0.0)

        if "Trade value" not in df.columns:
            df["Trade value"] = df["Quantity"] * df["Cost Basis"]

        df["Trade value"] = pd.to_numeric(df["Trade value"].astype(str).str.replace(",","").str.split().str[0], errors="coerce").fillna(0.0)

        # Downloading current data
        unique_tickers = df["Symbol"].unique().tolist()
        data = yf.download(unique_tickers, period="1d", group_by="ticker")

        # Removing Columns no matter the Broker
        df_clean = df.dropna(axis=1).copy()
        existing_drop = [col for col in COLUMNS_TO_DROP if col in df_clean.columns]
        df_clean.drop(columns=existing_drop, inplace=True)
        df_clean.reset_index(drop=True, inplace=True)

        # Creating rows for updated data
        live_prices = []
        live_market_values = []
        live_pnl_values = []
        live_pnl_percents = []

        # Updating data frame to current market structure iterating through each Asset
        for idx, row in df_clean.iterrows():
            ticker = row["Symbol"]
            qty = row["Quantity"]
            side = row["Side"]
            cost_basis = row[cost_basis_col]
            trade_value = row["Trade value"]

            try:
                if len(unique_tickers) > 1:
                    latest_close = data[ticker]["Close"].iloc[-1]
                else:
                    latest_close = data["Close"].iloc[0]
            except Exception:
                latest_close = cost_basis

            market_val = latest_close * qty

            if side == "Long":
                pnl_val = market_val - trade_value
                pnl_pct = ((latest_close - cost_basis) / cost_basis * 100) if cost_basis !=0 else 0
            else:
                pnl_val = trade_value - market_val
                pnl_pct = ((cost_basis - latest_close) / cost_basis * 100) if cost_basis !=0 else 0

            live_prices.append(latest_close)
            live_market_values.append(market_val)
            live_pnl_values.append(pnl_val)
            live_pnl_percents.append(pnl_pct)

        df_clean["Last price"] = live_prices
        df_clean["Market value"] = live_market_values
        df_clean["Unrealized PnL (value)"] = live_pnl_values
        df_clean["Unrealized PnL %"] = live_pnl_percents

        # Generating Analysis data
        analysis_rows = []
        for ticker in unique_tickers:
            try:
                tick_obj = yf.Ticker(ticker)
                info = tick_obj.info

                # Type of Asset
                quote_type = info.get("quoteType","").upper()

                # Current Price
                current_price = info.get("currentPrice",info.get("regularMarketPrice","N/A"))

                # Extract specific metrics
                if quote_type == "ETF":
                    analysis_rows.append({
                        "Symbol": ticker,
                        "Sector": "ETF (No Sector)",
                        "Industry": info.get("fundFamily", "ETF Fund"),
                        "PE Ratio (trailing)": "N/A (Fund)",
                        "Current Price": f"${current_price}",
                        "Analyst Target Mean (1yr)": "N/A (Fund)",
                        "Potential Upside %": "N/A (Fund)",
                        "Recommendation": "N/A (Fund)",
                    })
                else:
                    analysis_rows.append({
                        "Symbol": ticker,
                        "Sector": info.get("sector", "N/A"),
                        "Industry": info.get("industry", "N/A"),
                        "PE Ratio (trailing)": info.get("trailingPE", "Unprofitable"),
                        "Current Price": f"${current_price}",
                        "Analyst Target Mean (1yr)": f"${info.get("targetMeanPrice", "N/A"):,.2f}",
                        "Potential Upside %": f"{(info.get("targetMeanPrice") - current_price) / current_price * 100:.2f}%",
                        "Recommendation": info.get("recommendationKey"),
                    })
            except Exception as e:
                analysis_rows.append({
                    "Symbol": ticker,
                    "Sector": "Error",
                    "Industry": "Error",
                    "PE Ratio (trailing)": "Error",
                    "Current Price": "Error",
                    "Analyst Target Mean (1yr)": "Error",
                    "Potential Upside %": "Error",
                    "Recommendation": "Error",
                })
        # Build DataFrame
        df_analysis = pd.DataFrame(analysis_rows)

        # Indicating Gain/Loss with color
        def color_negative_red(value):
            color = "red" if value < 0 else "green"
            return f'color: {color}'

        # Save styler object
        styled_df = df_clean.style.map(color_negative_red, subset=["Unrealized PnL (value)", "Unrealized PnL %"])
        styled_df.format({
            "Market value" : "${:,.2f}",
            "Trade value": "${:,.2f}",
            "Unrealized PnL (value)": "${:,.2f}",
            "Cost Basis": "${:,.2f}",
            "Last price": "${:,.2f}",
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

        # Portfolio Beta
        st.subheader("Portfolio Beta")


        # Portfolio Weight %
        fig = px.pie(
            df_clean,
            values = "Market value",
            names = "Symbol",
            title = "Portfolio Allocation"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Portfolio Sector %
        sector_fig = px.pie(
            df_analysis,
            values = df_clean["Market value"] / total_market_value * 100,
            names = "Sector",
            title = "Portfolio Sector Allocation"
        )
        st.plotly_chart(sector_fig, use_container_width=True)

        # Displaying Positions from csv file
        st.subheader("Positions")
        st.write(styled_df)

        # Displaying Analysis of each stock
        st.subheader("Stock Analysis")
        st.write(df_analysis)
else:
    st.write("Please upload your positions(csv)!")