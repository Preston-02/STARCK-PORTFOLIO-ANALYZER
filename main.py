import streamlit as st
import pandas as pd
import yfinance as yf

st.title("STARCK PORTFOLIO ANALYZER")
# Prompting User for Uploading
positions = st.file_uploader("Upload your positions(csv)", type=["csv"])
if positions is not None:

    # Uploading CSV file
    df = pd.read_csv(positions)

    # Organizing data frame
    symbols_list = df["Symbol"].tolist()
    clean_symbols_list = [s.split(":", 1)[1] if ":" in s else s for s in symbols_list]
    df["Symbol"] = clean_symbols_list
    df = df.sort_values(by=["Symbol"])
    quantity_list = df["Quantity"].tolist()
    quantity_list_int = [int(quantity) for quantity in quantity_list]
    side_list = df["Side"].tolist()
    trade_value_list = df["Trade value"].tolist()
    trade_value_list_commas = [trade_value.replace(",","") for trade_value in trade_value_list]
    trade_value_list_str = [trade_value.split(" ",1)[0] for trade_value in trade_value_list_commas]
    trade_value_list_float = [float(trade_value) for trade_value in trade_value_list_str]
    df["Trade value"] = trade_value_list_float

    # Downloading current data
    tickers = df["Symbol"].tolist()
    data = yf.download(tickers, period="1d")
    current_prices = data["Close"].iloc[-1]

    # Removing unnecessary information
    df_clean = df.dropna(axis=1)
    df_clean.drop(columns=["Margin","Leverage","Unrealized PnL (currency)"], inplace=True)
    df_clean.reset_index(drop=True, inplace=True)

    # Creating dictionaries for updated data
    prices_dict = {}
    market_value_dict = {}
    PnL_value_dict = {}
    PnL_percent_dict = {}

    # Updating data frame to current market structure iterating through each Asset
    for ticker, qty, side in zip(tickers, quantity_list_int, side_list):
        latest_close = data["Close"][ticker].iloc[-1]
        prices_dict[ticker] = latest_close
        market_value_dict[ticker] = latest_close * qty

        ticker_index = tickers.index(ticker)
        if side == "Long":
            PnL_value_dict[ticker] = market_value_dict[ticker] - trade_value_list_float[ticker_index]
            PnL_percent_dict[ticker] = (latest_close - df_clean["Avg fill price"][ticker_index]) / df_clean["Avg fill price"][ticker_index] * 100
        else:
            PnL_value_dict[ticker] = trade_value_list_float[ticker_index] - market_value_dict[ticker]
            PnL_percent_dict[ticker] = (df_clean["Avg fill price"][ticker_index] - latest_close) / df_clean["Avg fill price"][ticker_index] *100

    # Replacing old data for each Asset with new data
    df_clean["Market value"] = df_clean["Symbol"].map(market_value_dict)
    df_clean["Last price"]  = df_clean["Symbol"].map(prices_dict)
    df_clean["Unrealized PnL (value)"] = df_clean["Symbol"].map(PnL_value_dict)
    df_clean["Unrealized PnL %"] = df_clean["Symbol"].map(PnL_percent_dict)

    # Displaying Positions from csv file
    st.subheader("Positions")
    st.write(df_clean)

    # Display of Statistics
    st.subheader("Position Statistics")
    described = df_clean.describe()
    st.write(described)


else:
    st.write("Please upload your positions(csv)!")