"""Official market-data APIs used when Yahoo Finance blocks the server.

Twelve Data  -> daily price history      (free: 800 credits/day, 8 per minute)
Alpha Vantage -> company overview         (free: 25 calls/day, 5 per minute)

API keys are read from Streamlit secrets (.streamlit/secrets.toml locally, or the
app's Secrets settings on Streamlit Cloud) or from environment variables:

    TWELVE_DATA_API_KEY = "..."
    ALPHA_VANTAGE_API_KEY = "..."

With no keys set, these functions return nothing and the app uses Yahoo only.
"""
import os
import time
from collections import deque

import pandas as pd
import requests
import streamlit as st

TWELVE_DATA_URL = "https://api.twelvedata.com/time_series"
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"

TD_CREDITS_PER_MINUTE = 8
AV_CALLS_PER_MINUTE = 5

# Twelve Data's free plan has no index data, so SPY (an S&P 500 ETF) stands in for ^GSPC
TD_SYMBOL_OVERRIDES = {"^GSPC": "SPY"}

_av_call_times = deque()


class RateLimited(Exception):
    """The API refused the call because a limit was reached."""


def get_api_key(name):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        # No secrets file at all
        pass
    return os.environ.get(name)


def has_twelve_data():
    return bool(get_api_key("TWELVE_DATA_API_KEY"))


def has_alpha_vantage():
    return bool(get_api_key("ALPHA_VANTAGE_API_KEY"))


def _td_symbol(ticker):
    # Yahoo writes class shares as BRK-B, Twelve Data as BRK.B
    return TD_SYMBOL_OVERRIDES.get(ticker, ticker.replace("-", "."))


def _td_request(td_symbols, outputsize, api_key):
    params = {
        "symbol": ",".join(td_symbols),
        "interval": "1day",
        "outputsize": outputsize,
        "apikey": api_key,
    }
    resp = requests.get(TWELVE_DATA_URL, params=params, timeout=30)
    data = resp.json()
    if isinstance(data, dict) and data.get("status") == "error":
        if data.get("code") == 429:
            raise RateLimited(data.get("message", "Twelve Data rate limit"))
        # Whole-request error (e.g. bad key): treat as no data
        return {}
    # One symbol comes back unwrapped; several come back keyed by symbol
    if len(td_symbols) == 1:
        return {td_symbols[0]: data}
    return data


def twelve_data_history(tickers, outputsize=1300):
    """Daily closes for each ticker as one DataFrame (columns = original tickers).
    Tickers Twelve Data can't supply are simply left out."""
    api_key = get_api_key("TWELVE_DATA_API_KEY")
    if not api_key or not tickers:
        return pd.DataFrame()

    symbol_map = {_td_symbol(t): t for t in tickers}
    td_symbols = list(symbol_map)
    series = {}

    # Each symbol costs one credit, and the free plan allows 8 per minute
    for i in range(0, len(td_symbols), TD_CREDITS_PER_MINUTE):
        batch = td_symbols[i:i + TD_CREDITS_PER_MINUTE]
        if i > 0:
            time.sleep(61)
        try:
            result = _td_request(batch, outputsize, api_key)
        except RateLimited:
            time.sleep(61)
            try:
                result = _td_request(batch, outputsize, api_key)
            except (RateLimited, requests.RequestException, ValueError):
                continue
        except (requests.RequestException, ValueError):
            continue

        for td_sym, payload in result.items():
            if not isinstance(payload, dict) or payload.get("status") != "ok":
                continue
            values = payload.get("values") or []
            if not values:
                continue
            frame = pd.DataFrame(values)
            s = pd.Series(
                pd.to_numeric(frame["close"], errors="coerce").values,
                index=pd.to_datetime(frame["datetime"]),
            ).sort_index()
            series[symbol_map.get(td_sym, td_sym)] = s

    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).sort_index()


def _av_throttle():
    # Free plan: 5 calls per minute. Wait just long enough for a slot to open.
    now = time.time()
    while _av_call_times and now - _av_call_times[0] > 60:
        _av_call_times.popleft()
    if len(_av_call_times) >= AV_CALLS_PER_MINUTE:
        time.sleep(60 - (now - _av_call_times[0]) + 1)
    _av_call_times.append(time.time())


def _av_float(value):
    try:
        f = float(value)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        # Alpha Vantage uses "None" and "-" for missing values
        return None


def _av_recommendation(o):
    # Turn analyst rating counts into Yahoo-style keys (1 = strong buy ... 5 = sell)
    weights = {
        "AnalystRatingStrongBuy": 1, "AnalystRatingBuy": 2, "AnalystRatingHold": 3,
        "AnalystRatingSell": 4, "AnalystRatingStrongSell": 5,
    }
    counts = {k: _av_float(o.get(k)) or 0 for k in weights}
    total = sum(counts.values())
    if not total:
        return None
    score = sum(weights[k] * n for k, n in counts.items()) / total
    if score < 1.5:
        return "strong_buy"
    if score < 2.5:
        return "buy"
    if score < 3.5:
        return "hold"
    if score < 4.5:
        return "underperform"
    return "sell"


def alpha_vantage_overview(ticker):
    """Company overview mapped onto the same keys Yahoo's .info uses.
    Raises RateLimited when the minute/day limit is hit, ValueError when the
    symbol has no overview (Alpha Vantage doesn't cover ETFs or mutual funds)."""
    api_key = get_api_key("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError("No Alpha Vantage key")

    _av_throttle()
    resp = requests.get(
        ALPHA_VANTAGE_URL,
        params={"function": "OVERVIEW", "symbol": ticker, "apikey": api_key},
        timeout=30,
    )
    o = resp.json()
    if "Information" in o or "Note" in o:
        raise RateLimited(o.get("Information") or o.get("Note"))
    if not o.get("Symbol"):
        raise ValueError(f"No Alpha Vantage overview for {ticker}")

    asset_type = (o.get("AssetType") or "").upper()
    sector = (o.get("Sector") or "").title() or None
    industry = (o.get("Industry") or "").title() or None
    return {
        "quoteType": "ETF" if asset_type == "ETF" else "EQUITY",
        "sector": sector,
        "industry": industry,
        "trailingPE": _av_float(o.get("PERatio")),
        "beta": _av_float(o.get("Beta")),
        "targetMeanPrice": _av_float(o.get("AnalystTargetPrice")),
        "recommendationKey": _av_recommendation(o),
        "source": "alpha_vantage",
    }
