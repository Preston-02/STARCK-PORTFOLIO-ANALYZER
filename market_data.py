import logging

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

import data_sources as ds

# How long downloaded market data is reused before Yahoo is hit again (seconds)
LIVE_PRICE_TTL = 300        # 5 minutes
FUNDAMENTALS_TTL = 3600     # 1 hour
HISTORY_TTL = 3600          # 1 hour
ALPHA_VANTAGE_TTL = 86400   # 24 hours: the free plan only allows 25 calls a day

PERIOD_DAYS = {"1y": 365, "3y": 365 * 3, "5y": 365 * 5}

# yfinance logs every refused Yahoo request; keep the app logs readable
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


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
    latest = {}
    if not close.empty:
        # Forward/back-fill so mutual funds without intraday data still get a price
        latest = close.ffill().bfill().iloc[-1].dropna().to_dict()

    # Anything Yahoo didn't return: last close from Twelve Data's (cached) history
    missing = [t for t in tickers if t not in latest]
    if missing and ds.has_twelve_data():
        # Same request the price history makes when Yahoo is fully blocked, so it's
        # one cached Twelve Data call instead of two
        td = _td_history(tuple(sorted(set(missing) | {"^GSPC"})))
        for t in missing:
            if t in td.columns and td[t].notna().any():
                latest[t] = float(td[t].dropna().iloc[-1])
    return latest


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


@st.cache_data(ttl=FUNDAMENTALS_TTL, show_spinner=False)
def _fetch_info(ticker):
    # Yahoo's .info endpoint needs a session "crumb", which Yahoo often refuses
    # on shared cloud servers like Streamlit Cloud (HTTP 429 / 401 Invalid Crumb).
    # One attempt only: retrying just adds to the rate limiting. A failure raises,
    # and Streamlit never caches an exception, so a later rerun can try again.
    info = yf.Ticker(ticker).info
    if not info or not info.get("quoteType"):
        raise ValueError(f"No info returned for {ticker}")
    return info


@st.cache_data(ttl=FUNDAMENTALS_TTL, show_spinner=False)
def _fetch_profile(ticker):
    # Sector / industry / asset type from Yahoo's search endpoint,
    # which works without the crumb that .info needs
    try:
        quotes = yf.Search(ticker, max_results=5, news_count=0).quotes
    except Exception:
        return {}
    for q in quotes:
        if str(q.get("symbol", "")).upper() == ticker.upper():
            return {
                "quoteType": (q.get("quoteType") or "").upper(),
                "sector": q.get("sectorDisp") or q.get("sector"),
                "industry": q.get("industryDisp") or q.get("industry"),
            }
    return {}


@st.cache_data(ttl=ALPHA_VANTAGE_TTL, show_spinner=False)
def _fetch_alpha_vantage(ticker):
    # Raises on a refusal, so failures are never cached
    return ds.alpha_vantage_overview(ticker)


def _computed_betas(tickers):
    # Beta from 1 year of daily returns vs. the S&P 500: cov(stock, market) / var(market).
    # Uses the same cached price download as the performance chart.
    close = _price_history(tuple(sorted(tickers)), "1y")
    if close.empty or "^GSPC" not in close.columns:
        return {}
    returns = close.ffill().pct_change(fill_method=None)
    market = returns["^GSPC"]
    market_var = market.var()
    betas = {}
    for t in tickers:
        if t in returns.columns and market_var:
            pair = returns[[t, "^GSPC"]].dropna()
            if len(pair) > 30:
                betas[t] = round(pair[t].cov(pair["^GSPC"]) / pair["^GSPC"].var(), 2)
    return betas


def _num(value):
    return value if isinstance(value, (int, float)) and not pd.isna(value) else None


