from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# How long downloaded market data is reused before Yahoo is hit again (seconds)
LIVE_PRICE_TTL = 300        # 5 minutes
FUNDAMENTALS_TTL = 3600     # 1 hour
HISTORY_TTL = 3600          # 1 hour


def _close_prices(data, tickers):
    """Return a DataFrame of Close prices with one column per ticker,
    whatever column layout yfinance hands back."""
    if data is None or data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        # Layout is either (field, ticker) or (ticker, field)
        if "Close" in data.columns.get_level_values(0):
            close = data["Close"]
        else:
            close = data.xs("Close", axis=1, level=1)
    else:
        close = data[["Close"]].rename(columns={"Close": tickers[0]})

    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])
    return close


@st.cache_data(ttl=LIVE_PRICE_TTL, show_spinner="Fetching live prices...")
def _download_latest_closes(tickers):
    data = yf.download(list(tickers), period="5d", progress=False, threads=True)
    close = _close_prices(data, list(tickers))
    if close.empty:
        return {}
    # Forward/back-fill so mutual funds without intraday data still get a price
    return close.ffill().bfill().iloc[-1].to_dict()


def fetch_live_market_data(df, unique_tickers, COLUMNS_TO_DROP):

    if df.empty or not unique_tickers:
        return df

    latest = _download_latest_closes(tuple(sorted(unique_tickers)))

    # Removing Columns despite the Broker
    df_clean = df.dropna(axis=1).copy()
    existing_drop = [col for col in COLUMNS_TO_DROP if col in df_clean.columns]
    df_clean.drop(columns=existing_drop, inplace=True, errors="ignore")
    df_clean.reset_index(drop=True, inplace=True)

    cost_basis = df_clean["Cost Basis"]
    qty = df_clean["Quantity"]
    trade_value = df_clean["Trade value"]

    # Latest close per row (vectorised), falling back to cost basis if Yahoo had nothing
    last_price = pd.to_numeric(df_clean["Symbol"].map(latest), errors="coerce")
    last_price = last_price.fillna(cost_basis)

    market_val = last_price * qty
    is_long = df_clean["Side"] == "Long"
    safe_cb = cost_basis.replace(0, np.nan)

    pnl_val = np.where(is_long, market_val - trade_value, trade_value - market_val)
    pnl_pct = np.where(
        is_long,
        (last_price - cost_basis) / safe_cb * 100,
        (cost_basis - last_price) / safe_cb * 100,
    )

    df_clean["Last Price"] = last_price
    df_clean["Market value"] = market_val
    df_clean["Unrealized PnL (value)"] = pnl_val
    df_clean["Unrealized PnL %"] = pd.Series(pnl_pct, index=df_clean.index).fillna(0.0)

    return df_clean


def _analyze_ticker(ticker):
    try:
        info = yf.Ticker(ticker).info

        # Type of Asset
        quote_type = (info.get("quoteType") or "").upper()

        # Current Price
        current_price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("navPrice")
            or info.get("previousClose")
        )
        has_price = isinstance(current_price, (int, float)) and current_price != 0
        price_str = f"${current_price:,.2f}" if has_price else "N/A"

        if quote_type in ["ETF", "MUTUALFUND"]:
            return {
                "Symbol": ticker,
                "Sector": "Fund (No Sector)",
                "Industry": info.get("fundFamily", "ETF Fund"),
                "PE Ratio (trailing)": "N/A (Fund)",
                "Current Price": price_str,
                "Analyst Target Mean (1yr)": "N/A (Fund)",
                "Potential Upside %": "N/A (Fund)",
                "Recommendation": "N/A (Fund)",
                "Beta": info.get("beta3Year", "N/A"),
            }

        # Stocks with no analyst coverage used to crash into an "Error" row
        target = info.get("targetMeanPrice")
        if isinstance(target, (int, float)) and has_price:
            target_str = f"${target:,.2f}"
            upside_str = f"{(target - current_price) / current_price * 100:.2f}%"
        else:
            target_str = "N/A"
            upside_str = "N/A"

        return {
            "Symbol": ticker,
            "Sector": info.get("sector", "N/A"),
            "Industry": info.get("industry", "N/A"),
            "PE Ratio (trailing)": info.get("trailingPE", "Unprofitable"),
            "Current Price": price_str,
            "Analyst Target Mean (1yr)": target_str,
            "Potential Upside %": upside_str,
            "Recommendation": info.get("recommendationKey"),
            "Beta": info.get("beta", "N/A"),
        }
    except Exception:
        return {
            "Symbol": ticker,
            "Sector": "Error",
            "Industry": "Error",
            "PE Ratio (trailing)": "Error",
            "Current Price": "Error",
            "Analyst Target Mean (1yr)": "Error",
            "Potential Upside %": "Error",
            "Recommendation": "Error",
            "Beta": "Error",
        }


@st.cache_data(ttl=FUNDAMENTALS_TTL, show_spinner="Loading fundamentals...")
def _fundamentals(tickers):
    # One .info request per ticker, run in parallel instead of one after another
    with ThreadPoolExecutor(max_workers=min(8, len(tickers))) as pool:
        rows = list(pool.map(_analyze_ticker, tickers))
    df = pd.DataFrame(rows)
    # Mixed text/number columns make Streamlit's table conversion slow and noisy
    for col in ["PE Ratio (trailing)", "Beta"]:
        df[col] = df[col].astype(str)
    return df


def generate_fundamental_analysis(unique_tickers):
    if not unique_tickers:
        return pd.DataFrame()
    return _fundamentals(tuple(unique_tickers))


@st.cache_data(ttl=HISTORY_TTL, show_spinner="Loading price history...")
def _download_history(tickers, period):
    # Portfolio tickers and the S&P 500 in a single request
    all_tickers = list(tickers) + ["^GSPC"]
    data = yf.download(all_tickers, period=period, auto_adjust=True, progress=False, threads=True)
    return _close_prices(data, all_tickers)


def fetch_historical_performance(df_clean, period="1y"):

    if df_clean.empty:
        return pd.DataFrame()

    # Calculate total current portfolio value
    total_market_value = df_clean["Market value"].sum()

    if total_market_value <= 0:
        return pd.DataFrame()

    # Current portfolio weights (summed in case a ticker appears on two rows)
    weights = df_clean.groupby("Symbol")["Market value"].sum() / total_market_value

    tickers = sorted(weights.index.dropna().unique().tolist())
    if not tickers:
        return pd.DataFrame()

    close = _download_history(tuple(tickers), period)
    if close.empty or "^GSPC" not in close.columns:
        return pd.DataFrame()

    valid_tickers = [t for t in tickers if t in close.columns and close[t].notna().any()]
    if not valid_tickers:
        return pd.DataFrame()

    price_data = close[valid_tickers].ffill().bfill()

    # Normalize each security to 100 at the beginning, then weight (vectorised)
    normalized_prices = price_data / price_data.iloc[0] * 100
    portfolio_performance = normalized_prices.mul(weights[valid_tickers], axis=1).sum(axis=1)

    sp500 = close["^GSPC"].ffill().bfill()
    sp500_performance = sp500 / sp500.iloc[0] * 100

    return pd.DataFrame({
        "Date": portfolio_performance.index,
        "Portfolio": portfolio_performance.values,
        "S&P 500": sp500_performance.reindex(portfolio_performance.index).values,
    })
