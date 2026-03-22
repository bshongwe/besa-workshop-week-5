"""
Financial Markets MCP Server
=============================
A production-grade MCP server for financial markets analysis, built for use by
major financial institutions such as JPMorgan Chase, Investec Bank, Bank of
America, and other world-leading banks.

The server implements industry-standard financial analysis methods aligned with
the quantitative-finance practices used at large financial institutions.

Key capabilities
----------------
* Real-time & historical market data (via Yahoo Finance / yfinance)
* Portfolio analytics   – returns, volatility, Sharpe ratio, Value-at-Risk
* Options pricing       – Black-Scholes model (calls & puts), Greeks
* Fixed-income          – bond price, yield-to-maturity, duration
* Foreign exchange      – live FX rates and cross-currency conversions
* Technical analysis    – SMA, EMA, RSI, MACD, Bollinger Bands
* Risk metrics          – drawdown, beta, correlation, VaR (parametric & historical)
* Stock screening       – filter equities by fundamental/price criteria

Dependencies (add to requirements.txt):
    yfinance>=0.2.38
    pandas>=2.0.0
    numpy>=1.26.0
    scipy>=1.12.0
"""

from __future__ import annotations

import math
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from mcp.server.fastmcp import FastMCP
from scipy import stats

# ---------------------------------------------------------------------------
# Server initialisation
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("Financial Markets Server")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Download OHLCV data from Yahoo Finance; raises ValueError on failure."""
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data found for ticker '{ticker}'. Verify the symbol.")
    return df


def _annualisation_factor(interval: str) -> float:
    """Return the number of periods per year for a given data interval."""
    mapping = {
        "1d": 252.0,
        "1wk": 52.0,
        "1mo": 12.0,
        "1h": 252.0 * 6.5,
    }
    return mapping.get(interval, 252.0)


# ---------------------------------------------------------------------------
# Tool: get_stock_quote
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Retrieve the latest quote and key fundamental metrics for a single equity. "
        "Returns bid/ask, day range, 52-week range, market cap, P/E ratio, dividend "
        "yield, EPS, and analyst target price."
    )
)
def get_stock_quote(ticker: str) -> Dict:
    """
    Get a real-time stock quote and fundamental snapshot.

    Args:
        ticker: Exchange ticker symbol (e.g. 'JPM', 'BAC', 'AAPL').

    Returns:
        Dictionary containing price data and fundamental metrics.
    """
    try:
        t = yf.Ticker(ticker.upper())
        info = t.info

        # Fast-info for live price
        fi = t.fast_info
        current_price = fi.last_price or info.get("currentPrice") or info.get("regularMarketPrice")

        return {
            "success": True,
            "ticker": ticker.upper(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price": {
                "current": round(current_price, 4) if current_price else None,
                "open": info.get("regularMarketOpen"),
                "previous_close": info.get("previousClose") or info.get("regularMarketPreviousClose"),
                "day_low": info.get("dayLow") or info.get("regularMarketDayLow"),
                "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
                "week_52_low": info.get("fiftyTwoWeekLow"),
                "week_52_high": info.get("fiftyTwoWeekHigh"),
                "bid": info.get("bid"),
                "ask": info.get("ask"),
                "volume": info.get("volume") or info.get("regularMarketVolume"),
                "avg_volume_10d": info.get("averageVolume10days"),
            },
            "fundamentals": {
                "market_cap": info.get("marketCap"),
                "enterprise_value": info.get("enterpriseValue"),
                "pe_ratio_ttm": info.get("trailingPE"),
                "pe_ratio_forward": info.get("forwardPE"),
                "eps_ttm": info.get("trailingEps"),
                "eps_forward": info.get("forwardEps"),
                "price_to_book": info.get("priceToBook"),
                "dividend_yield": info.get("dividendYield"),
                "payout_ratio": info.get("payoutRatio"),
                "beta": info.get("beta"),
                "analyst_target": info.get("targetMeanPrice"),
            },
            "company": {
                "name": info.get("longName") or info.get("shortName"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "currency": info.get("currency"),
                "exchange": info.get("exchange"),
            },
        }
    except Exception as exc:
        logger.exception("get_stock_quote failed for %s", ticker)
        return {"success": False, "ticker": ticker.upper(), "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool: get_historical_prices
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Fetch OHLCV (Open-High-Low-Close-Volume) historical price data for a ticker. "
        "Useful for back-testing strategies, building charts, and running statistical "
        "analyses. Supports periods from 1 day to 10 years and multiple intervals."
    )
)
def get_historical_prices(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
    max_rows: int = 252,
) -> Dict:
    """
    Retrieve historical OHLCV data.

    Args:
        ticker:   Exchange ticker symbol (e.g. 'JPM', 'GS', 'MS').
        period:   Lookback period. Valid values: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y,
                  5y, 10y, ytd, max.  Default: '1y'.
        interval: Data interval. Valid values: 1m, 2m, 5m, 15m, 30m, 60m, 90m,
                  1h, 1d, 5d, 1wk, 1mo, 3mo.  Default: '1d'.
        max_rows: Maximum number of rows to return (most recent). Default: 252.

    Returns:
        Dictionary with list of OHLCV records and summary statistics.
    """
    try:
        df = _fetch_history(ticker, period=period, interval=interval)
        df = df.tail(max_rows)

        records = []
        for ts, row in df.iterrows():
            records.append({
                "date": ts.isoformat(),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            })

        closes = df["Close"]
        return {
            "success": True,
            "ticker": ticker.upper(),
            "period": period,
            "interval": interval,
            "rows": len(records),
            "data": records,
            "summary": {
                "start_date": records[0]["date"] if records else None,
                "end_date": records[-1]["date"] if records else None,
                "start_price": records[0]["close"] if records else None,
                "end_price": records[-1]["close"] if records else None,
                "total_return_pct": round(
                    (float(closes.iloc[-1]) / float(closes.iloc[0]) - 1) * 100, 2
                ) if len(closes) > 1 else None,
                "high": round(float(closes.max()), 4),
                "low": round(float(closes.min()), 4),
                "avg_volume": int(df["Volume"].mean()),
            },
        }
    except Exception as exc:
        logger.exception("get_historical_prices failed for %s", ticker)
        return {"success": False, "ticker": ticker.upper(), "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool: calculate_portfolio_metrics
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Analyse a multi-asset portfolio: compute weighted returns, annualised "
        "volatility, Sharpe ratio, maximum drawdown, Sortino ratio, and "
        "Value-at-Risk (both parametric and historical simulation). "
        "Used in asset management, wealth advisory, and risk management desks."
    )
)
def calculate_portfolio_metrics(
    tickers: List[str],
    weights: Optional[List[float]] = None,
    period: str = "1y",
    risk_free_rate: float = 0.05,
    var_confidence: float = 0.95,
) -> Dict:
    """
    Compute comprehensive portfolio performance and risk metrics.

    Args:
        tickers:         List of ticker symbols (e.g. ['JPM', 'BAC', 'GS', 'MS']).
        weights:         Portfolio weights summing to 1.0. Equal-weight if omitted.
        period:          Historical lookback period (default: '1y').
        risk_free_rate:  Annualised risk-free rate as a decimal (default: 0.05 = 5%).
        var_confidence:  Confidence level for VaR (default: 0.95 = 95%).

    Returns:
        Dictionary with return, risk, and ratio metrics for the portfolio.
    """
    try:
        if not tickers:
            raise ValueError("At least one ticker is required.")

        n = len(tickers)
        if weights is None:
            weights = [1.0 / n] * n
        if len(weights) != n:
            raise ValueError("Length of 'weights' must match length of 'tickers'.")
        if abs(sum(weights) - 1.0) > 1e-6:
            raise ValueError("Weights must sum to 1.0.")

        # Download adjusted closes
        close_frames: List[pd.Series] = []
        for sym in tickers:
            df = _fetch_history(sym, period=period, interval="1d")
            close_frames.append(df["Close"].rename(sym))

        prices = pd.concat(close_frames, axis=1).dropna()
        daily_returns = prices.pct_change().dropna()
        portfolio_returns = daily_returns.dot(weights)

        ann = 252.0
        total_ret = float((prices.iloc[-1] / prices.iloc[0] - 1).dot(weights))
        ann_ret = (1 + total_ret) ** (ann / len(portfolio_returns)) - 1
        ann_vol = float(portfolio_returns.std() * math.sqrt(ann))
        sharpe = (ann_ret - risk_free_rate) / ann_vol if ann_vol > 0 else None

        # Sortino ratio (downside deviation)
        downside = portfolio_returns[portfolio_returns < 0]
        downside_std = float(downside.std() * math.sqrt(ann)) if not downside.empty else 0.0
        sortino = (ann_ret - risk_free_rate) / downside_std if downside_std > 0 else None

        # Maximum drawdown
        cumulative = (1 + portfolio_returns).cumprod()
        rolling_max = cumulative.cummax()
        drawdown = (cumulative - rolling_max) / rolling_max
        max_drawdown = float(drawdown.min())

        # Value-at-Risk (parametric)
        var_param = float(
            stats.norm.ppf(1 - var_confidence, loc=portfolio_returns.mean(), scale=portfolio_returns.std())
        )
        # Value-at-Risk (historical simulation)
        var_hist = float(portfolio_returns.quantile(1 - var_confidence))

        # Individual asset contributions
        asset_contributions = {}
        for sym, w in zip(tickers, weights):
            s = daily_returns[sym]
            asset_contributions[sym] = {
                "weight": round(w, 4),
                "annualised_return_pct": round(
                    ((1 + float(s.mean())) ** ann - 1) * 100, 2
                ),
                "annualised_volatility_pct": round(float(s.std() * math.sqrt(ann)) * 100, 2),
            }

        return {
            "success": True,
            "portfolio": {
                "tickers": tickers,
                "weights": [round(w, 4) for w in weights],
                "period": period,
                "observations": int(len(portfolio_returns)),
            },
            "performance": {
                "total_return_pct": round(total_ret * 100, 2),
                "annualised_return_pct": round(ann_ret * 100, 2),
                "annualised_volatility_pct": round(ann_vol * 100, 2),
                "sharpe_ratio": round(sharpe, 4) if sharpe is not None else None,
                "sortino_ratio": round(sortino, 4) if sortino is not None else None,
                "max_drawdown_pct": round(max_drawdown * 100, 2),
            },
            "risk": {
                "var_1d_parametric_pct": round(var_param * 100, 2),
                "var_1d_historical_pct": round(var_hist * 100, 2),
                "var_confidence_level": var_confidence,
                "risk_free_rate": risk_free_rate,
            },
            "asset_contributions": asset_contributions,
        }
    except Exception as exc:
        logger.exception("calculate_portfolio_metrics failed")
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool: calculate_options_price
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Price European call and put options using the Black-Scholes-Merton model "
        "and compute all first-order Greeks (delta, gamma, theta, vega, rho). "
        "This is the industry-standard model used in derivatives desks at banks "
        "such as JPMorgan Chase, Goldman Sachs, and Bank of America."
    )
)
def calculate_options_price(
    spot_price: float,
    strike_price: float,
    time_to_expiry_days: float,
    volatility: float,
    risk_free_rate: float = 0.05,
    dividend_yield: float = 0.0,
) -> Dict:
    """
    Price a European option and compute Greeks via Black-Scholes-Merton.

    Args:
        spot_price:          Current underlying asset price (S).
        strike_price:        Option strike / exercise price (K).
        time_to_expiry_days: Number of calendar days until expiry (T in days).
        volatility:          Implied or historical annualised volatility as a
                             decimal (e.g. 0.20 = 20%).
        risk_free_rate:      Annualised continuously-compounded risk-free rate
                             as a decimal (default: 0.05).
        dividend_yield:      Continuous dividend yield as a decimal (default: 0.0).

    Returns:
        Dictionary with call/put prices and Greek values.
    """
    try:
        if spot_price <= 0 or strike_price <= 0:
            raise ValueError("spot_price and strike_price must be positive.")
        if time_to_expiry_days <= 0:
            raise ValueError("time_to_expiry_days must be positive.")
        if volatility <= 0:
            raise ValueError("volatility must be positive.")

        T = time_to_expiry_days / 365.0
        S = spot_price
        K = strike_price
        r = risk_free_rate
        q = dividend_yield
        sigma = volatility

        d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        # Standard-normal CDF and PDF
        N = stats.norm.cdf
        n = stats.norm.pdf

        call_price = S * math.exp(-q * T) * N(d1) - K * math.exp(-r * T) * N(d2)
        put_price = K * math.exp(-r * T) * N(-d2) - S * math.exp(-q * T) * N(-d1)

        # Greeks
        delta_call = math.exp(-q * T) * N(d1)
        delta_put = delta_call - math.exp(-q * T)
        gamma = math.exp(-q * T) * n(d1) / (S * sigma * math.sqrt(T))
        theta_call = (
            -S * math.exp(-q * T) * n(d1) * sigma / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * N(d2)
            + q * S * math.exp(-q * T) * N(d1)
        ) / 365.0
        theta_put = (
            -S * math.exp(-q * T) * n(d1) * sigma / (2 * math.sqrt(T))
            + r * K * math.exp(-r * T) * N(-d2)
            - q * S * math.exp(-q * T) * N(-d1)
        ) / 365.0
        vega = S * math.exp(-q * T) * n(d1) * math.sqrt(T) / 100.0  # per 1% vol move
        rho_call = K * T * math.exp(-r * T) * N(d2) / 100.0          # per 1% rate move
        rho_put = -K * T * math.exp(-r * T) * N(-d2) / 100.0

        intrinsic_call = max(S - K, 0.0)
        intrinsic_put = max(K - S, 0.0)

        return {
            "success": True,
            "inputs": {
                "spot_price": S,
                "strike_price": K,
                "time_to_expiry_days": time_to_expiry_days,
                "time_to_expiry_years": round(T, 6),
                "volatility_pct": round(sigma * 100, 2),
                "risk_free_rate_pct": round(r * 100, 2),
                "dividend_yield_pct": round(q * 100, 2),
            },
            "intermediates": {
                "d1": round(d1, 6),
                "d2": round(d2, 6),
            },
            "call": {
                "price": round(call_price, 4),
                "intrinsic_value": round(intrinsic_call, 4),
                "time_value": round(call_price - intrinsic_call, 4),
                "delta": round(delta_call, 6),
                "theta_per_day": round(theta_call, 6),
                "rho_per_1pct": round(rho_call, 6),
            },
            "put": {
                "price": round(put_price, 4),
                "intrinsic_value": round(intrinsic_put, 4),
                "time_value": round(put_price - intrinsic_put, 4),
                "delta": round(delta_put, 6),
                "theta_per_day": round(theta_put, 6),
                "rho_per_1pct": round(rho_put, 6),
            },
            "shared_greeks": {
                "gamma": round(gamma, 6),
                "vega_per_1pct_vol": round(vega, 6),
            },
            "put_call_parity_check": round(call_price - put_price - (S * math.exp(-q * T) - K * math.exp(-r * T)), 8),
        }
    except Exception as exc:
        logger.exception("calculate_options_price failed")
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool: calculate_bond_metrics
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Price a fixed-rate bond and compute its yield-to-maturity, modified "
        "duration, Macaulay duration, and convexity. Essential for fixed-income "
        "desks and treasury operations at major banks."
    )
)
def calculate_bond_metrics(
    face_value: float,
    coupon_rate: float,
    years_to_maturity: float,
    market_price: Optional[float] = None,
    yield_to_maturity: Optional[float] = None,
    coupon_frequency: int = 2,
) -> Dict:
    """
    Price a fixed-rate bond and compute duration and convexity.

    Provide either market_price (to solve for YTM) or yield_to_maturity
    (to solve for price). At least one must be supplied.

    Args:
        face_value:         Par / face value of the bond (e.g. 1000.0).
        coupon_rate:        Annual coupon rate as a decimal (e.g. 0.05 = 5%).
        years_to_maturity:  Years until maturity (e.g. 10.0).
        market_price:       Current clean market price. Supply to compute YTM.
        yield_to_maturity:  Required yield as a decimal. Supply to compute price.
        coupon_frequency:   Coupon payments per year (1 = annual, 2 = semi-annual).

    Returns:
        Dictionary with price, YTM, Macaulay duration, modified duration,
        convexity, and DV01 (dollar value of 1 basis-point change in yield).
    """
    try:
        if market_price is None and yield_to_maturity is None:
            raise ValueError("Provide either market_price or yield_to_maturity.")
        if face_value <= 0:
            raise ValueError("face_value must be positive.")
        if coupon_rate < 0:
            raise ValueError("coupon_rate cannot be negative.")
        if years_to_maturity <= 0:
            raise ValueError("years_to_maturity must be positive.")
        if coupon_frequency not in (1, 2, 4, 12):
            raise ValueError("coupon_frequency must be 1, 2, 4, or 12.")

        freq = coupon_frequency
        n_periods = int(years_to_maturity * freq)
        coupon_payment = face_value * coupon_rate / freq

        def _price_from_yield(ytm_decimal: float) -> float:
            r = ytm_decimal / freq
            if r == 0:
                return coupon_payment * n_periods + face_value
            pv_coupons = coupon_payment * (1 - (1 + r) ** (-n_periods)) / r
            pv_face = face_value / (1 + r) ** n_periods
            return pv_coupons + pv_face

        if market_price is not None and yield_to_maturity is None:
            # Solve for YTM via bisection
            lo, hi = 1e-8, 5.0
            for _ in range(200):
                mid = (lo + hi) / 2
                if _price_from_yield(mid) > market_price:
                    lo = mid
                else:
                    hi = mid
                if hi - lo < 1e-10:
                    break
            ytm = (lo + hi) / 2
            price = market_price
        else:
            ytm = yield_to_maturity  # type: ignore[assignment]
            price = _price_from_yield(ytm)

        # Macaulay duration
        r = ytm / freq
        if r == 0:
            # Flat yield – simple weighted average of time
            times = [(t / freq) * coupon_payment for t in range(1, n_periods + 1)]
            times[-1] += face_value  # add face value to last payment
            mac_duration = sum((t / freq) * pmt for t, pmt in enumerate(times, 1)) / price
        else:
            weighted_pv = sum(
                (t / freq) * (coupon_payment / (1 + r) ** t)
                for t in range(1, n_periods + 1)
            ) + (n_periods / freq) * (face_value / (1 + r) ** n_periods)
            mac_duration = weighted_pv / price

        mod_duration = mac_duration / (1 + ytm / freq)

        # Convexity
        convexity = sum(
            (t / freq) * ((t / freq) + (1 / freq)) * coupon_payment / (1 + r) ** t
            for t in range(1, n_periods + 1)
        )
        convexity += (n_periods / freq) * ((n_periods / freq) + (1 / freq)) * face_value / (1 + r) ** n_periods
        convexity /= price * (1 + ytm / freq) ** 2

        dv01 = mod_duration * price * 0.0001

        return {
            "success": True,
            "inputs": {
                "face_value": face_value,
                "coupon_rate_pct": round(coupon_rate * 100, 4),
                "years_to_maturity": years_to_maturity,
                "coupon_frequency": freq,
            },
            "results": {
                "clean_price": round(price, 4),
                "yield_to_maturity_pct": round(ytm * 100, 4),
                "macaulay_duration_years": round(mac_duration, 4),
                "modified_duration": round(mod_duration, 4),
                "convexity": round(convexity, 4),
                "dv01_dollar_per_bp": round(dv01, 4),
            },
            "interpretation": {
                "price_vs_par": "at par" if abs(price - face_value) < 0.01
                               else ("at premium" if price > face_value else "at discount"),
                "note": (
                    "Modified duration approximates % price change for a 1% yield move. "
                    "Convexity corrects for curvature."
                ),
            },
        }
    except Exception as exc:
        logger.exception("calculate_bond_metrics failed")
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool: get_fx_rates
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Retrieve the latest foreign-exchange rates and perform cross-currency "
        "conversions. Supports all major currency pairs. Used in FX trading desks, "
        "treasury management, and international transaction processing."
    )
)
def get_fx_rates(
    base_currency: str,
    target_currencies: List[str],
    amount: float = 1.0,
) -> Dict:
    """
    Get live FX rates and convert an amount from a base currency.

    Args:
        base_currency:      ISO 4217 base currency code (e.g. 'USD', 'EUR', 'GBP').
        target_currencies:  List of target currency codes (e.g. ['EUR', 'GBP', 'JPY']).
        amount:             Amount in base currency to convert (default: 1.0).

    Returns:
        Dictionary with current rates and converted amounts.
    """
    try:
        base = base_currency.upper()
        results = {}
        errors = []

        for tgt in target_currencies:
            tgt_upper = tgt.upper()
            pair = f"{base}{tgt_upper}=X"
            try:
                tk = yf.Ticker(pair)
                fi = tk.fast_info
                rate = fi.last_price
                if rate is None:
                    # Fall back to history
                    hist = tk.history(period="5d", interval="1d")
                    rate = float(hist["Close"].iloc[-1]) if not hist.empty else None
                if rate is None:
                    errors.append(f"Could not fetch rate for {base}/{tgt_upper}")
                    continue
                results[tgt_upper] = {
                    "rate": round(float(rate), 6),
                    "converted_amount": round(amount * float(rate), 4),
                    "inverse_rate": round(1.0 / float(rate), 6),
                }
            except Exception as e:
                errors.append(f"{base}/{tgt_upper}: {str(e)}")

        return {
            "success": True,
            "base_currency": base,
            "amount": amount,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rates": results,
            "errors": errors if errors else None,
        }
    except Exception as exc:
        logger.exception("get_fx_rates failed")
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool: get_market_indices
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Get a snapshot of the world's major equity indices, US Treasury yields, "
        "and key commodity prices. Provides a quick macro overview for market "
        "strategists and portfolio managers at global financial institutions."
    )
)
def get_market_indices() -> Dict:
    """
    Retrieve live quotes for major market benchmarks, yields, and commodities.

    Returns:
        Dictionary grouped by asset class with current prices and daily changes.
    """
    groups = {
        "equity_indices": {
            "S&P 500": "^GSPC",
            "NASDAQ 100": "^NDX",
            "Dow Jones": "^DJI",
            "FTSE 100": "^FTSE",
            "DAX": "^GDAXI",
            "Nikkei 225": "^N225",
            "Hang Seng": "^HSI",
            "JSE All Share": "^JN0U.JO",
        },
        "us_treasury_yields": {
            "2Y Yield": "^IRX",
            "10Y Yield": "^TNX",
            "30Y Yield": "^TYX",
        },
        "commodities": {
            "Gold": "GC=F",
            "Silver": "SI=F",
            "Crude Oil (WTI)": "CL=F",
            "Brent Crude": "BZ=F",
            "Natural Gas": "NG=F",
        },
        "volatility": {
            "VIX": "^VIX",
            "VVIX": "^VVIX",
        },
    }

    output: Dict[str, Dict] = {}
    try:
        for group, symbols in groups.items():
            output[group] = {}
            for name, sym in symbols.items():
                try:
                    tk = yf.Ticker(sym)
                    fi = tk.fast_info
                    price = fi.last_price
                    prev_close = fi.previous_close
                    if price is not None and prev_close:
                        change = price - prev_close
                        change_pct = (change / prev_close) * 100
                    else:
                        change = change_pct = None
                    output[group][name] = {
                        "symbol": sym,
                        "price": round(float(price), 4) if price else None,
                        "change": round(float(change), 4) if change is not None else None,
                        "change_pct": round(float(change_pct), 2) if change_pct is not None else None,
                    }
                except Exception:
                    output[group][name] = {"symbol": sym, "price": None, "error": "fetch_failed"}

        return {
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **output,
        }
    except Exception as exc:
        logger.exception("get_market_indices failed")
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool: calculate_technical_indicators
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Compute a full suite of technical analysis indicators for an equity: "
        "Simple & Exponential Moving Averages (SMA/EMA), Relative Strength Index "
        "(RSI), MACD, Bollinger Bands, Average True Range (ATR), and On-Balance "
        "Volume (OBV). Used by quantitative analysts and algorithmic trading desks."
    )
)
def calculate_technical_indicators(
    ticker: str,
    period: str = "6mo",
) -> Dict:
    """
    Calculate common technical analysis indicators.

    Args:
        ticker: Exchange ticker symbol.
        period: Lookback period for source data (default: '6mo').

    Returns:
        Dictionary with the most recent values for each indicator.
    """
    try:
        df = _fetch_history(ticker, period=period, interval="1d")
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        def sma(series: pd.Series, n: int) -> float:
            return float(series.rolling(n).mean().iloc[-1])

        def ema(series: pd.Series, n: int) -> float:
            return float(series.ewm(span=n, adjust=False).mean().iloc[-1])

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_histogram = macd_line - signal_line

        # Bollinger Bands (20-day, 2 std)
        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std
        current_price = float(close.iloc[-1])
        bb_pct = float(
            (current_price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])
        ) if (bb_upper.iloc[-1] - bb_lower.iloc[-1]) != 0 else 0.5

        # Average True Range (ATR-14)
        hl = high - low
        hc = (high - close.shift()).abs()
        lc = (low - close.shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])

        # On-Balance Volume (OBV) – most recent value
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        obv_value = int(obv.iloc[-1])

        def _r(x: Optional[float], n: int = 4) -> Optional[float]:
            return round(x, n) if x is not None and not math.isnan(x) else None

        return {
            "success": True,
            "ticker": ticker.upper(),
            "period": period,
            "as_of": df.index[-1].isoformat(),
            "current_price": round(current_price, 4),
            "moving_averages": {
                "sma_20": _r(sma(close, 20)),
                "sma_50": _r(sma(close, 50)),
                "sma_200": _r(sma(close, 200)),
                "ema_12": _r(ema(close, 12)),
                "ema_26": _r(ema(close, 26)),
                "ema_50": _r(ema(close, 50)),
            },
            "momentum": {
                "rsi_14": _r(rsi, 2),
                "rsi_signal": (
                    "oversold" if rsi < 30 else ("overbought" if rsi > 70 else "neutral")
                ),
                "macd": _r(float(macd_line.iloc[-1])),
                "macd_signal": _r(float(signal_line.iloc[-1])),
                "macd_histogram": _r(float(macd_histogram.iloc[-1])),
                "macd_crossover": (
                    "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] else "bearish"
                ),
            },
            "volatility": {
                "bollinger_upper": _r(float(bb_upper.iloc[-1])),
                "bollinger_mid": _r(float(bb_mid.iloc[-1])),
                "bollinger_lower": _r(float(bb_lower.iloc[-1])),
                "bollinger_width_pct": _r(
                    (float(bb_upper.iloc[-1]) - float(bb_lower.iloc[-1])) / float(bb_mid.iloc[-1]) * 100, 2
                ),
                "bollinger_pct_b": _r(bb_pct, 4),
                "atr_14": _r(atr),
            },
            "volume": {
                "obv": obv_value,
                "avg_volume_20d": int(volume.rolling(20).mean().iloc[-1]),
            },
        }
    except Exception as exc:
        logger.exception("calculate_technical_indicators failed for %s", ticker)
        return {"success": False, "ticker": ticker.upper(), "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool: screen_stocks
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Screen a watchlist of equities against fundamental and technical criteria. "
        "Returns a ranked summary table useful for equity research, sector rotation "
        "strategies, and portfolio construction workflows at asset managers and banks."
    )
)
def screen_stocks(
    tickers: List[str],
    min_market_cap_usd: Optional[float] = None,
    max_pe_ratio: Optional[float] = None,
    min_dividend_yield_pct: Optional[float] = None,
    max_beta: Optional[float] = None,
) -> Dict:
    """
    Screen a list of equities against optional fundamental filters.

    Args:
        tickers:                List of ticker symbols to screen.
        min_market_cap_usd:     Minimum market capitalisation in USD.
        max_pe_ratio:           Maximum trailing P/E ratio.
        min_dividend_yield_pct: Minimum dividend yield as a percentage (e.g. 2.0).
        max_beta:               Maximum 5-year monthly beta.

    Returns:
        Dictionary with passed/filtered lists and a data table for each ticker.
    """
    try:
        rows = []
        for sym in tickers:
            try:
                t = yf.Ticker(sym.upper())
                info = t.info
                fi = t.fast_info

                market_cap = info.get("marketCap")
                pe = info.get("trailingPE")
                div_yield = info.get("dividendYield")  # decimal
                beta = info.get("beta")
                price = fi.last_price or info.get("currentPrice") or info.get("regularMarketPrice")

                passed = True
                if min_market_cap_usd and (market_cap is None or market_cap < min_market_cap_usd):
                    passed = False
                if max_pe_ratio and pe is not None and pe > max_pe_ratio:
                    passed = False
                if min_dividend_yield_pct and (div_yield is None or div_yield * 100 < min_dividend_yield_pct):
                    passed = False
                if max_beta and beta is not None and beta > max_beta:
                    passed = False

                rows.append({
                    "ticker": sym.upper(),
                    "name": info.get("longName") or info.get("shortName"),
                    "sector": info.get("sector"),
                    "price": round(float(price), 2) if price else None,
                    "market_cap_bn": round(market_cap / 1e9, 2) if market_cap else None,
                    "pe_ratio": round(pe, 2) if pe else None,
                    "dividend_yield_pct": round(div_yield * 100, 2) if div_yield else None,
                    "beta": round(beta, 2) if beta else None,
                    "passed_screen": passed,
                })
            except Exception as e:
                rows.append({
                    "ticker": sym.upper(),
                    "error": str(e),
                    "passed_screen": False,
                })

        passed = [r for r in rows if r.get("passed_screen")]
        failed = [r for r in rows if not r.get("passed_screen")]

        return {
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "screen_criteria": {
                "min_market_cap_usd": min_market_cap_usd,
                "max_pe_ratio": max_pe_ratio,
                "min_dividend_yield_pct": min_dividend_yield_pct,
                "max_beta": max_beta,
            },
            "summary": {
                "total_screened": len(rows),
                "passed": len(passed),
                "filtered_out": len(failed),
            },
            "passed": passed,
            "filtered_out": failed,
        }
    except Exception as exc:
        logger.exception("screen_stocks failed")
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool: calculate_risk_metrics
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Calculate advanced risk metrics for a single equity relative to a benchmark: "
        "beta, alpha (Jensen), information ratio, tracking error, Calmar ratio, "
        "tail-risk (CVaR/Expected Shortfall), and rolling 30-day volatility. "
        "Used by risk management and compliance teams at major financial institutions."
    )
)
def calculate_risk_metrics(
    ticker: str,
    benchmark: str = "^GSPC",
    period: str = "2y",
    risk_free_rate: float = 0.05,
) -> Dict:
    """
    Compute risk and risk-adjusted return metrics versus a benchmark.

    Args:
        ticker:          Equity ticker symbol.
        benchmark:       Benchmark index symbol (default: '^GSPC' = S&P 500).
        period:          Historical lookback period (default: '2y').
        risk_free_rate:  Annualised risk-free rate as a decimal (default: 0.05).

    Returns:
        Dictionary with alpha, beta, information ratio, CVaR, and rolling volatility.
    """
    try:
        asset_df = _fetch_history(ticker, period=period, interval="1d")
        bench_df = _fetch_history(benchmark, period=period, interval="1d")

        asset_ret = asset_df["Close"].pct_change().dropna()
        bench_ret = bench_df["Close"].pct_change().dropna()

        # Align dates
        combined = pd.concat([asset_ret, bench_ret], axis=1, keys=["asset", "bench"]).dropna()
        ar = combined["asset"]
        br = combined["bench"]

        ann = 252.0
        rf_daily = risk_free_rate / ann

        # Beta and Alpha
        cov = np.cov(ar, br)
        beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] != 0 else None
        ann_asset = (1 + float(ar.mean())) ** ann - 1
        ann_bench = (1 + float(br.mean())) ** ann - 1
        alpha = ann_asset - (risk_free_rate + beta * (ann_bench - risk_free_rate)) if beta else None

        # Tracking error and information ratio
        active_return = ar - br
        tracking_error = float(active_return.std() * math.sqrt(ann))
        info_ratio = float(active_return.mean() * ann / tracking_error) if tracking_error > 0 else None

        # Sharpe
        ann_vol = float(ar.std() * math.sqrt(ann))
        sharpe = (ann_asset - risk_free_rate) / ann_vol if ann_vol > 0 else None

        # Maximum drawdown
        cum = (1 + ar).cumprod()
        max_dd = float(((cum - cum.cummax()) / cum.cummax()).min())

        # Calmar ratio
        calmar = -ann_asset / max_dd if max_dd < 0 else None

        # CVaR (Expected Shortfall at 95%)
        var_95 = float(ar.quantile(0.05))
        cvar_95 = float(ar[ar <= var_95].mean())

        # Rolling 30-day volatility (latest)
        rolling_vol_30 = float(ar.rolling(30).std().iloc[-1] * math.sqrt(ann))

        # Correlation
        correlation = float(ar.corr(br))

        def _r(x, n=4):
            return round(x, n) if x is not None and not math.isnan(x) else None

        return {
            "success": True,
            "ticker": ticker.upper(),
            "benchmark": benchmark,
            "period": period,
            "observations": int(len(ar)),
            "return_metrics": {
                "annualised_return_pct": _r(ann_asset * 100, 2),
                "benchmark_return_pct": _r(ann_bench * 100, 2),
                "alpha_pct": _r(alpha * 100, 2) if alpha else None,
            },
            "risk_metrics": {
                "beta": _r(beta),
                "annualised_volatility_pct": _r(ann_vol * 100, 2),
                "rolling_30d_volatility_pct": _r(rolling_vol_30 * 100, 2),
                "max_drawdown_pct": _r(max_dd * 100, 2),
                "tracking_error_pct": _r(tracking_error * 100, 2),
                "correlation_with_benchmark": _r(correlation),
                "var_95_1d_pct": _r(var_95 * 100, 2),
                "cvar_95_1d_pct": _r(cvar_95 * 100, 2),
            },
            "ratios": {
                "sharpe_ratio": _r(sharpe),
                "information_ratio": _r(info_ratio),
                "calmar_ratio": _r(calmar),
            },
        }
    except Exception as exc:
        logger.exception("calculate_risk_metrics failed for %s", ticker)
        return {"success": False, "ticker": ticker.upper(), "error": str(exc)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("🏦 Starting Financial Markets MCP Server...")
    print("   Tools: stock quotes, historical prices, portfolio metrics,")
    print("          options pricing (Black-Scholes), bond metrics, FX rates,")
    print("          market indices, technical indicators, stock screener,")
    print("          and advanced risk analytics.")
    mcp.run(transport="stdio")
