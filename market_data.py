import pandas as pd
import yfinance as yf

def fetch_live_market_data(df, unique_tickers, COLUMNS_TO_DROP):

    if df.empty or not unique_tickers:
        return df

    cost_basis_col = "Cost Basis"
    data = yf.download(unique_tickers, period="5d", group_by="ticker")

    # Removing Columns despite the Broker
    df_clean = df.dropna(axis=1).copy()
    existing_drop = [col for col in COLUMNS_TO_DROP if col in df_clean.columns]
    df_clean.drop(columns=existing_drop, inplace=True, errors = "ignore")
    live_prices = []
    live_market_values = []
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
                # Forward-fill/backward-fill missing daytime data for mutual funds
                latest_close = data[ticker]["Close"].ffill().bfill().iloc[-1]
            else:
                latest_close = data["Close"].ffill().bfill().iloc[-1]

            if pd.isna(latest_close):
                latest_close = cost_basis
        except Exception:
            latest_close = cost_basis

        market_val = latest_close * qty

        if side == "Long":
            pnl_val = market_val - trade_value
            pnl_pct = ((latest_close - cost_basis) / cost_basis * 100) if cost_basis != 0 else 0
        else:
            pnl_val = trade_value - market_val
            pnl_pct = ((cost_basis - latest_close) / cost_basis * 100) if cost_basis != 0 else 0

        live_prices.append(latest_close)
        live_market_values.append(market_val)
        live_pnl_values.append(pnl_val)
        live_pnl_percents.append(pnl_pct)

    df_clean["Last Price"] = live_prices
    df_clean["Market value"] = live_market_values
    df_clean["Unrealized PnL (value)"] = live_pnl_values
    df_clean["Unrealized PnL %"] = live_pnl_percents

    return df_clean

def generate_fundamental_analysis(unique_tickers):
    # Generating Analysis data
    analysis_rows = []
    for ticker in unique_tickers:
        try:
            tick_obj = yf.Ticker(ticker)
            info = tick_obj.info

            # Type of Asset
            quote_type = info.get("quoteType", "").upper()

            # Current Price
            current_price = info.get("currentPrice", info.get("regularMarketPrice", info.get("navPrice", info.get("previousClose", "N/A"))))

            # Extract specific metrics
            if quote_type in ["ETF", "MUTUALFUND"]:
                analysis_rows.append({
                    "Symbol": ticker,
                    "Sector": "Fund (No Sector)",
                    "Industry": info.get("fundFamily", "ETF Fund"),
                    "PE Ratio (trailing)": "N/A (Fund)",
                    "Current Price": f"${current_price}",
                    "Analyst Target Mean (1yr)": "N/A (Fund)",
                    "Potential Upside %": "N/A (Fund)",
                    "Recommendation": "N/A (Fund)",
                    "Beta": info.get("beta3Year","N/A"),
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
                    "Beta": info.get("beta", "N/A"),
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
                "Beta": "Error",
            })
    return pd.DataFrame(analysis_rows)
def fetch_historical_performance(df_clean, period="1y"):

    if df_clean.empty:
        return pd.DataFrame()

    # Calculate total current portfolio value
    total_market_value = df_clean["Market value"].sum()

    if total_market_value <= 0:
        return pd.DataFrame()

    # Calculate current portfolio weights
    df_weights = df_clean[["Symbol", "Market value"]].copy()

    df_weights["Weight"] = (
        df_weights["Market value"] / total_market_value
    )

    # Get unique tickers
    tickers = df_weights["Symbol"].dropna().unique().tolist()

    if not tickers:
        return pd.DataFrame()

    # Download historical prices
    price_data = yf.download(
        tickers,
        period=period,
        auto_adjust=True,
        progress=False
    )["Close"]

    # Make sure price_data is always a DataFrame
    if isinstance(price_data, pd.Series):
        price_data = price_data.to_frame()

    # Remove tickers that did not return historical data
    valid_tickers = [
        ticker for ticker in tickers
        if ticker in price_data.columns
    ]

    if not valid_tickers:
        return pd.DataFrame()

    price_data = price_data[valid_tickers].ffill().bfill()

    # Normalize each security to 100 at the beginning
    normalized_prices = price_data / price_data.iloc[0] * 100

    # Calculate weighted portfolio performance
    portfolio_performance = pd.Series(
        0.0,
        index=normalized_prices.index
    )

    for ticker in valid_tickers:

        weight = df_weights.loc[
            df_weights["Symbol"] == ticker,
            "Weight"
        ].iloc[0]

        portfolio_performance += (
            normalized_prices[ticker] * weight
        )

    # Download S&P 500
    sp500_data = yf.download(
        "^GSPC",
        period=period,
        auto_adjust=True,
        progress=False
    )["Close"]

    # Convert to Series if necessary
    if isinstance(sp500_data, pd.DataFrame):
        sp500_data = sp500_data.squeeze()

    sp500_data = sp500_data.ffill().bfill()

    # Normalize S&P 500 to 100
    sp500_performance = (
        sp500_data / sp500_data.iloc[0] * 100
    )

    # Put both series into one DataFrame
    df_performance = pd.DataFrame({
        "Date": portfolio_performance.index,
        "Portfolio": portfolio_performance.values,
        "S&P 500": sp500_performance.reindex(
            portfolio_performance.index
        ).values
    })

    return df_performance