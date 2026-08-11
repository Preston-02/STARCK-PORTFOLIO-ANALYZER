# STARK

## Portfolio Analystics Dashboard
STARK is a portfolio analytics dashboard built with Python and Streamlit. 
It allows users to upload supported brokerage CSV files and analyze their portfolio using current market data, portfolio statistics, risk metrics, and visualizations.

## Features

### Portfolio Analystics
- Total market value
- Total trade value
- Unrealized P&L ($)
- Unrealized P&L (%)
- Portfolio beta
- Portfolio allocation
- Sector allocation

### Stock Analytics
- Current market price
- Individual stock beta
- P/E trailing ratio
- Analyst recommendation
- 1-year average price target
- Potential upside (%)

### Visualizations
- Portfolio allocation pie chart
- Sector allocation pie chart
- Portfolio beta gauge
- Gain/loss formatting

### Market Data
STARK retrieves the latest available market prices using Yahoo Finance when the application is loaded or refreshed. These prices are used to calculate the Unrealized P&L and current market value

## Supported Brokerages

STARK currently supports: 

- Merrill Lynch
- TradingView (paper trading)
- Fidelity
- Charles Schwab

## Libraries

- Python
- Streamlit
- Pandas
- Plotly
- yfinance

## Project Structure

```text
├── app.py              # Main Streamlit application
├── assets/             # Static visual elements
│   └── logo.png        # Project logo image file
├── charts.py           # Data visualization
├── data_cleaning.py    # Cleaning data frames
├── market_data.py      # API fetching and financial market data
└── portfolio_utils.py  # Brokerage mapping and portfolio formatting
```

## How it works

1. Upload a supported brokerage CSV file.
2. STARCK identifies and cleans the raw brokerage data.
3. Brokerage specific column names are mapped to a standard format with only necessary information.
4. The application retreives the latest available market data using Yahoo Finance.
5. Current market value and Unrealized P&L are calculated using the latest available prices.
6. Portfolio statistics and stock analytics are displayed in the dashboard.
7. Charts provide visualizations of portfolio allocation, sector allocation, and portfolio beta.

## Portfolio Beta

STARCK calculates portfolio beta using market value weightings of individual assets.

## Installation

STARCK  is available as a deployed web application, so no installation is required to use it.

To run STARCK locally, clone the repository and install the required dependencies:

```bash
git clone https://github.com/Preston-02/STARCK-PORTFOLIO-ANALYZER.git
cd STARCK
pip install -r requirements.txt
streamlit run app.py 
```

## Data Privacy

STARCK does not require users to provide brokerage login credentials.

Users upload brokerage CSV files directly to the application. Users should avoid uploading files with sensitive information that is not required for portfolio analysis.

## Known Limitations

- Leverage postions may not be calculated correctly into metrics.
- Some securities may not have beta which can skew portfolio beta calculation.
- Market prices are updated when the application is refreshed or loaded.
- Works with portfolios specifically with stocks and funds

## Future Improvements

- Additional brokerage support
- Improved ETF sector classification
- S&P 500 performance comparison
- Monte Carlo portfolio simulation
- Additional risk metrics

## Author

Preston Jones

STARCK was created as a personal project combining financial analysis, Python programming, data processing, market data, and data visualizations.


