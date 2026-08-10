import pandas as pd
import io
from portfolio_utils import MERRILL_MAP, TRADINGVIEW_MAP, FIDELITY_MAP, SCHWAB_MAP


def clean_data(df, choice):
    # Convert raw upload into Dataframe
    if choice == "Fidelity":
        # Remove text from csv file
        lines = df.getvalue().decode("utf-8").splitlines()
        valid_start = 0
        for i, line in enumerate(lines):
            if "Account Number" in line or "Symbol" in line:
                valid_start = i
                break
        clean_lines = [l for l in lines[valid_start:] if l.strip() and not l.startswith("Returns as of") and not l.startswith("The data and information")]
        df = pd.read_csv(io.StringIO("\n".join(clean_lines)))
    elif choice == "Charles Schwab":
        # Ignore text in CSV file
        lines = df.getvalue().decode("utf-8").splitlines()
        valid_start = 0
        for i, line in enumerate(lines):
            # First line of Schwab needed
            if "Symbol" in line:
                valid_start = i
                break

        # Filter out other text if any at bottom of file
        clean_lines = [l for l in lines[valid_start:] if
                       l.strip() and not l.startswith("\"***") and not l.startswith("End of Report")]
        df = pd.read_csv(io.StringIO("\n".join(clean_lines)))
    else:
        df = pd.read_csv(df)

    df.columns = [col.replace('"', '').replace("'", "").strip() for col in df.columns]

    if choice == "TradingView":
        df = df.rename(columns=TRADINGVIEW_MAP)
    elif choice == "Merrill Lynch":
        df = df.rename(columns=MERRILL_MAP)
    elif choice == "Fidelity":
        df = df.rename(columns=FIDELITY_MAP)
    elif choice == "Charles Schwab":
        df = df.rename(columns=SCHWAB_MAP)

    # Formatting fixes
    target_numeric_cols = ["Market value", "Unrealized PnL (value)", "Unrealized PnL %", "Quantity", "Cost Basis", "Trade value"]
    for col in target_numeric_cols:
        if col in df.columns:
            # Alter information for formatting and calculation purposes
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].str.replace(r"^\((.*)\)$", r"-\1", regex=True)
            df[col] = df[col].str.replace(",", "").str.replace("$", "").str.replace("%", "").str.replace("+", "")
            df[col] = df[col].str.split().str[0]
            # Form floats
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Format specific brokerages
    if choice == "Merrill Lynch":
        df = df[~df["Symbol"].astype(str).str.contains(r"\--", na=False)]
        merrill_drops = ["Last Price", "Cumulative Investment Return ($)", "Cumulative Investment Return (%)", "Accrued Interest ($)", "Security #", "CUSIP #", "Account Nickname", "Account Registration", "Account #"]
        df.drop(columns=merrill_drops, errors="ignore", inplace=True)
        # Recalculate tracking layers
        df["Trade value"] = df["Market value"] - df["Unrealized PnL (value)"]
        df["Cost Basis"] = df.apply(
            lambda row: (row["Trade value"] / row["Quantity"] if row["Quantity"] != 0 else 0.0),
            axis=1
        )
    elif choice == "Fidelity":
        # Drops empty, header metadata, and raw disclaimer text
        df = df[df["Symbol"].notna() & (df["Symbol"].astype(str).str.strip() != "")]
        df = df[~df["Symbol"].astype(str).str.contains("Symbol|Returns as of|The data and information", case=False, na=False)]

        # Drop specific columns
        fidelity_drops = ["Account Number", "Account Name", "Description", "Last Price", "Last Price Change", "Todays Gain/Loss Dollar", "Todays Gain/Loss Percent", "Percent Of Account", "Type"]
        df.drop(columns=fidelity_drops, errors="ignore", inplace=True)
        # Calculate overall asset allocation tracking volume
        df["Trade value"] = df["Quantity"] * df["Cost Basis"]
    elif choice == "Charles Schwab":
        if "Trade value"in df.columns and "Quantity" in df.columns:
            df["Cost Basis"] = df.apply(
                lambda row: (row["Trade value"] / row["Quantity"] if row["Quantity"] != 0 else 0.0),
                axis=1
            )
        df = df[~df["Symbol"].astype(str).str.contains(r"[a-z]",regex=True, na=False)]
        schwab_drops = ["Price", "Price Chng $ (Price Change $)", "Price Chng % (Price Change %)", "Day Chng $ (Day Change $)", "Day Chng % (Day Change %)", "Reinvest?", "Asset Type"]
        df.drop(columns=schwab_drops, errors="ignore", inplace=True)


    # Determining Position type
    if "Side" not in df.columns:
        df["Side"] = "Long"

    # Safely strip out exchange namespace formatting like "NASDAQ:AAPL"
    if "Symbol" in df.columns:
        df["Symbol"] = df["Symbol"].astype(str).apply(
            lambda s: s.split(":", 1)[1] if ":" in s else s
        )
        return df.sort_values(by=["Symbol"]).reset_index(drop=True)
    else:
        fallback_col = df.columns if len(df.columns) > 0 else df.index
        return df.sort_values(by=fallback_col).reset_index(drop=True)
