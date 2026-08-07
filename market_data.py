import pandas as pd
import yfinance as yf

def fetch_live_market_data(df, unique_tickers, COLUMNS_TO_DROP):
    cost_basis_col = "Cost Basis"
    data = yf.download(unique_tickers, period="1d", group_by="ticker")

    # Removing Columns despite the Broker
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
            pnl_pct = ((latest_close - cost_basis) / cost_basis * 100) if cost_basis != 0 else 0
        else:
            pnl_val = trade_value - market_val
            pnl_pct = ((cost_basis - latest_close) / cost_basis * 100) if cost_basis != 0 else 0

        live_prices.append(latest_close)
        live_market_values.append(market_val)
        live_pnl_values.append(pnl_val)
        live_pnl_percents.append(pnl_pct)

    df_clean["Last price"] = live_prices
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
            current_price = info.get("currentPrice", info.get("regularMarketPrice", "N/A"))

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