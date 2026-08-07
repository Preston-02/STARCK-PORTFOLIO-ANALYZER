import pandas as pd
from portfolio_utils import MERRILL_MAP, TRADINGVIEW_MAP


def clean_data(df, choice):
    if choice == "TradingView":
        df = df.rename(columns=TRADINGVIEW_MAP)
    else:
        df = df.rename(columns=MERRILL_MAP)

        # Format Cleaning
        for col in ["Market value", "Unrealized PnL (value)", "Quantity"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].str.replace(
                    r"^\((.*)\)$", r"-\1", regex=True
                )  # Converts (42.12) to -42.12
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

        # Fixing missed data
        df["Trade value"] = df["Market value"] - df["Unrealized PnL (value)"]
        df["Cost Basis"] = df.apply(
            lambda row: (
                row["Trade value"] / row["Quantity"]
                if row["Quantity"] != 0
                else 0
            ),
            axis=1,
        )

    if "Side" not in df.columns:
        df["Side"] = "Long"

    # Organizing data frame
    symbols_list = df["Symbol"].tolist()

    # Fixed: Standardized string casting to safely strip broker prefixes out
    clean_symbols_list = [
        str(s).split(":", 1)[1] if ":" in str(s) else str(s)
        for s in symbols_list
    ]
    df["Symbol"] = clean_symbols_list
    df = df.sort_values(by=["Symbol"])

    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0.0)
    df["Cost Basis"] = pd.to_numeric(df["Cost Basis"], errors="coerce").fillna(
        0.0
    )

    if "Trade value" not in df.columns:
        df["Trade value"] = df["Quantity"] * df["Cost Basis"]

    df["Trade value"] = pd.to_numeric(
        df["Trade value"]
        .astype(str)
        .str.replace(",", "")
        .str.split()
        .str[0],
        errors="coerce",
    ).fillna(0.0)

    return df
