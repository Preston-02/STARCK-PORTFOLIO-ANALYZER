import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def portfolio_charts_allocation(df_clean):
    # Portfolio Weight %
    fig = px.pie(
        df_clean,
        values="Market value",
        names="Symbol",
        title="Portfolio Allocation"
    )
    return fig


def sector_charts_allocation(df_analysis, df_clean, total_market_value):
    # Safely map market tickers
    merged_temp = pd.merge(
        df_analysis,
        df_clean[["Symbol", "Market value"]],
        on="Symbol",
        how="left"
    ).fillna(0.0)

    # Portfolio Sector %
    sector_fig = px.pie(
        merged_temp,
        values=merged_temp["Market value"] / total_market_value * 100,
        names="Sector",
        title="Portfolio Sector Allocation"
    )
    return sector_fig


def portfolio_beta_gauge(portfolio_beta):

    # Displays only from 0.0 to 3.0 portfolio beta
    visual_beta = max(0.0, min(portfolio_beta, 3.0))

    if portfolio_beta < 0:
        suffix = "(Inverse Short)"
    elif portfolio_beta > 3.0:
        suffix = "(Ultra Speculative)"
    else:
        suffix = ""

    # Portfolio Beta Gauge
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=visual_beta,
        number={
            "valueformat": ".2f",
            "suffix": suffix,
            "prefix": f"{portfolio_beta:.2f}"
            if (portfolio_beta < 0.0 or portfolio_beta > 3.0)
            else "",
        },
        domain={"x": [0, 1], "y": [0, 1]},
        title={
            "text": "Portfolio Beta Gauge",
            "font": {"size": 20}
        },
        gauge={
            "axis": {
                "range": [0.0, 3.0],
                "tickwidth": 1,
                "tickcolor": "gray",
                "dtick": 0.5
            },
            "bar": {"color": "#1E1E1E"},
            "bgcolor": "white",
            "borderwidth": 1,
            "bordercolor": "gray",
            "steps": [
                {
                    "range": [0.0, 0.8],
                    "color": "#23c48e"
                },
                {
                    "range": [0.8, 1.2],
                    "color": "#f3ba2f"
                },
                {
                    "range": [1.2, 2.0],
                    "color": "#f25050"
                },
                {
                    "range": [2.0, 3.0],
                    "color": "#420D09"
                }
            ],
            "threshold": {
                "line": {
                    "color": "black",
                    "width": 4
                },
                "thickness": 0.75,
                "value": 1.0
            }
        }
    ))

    return fig


def portfolio_vs_sp500_chart(df_performance):

    fig = go.Figure()

    # Portfolio performance
    fig.add_trace(go.Scatter(
        x=df_performance["Date"],
        y=df_performance["Portfolio"],
        mode="lines",
        name="Portfolio",
        hovertemplate = "Portfolio: %{y:.2f}<extra></extra>"
    ))

    # S&P 500 performance
    fig.add_trace(go.Scatter(
        x=df_performance["Date"],
        y=df_performance["S&P 500"],
        mode="lines",
        name="S&P 500",
        hovertemplate = "S&P 500: %{y:.2f}<extra></extra>"
    ))

    fig.update_layout(
        title="Portfolio vs. S&P 500",
        xaxis_title="Date",
        yaxis_title="Growth of $100",
        hovermode="x unified",
        legend_title="Benchmark"
    )

    return fig