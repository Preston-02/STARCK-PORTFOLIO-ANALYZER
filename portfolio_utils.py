TRADINGVIEW_MAP = {
        "Symbol" : "Symbol",
        "Side" : "Side",
        "Quantity" : "Quantity",
        "Avg fill price" : "Cost Basis",
        "Last price" : "Last Price",
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

# Indicating Gain/Loss with color
def color_negative_red(value):
    color = "red" if value < 0 else "green"
    return f'color: {color}'