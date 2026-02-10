# Polymarket vs. Kalshi Arbitrage Advisor

A Python-based arbitrage detection system for identifying risk-neutral synthetic arbitrage opportunities between Polymarket and Kalshi prediction markets. This tool **does not execute trades** - it only scans and outputs recommended positions for manual review.

**Key Feature**: **Bidirectional arbitrage detection** - automatically evaluates BOTH directions (Poly YES + Kalshi NO AND Poly NO + Kalshi YES) and selects the more profitable opportunity.

## Features

### Core Engines

**`arb_engine.py`** - Unidirectional (Original)
- **Fee Normalization**: Accurate calculation of Kalshi's tiered fee structure and Polymarket's 0.1% taker fee
- **No-Arbitrage Sizing**: Calculates exact contract quantities for perfectly hedged positions
- **High Precision**: Uses Python's `decimal` library for financial-grade calculations
- **Liquidity Constraints**: Automatically caps trade size based on order book depth

**`arb_engine_bidirectional.py`** - Bidirectional (Recommended)
- **Smart Direction Selection**: Evaluates BOTH Poly YES + Kalshi NO AND Poly NO + Kalshi YES
- **Automatic Optimization**: Returns the more profitable direction
- **Complete Analysis**: Shows comparison table of both opportunities
- **All Original Features**: Same precision, fees, and liquidity handling

### API Integration (`api_client.py`)
- **Polymarket**: Integration via `py-clob-client` with support for API key authentication
- **Kalshi**: Integration via `kalshi-python` with email/password or public API access
- **Weighted Average Pricing**: Calculates execution price when size exceeds first order book level
- **Rate Limiting**: Built-in protection against API throttling
- **Error Handling**: Robust timeout and connection error management

### Live Dashboard (`market_mapper.py`)
- **Market Mapping**: JSON-based mapping of Polymarket token IDs to Kalshi tickers
- **Rich Terminal UI**: Beautiful, live-updating table with color-coded signals
- **Real-time Alerts**: Highlighted notifications when ROI exceeds threshold (default: 1%)
- **Limit Order Suggestions**: Exact prices and quantities for manual order entry

## Installation

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Configure API credentials**:
```bash
cp config_template.json config.json
# Edit config.json with your actual credentials
```

3. **Set up market mappings**:
```bash
# market_mapping.json will be created automatically on first run
# Edit it to add your market pairs
```

## Usage

### Quick Test of Bidirectional Engine (Recommended)

```bash
# Automatically tests both directions and shows the better one
python3 arb_engine_bidirectional.py
```

Output example:
```
Direction Comparison:
           Direction Poly Side Kalshi Side  Poly Qty  Kalshi Qty  ROI %
Poly YES + Kalshi NO       YES          NO      1738          17 72.33%
Poly NO + Kalshi YES        NO         YES      1831          18 81.95% ← BETTER!

Best Opportunity: Poly NO + Kalshi YES
```

### Quick Test of Original Engine

```python
from arb_engine import ArbitrageCalculator

# Test single direction (Poly YES + Kalshi NO)
result = ArbitrageCalculator.calculate_no_arbitrage_sizing(
    poly_yes_price=0.52,      # 52 cents on Polymarket
    kalshi_no_price=46,        # 46 cents on Kalshi
    total_budget=1000.00,
    poly_liquidity=5000,
    kalshi_liquidity=50
)

print(f"ROI: {result['roi_percent']:.2f}%")
print(f"Buy {result['poly_quantity']} YES on Polymarket")
print(f"Buy {result['kalshi_quantity']} NO on Kalshi")
print(f"Expected profit: ${result['avg_profit']:.2f}")
```

### Run Live Dashboard

```python
from market_mapper import ArbitrageDashboard, MarketMapper
from api_client import PolymarketClient, KalshiClient

# Initialize
mapper = MarketMapper("market_mapping.json")
poly_client = PolymarketClient(api_key="...", private_key="...")
kalshi_client = KalshiClient(email="...", password="...")

# Create dashboard
dashboard = ArbitrageDashboard(
    poly_client=poly_client,
    kalshi_client=kalshi_client,
    market_mapper=mapper,
    budget=1000.0,
    min_roi_threshold=1.0
)

# Run live monitoring
dashboard.run_live_dashboard(refresh_seconds=30)
```

## Market Mapping Format

Edit `market_mapping.json` to define market pairs:

```json
{
  "BTC-100k": {
    "name": "Bitcoin to reach $100k by Dec 31",
    "polymarket_token_id": "0x1234567890abcdef...",
    "kalshi_ticker": "INXD-24DEC31-T4500",
    "description": "BTC >= $100,000 by Dec 31, 2024"
  }
}
```

## Strategy

**Type**: Risk-Neutral Synthetic Arbitrage
**Goal**: Maximize ROI per dollar while maintaining 100% hedge
**Order Type**: Limit orders only (no market orders)

### How It Works

1. **Identify Mispricing**: When `Poly YES + Kalshi NO < $1.00` (after fees)
2. **Calculate Hedge**: Determine exact quantities so payout is identical in both outcomes
3. **Check Liquidity**: Ensure sufficient order book depth to avoid slippage
4. **Output Signal**: Display ROI, sizing, and exact limit order prices
5. **Manual Execution**: User places limit orders on both platforms

### Example Arbitrage

```
Polymarket YES: $0.52
Kalshi NO: 46¢ ($0.46)
Combined: $0.98 (2% spread)

After fees (~0.5%): ~1.5% net ROI

Position:
- Buy 1000 YES on Polymarket @ $0.52 = $520
- Buy 10 NO on Kalshi @ $0.46 = $4.60

Payout regardless of outcome: ~$15 profit
```

## File Structure

```
kalshipolytest/
├── arb_engine.py           # Core math and fee calculations
├── api_client.py           # Polymarket & Kalshi API wrappers
├── market_mapper.py        # Dashboard and market mapping
├── requirements.txt        # Python dependencies
├── config_template.json    # API credential template
├── config.json            # Your actual credentials (gitignored)
├── market_mapping.json    # Your market pairs (auto-created)
└── README.md              # This file
```

## Safety Features

- **Read-Only Mode**: Can run without API credentials for testing
- **Liquidity Checks**: Never suggests trades exceeding available liquidity
- **Fee Accuracy**: Accounts for Kalshi's complex tiered structure
- **Decimal Precision**: No floating-point errors in financial calculations
- **Rate Limiting**: Prevents API throttling and bans

## Next Steps (Future Enhancements)

- **Auto-Trade Module**: Optional automated execution via limit orders
- **Historical Tracking**: Log all opportunities and executed trades
- **Backtesting**: Test strategy on historical market data
- **Multi-Account**: Support multiple API keys for larger capital deployment
- **Webhook Alerts**: Send notifications to Discord/Telegram

## Disclaimer

This tool is for educational and informational purposes. Prediction market trading carries financial risk. Always verify calculations and understand platform rules before placing trades. The authors are not responsible for any financial losses.

## License

MIT License - see LICENSE file for details
