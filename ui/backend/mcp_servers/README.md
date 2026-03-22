# MCP Servers for Everyday Productivity Accelerators Workshop

This directory contains MCP (Model Context Protocol) server examples used in the workshop.

## Directory Structure

```
mcp_servers/
├── README.md                    # This file
├── calculator_server.py         # Basic calculator MCP server
├── calculator_client.py         # Calculator client example
├── task_manager_server.py       # Custom task manager MCP server
├── task_manager_client.py       # Task manager client example
├── calendar/
│   └── calendar_server.py       # Calendar integration MCP server
├── weather/
│   └── weather_server.py        # Weather forecasting MCP server
└── financial/
    └── financial_markets_server.py  # Financial Markets MCP server (banks)
```

## Quick Start

### 1. Calculator Example (Module 1)

**Terminal 1 - Start the Calculator Server:**
```bash
cd ui/backend
python mcp_servers/calculator_server.py
```

**Terminal 2 - Start the Calculator Client:**
```bash
cd ui/backend
python mcp_servers/calculator_client.py
```

### 2. Task Manager Example (Module 1 - Build Your Own)

**Terminal 1 - Start the Task Manager Server:**
```bash
cd ui/backend
python mcp_servers/task_manager_server.py
```

**Terminal 2 - Start the Task Manager Client:**
```bash
cd ui/backend
python mcp_servers/task_manager_client.py
```

### 3. Calendar Integration (Module 2)

**Terminal 1 - Start the Calendar Server:**
```bash
cd ui/backend
python mcp_servers/calendar/calendar_server.py
```

### 4. Weather Forecasting (Module 3)

**Terminal 1 - Start the Weather Server:**
```bash
cd ui/backend
python mcp_servers/weather/weather_server.py
```

### 5. Financial Markets Server

Production-grade MCP server for use by major financial institutions (JPMorgan Chase,
Investec Bank, Bank of America, Goldman Sachs, etc.).

**Prerequisites:**
```bash
pip install yfinance pandas numpy scipy
```

**Terminal 1 - Start the Financial Markets Server:**
```bash
cd ui/backend
python mcp_servers/financial/financial_markets_server.py
```

**Available tools:**

| Tool | Description |
|------|-------------|
| `get_stock_quote` | Real-time price + key fundamentals for any ticker |
| `get_historical_prices` | OHLCV history with configurable period & interval |
| `calculate_portfolio_metrics` | Weighted portfolio returns, Sharpe, Sortino, VaR, max drawdown |
| `calculate_options_price` | Black-Scholes call/put pricing + full Greeks (Δ, Γ, Θ, ν, ρ) |
| `calculate_bond_metrics` | Bond price, YTM, Macaulay/modified duration, convexity, DV01 |
| `get_fx_rates` | Live FX rates and cross-currency conversion for any pair |
| `get_market_indices` | Snapshot of major equity indices, US Treasury yields, commodities |
| `calculate_technical_indicators` | SMA, EMA, RSI, MACD, Bollinger Bands, ATR, OBV |
| `screen_stocks` | Filter a watchlist by market cap, P/E, dividend yield, beta |
| `calculate_risk_metrics` | Beta, alpha, information ratio, CVaR, Calmar ratio, tracking error |

## Server Ports

| Server | Port | URL |
|--------|------|-----|
| Calculator | 8000 | http://localhost:8000/mcp/ |
| Task Manager | 8001 | http://localhost:8001/mcp/ |
| Calendar | 8002 | http://localhost:8002/mcp/ |
| Weather | 8003 | http://localhost:8003/mcp/ |

## Dependencies

Make sure you have the required dependencies installed:

```bash
cd ui/backend
pip install -r requirements.txt
```

## Workshop Notes

- Each server runs independently on different ports
- The main backend application (main.py) can integrate with these MCP servers
- All servers use the FastMCP library for simplicity
- In production, replace mock data with real API integrations

## Troubleshooting

### Common Issues:

1. **Port already in use**: Make sure no other processes are using the server ports
2. **Import errors**: Ensure all dependencies are installed with `pip install -r requirements.txt`
3. **Connection refused**: Make sure the server is running before starting the client

### Testing Server Status:

```bash
# Test if a server is running
curl http://localhost:8000/mcp/
```

## Integration with Main Application

The main backend application (`main.py`) can connect to these MCP servers using the Strands SDK. See the workshop content for detailed integration examples. 