def generate_fundamental_analysis(unique_tickers):
    if not unique_tickers:
        return pd.DataFrame()

    tickers = list(unique_tickers)
    latest = _download_latest_closes(tuple(sorted(tickers)))
    betas = _computed_betas(tickers)

    rows = []
    info_failures = 0
    alpha_vantage_ok = ds.has_alpha_vantage()
    with st.spinner("Loading fundamentals..."):
        for ticker in tickers:
            info = {}
            # Stop asking for .info once Yahoo has refused it twice this run
            if info_failures < 2:
                try:
                    info = _fetch_info(ticker)
                except Exception:
                    info_failures += 1
            # US mutual fund tickers are 5 letters ending in X (FXAIX, VFIAX)
            looks_like_fund = len(ticker) == 5 and ticker.upper().endswith("X")
            # Yahoo blocked: use Alpha Vantage's company overview instead
            # (it doesn't cover funds, so don't spend a daily call on one)
            if not info and alpha_vantage_ok and not looks_like_fund:
                try:
                    info = _fetch_alpha_vantage(ticker)
                except ds.RateLimited:
                    alpha_vantage_ok = False   # out of calls; don't keep asking
                except Exception:
                    pass                       # e.g. funds, which it doesn't cover
            profile = {} if info.get("sector") else _fetch_profile(ticker)

            quote_type = (info.get("quoteType") or profile.get("quoteType") or "").upper()
            if not quote_type and looks_like_fund:
                quote_type = "MUTUALFUND"
            current_price = (
                _num(info.get("currentPrice"))
                or _num(info.get("regularMarketPrice"))
                or _num(info.get("navPrice"))
                or _num(latest.get(ticker))
            )
            price_str = f"${current_price:,.2f}" if current_price else "N/A"
            yahoo_beta = _num(info.get("beta3Year" if quote_type in ["ETF", "MUTUALFUND"] else "beta"))
            beta = yahoo_beta if yahoo_beta is not None else betas.get(ticker, "N/A")

            if quote_type in ["ETF", "MUTUALFUND"]:
                rows.append({
                    "Symbol": ticker,
                    "Sector": "Fund (No Sector)",
                    "Industry": info.get("fundFamily") or "ETF Fund",
                    "PE Ratio (trailing)": "N/A (Fund)",
                    "Current Price": price_str,
                    "Analyst Target Mean (1yr)": "N/A (Fund)",
                    "Potential Upside %": "N/A (Fund)",
                    "Recommendation": "N/A (Fund)",
                    "Beta": beta,
                })
                continue

            target = _num(info.get("targetMeanPrice"))
            if target and current_price:
                target_str = f"${target:,.2f}"
                upside_str = f"{(target - current_price) / current_price * 100:.2f}%"
            else:
                target_str = upside_str = "N/A"

            pe = _num(info.get("trailingPE"))
            rows.append({
                "Symbol": ticker,
                "Sector": info.get("sector") or profile.get("sector") or "N/A",
                "Industry": info.get("industry") or profile.get("industry") or "N/A",
                "PE Ratio (trailing)": round(pe, 2) if pe else ("Unprofitable" if info else "N/A"),
                "Current Price": price_str,
                "Analyst Target Mean (1yr)": target_str,
                "Potential Upside %": upside_str,
                "Recommendation": info.get("recommendationKey") or "N/A",
                "Beta": beta,
            })

    return pd.DataFrame(rows)


@st.cache_data(ttl=HISTORY_TTL, show_spinner="Loading price history...")
def _download_history(tickers, period):
    # Portfolio tickers and the S&P 500 in a single Yahoo request
    all_tickers = list(tickers) + ["^GSPC"]
    data = yf.download(all_tickers, period=period, auto_adjust=True, progress=False, threads=True)
    return _close_prices(data, all_tickers)


@st.cache_data(ttl=HISTORY_TTL, show_spinner="Loading price history from Twelve Data...")
def _td_history(symbols):
    # Only the symbols Yahoo couldn't supply. 5 years in one go; the 1y/3y views
    # are sliced from it, so switching periods costs no extra credits.
    return ds.twelve_data_history(list(symbols))


def _price_history(tickers, period):
    """Close prices for the tickers plus ^GSPC. Yahoo first (fast, and it works
    on most home connections); Twelve Data only for whatever Yahoo didn't return."""
    tickers = tuple(tickers)
    yahoo = _download_history(tickers, period)
    if not ds.has_twelve_data():
        return yahoo

    wanted = list(tickers) + ["^GSPC"]
    missing = [t for t in wanted if t not in yahoo.columns or yahoo[t].isna().all()]
    if not missing:
        return yahoo

    td = _td_history(tuple(sorted(missing)))
    if td.empty:
        return yahoo
    start = td.index.max() - pd.Timedelta(days=PERIOD_DAYS.get(period, 365))
    td = td[td.index >= start]

    if yahoo.empty:
        return td
    yahoo = yahoo.copy()
    yahoo.index = pd.to_datetime(yahoo.index)
    if yahoo.index.tz is not None:
        yahoo.index = yahoo.index.tz_localize(None)
    keep = [c for c in yahoo.columns if c not in td.columns]
    return yahoo[keep].join(td, how="outer").sort_index()


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

    close = _price_history(tuple(tickers), period)
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
