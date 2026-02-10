# Complete Setup Guide - Get Running in 5 Minutes

## Overview

This guide will get you from zero to running the **Arbitrage Advisor Web App** with automatic market discovery.

## What You Need

1. **Python 3.8+** (check: `python3 --version`)
2. **Polymarket API credentials** (optional for testing)
3. **Kalshi account credentials** (optional for testing)

## Step-by-Step Setup

### Step 1: Install Dependencies (2 minutes)

```bash
cd /Users/williameklund/kalshipolytest

# Install all required packages
pip install -r requirements.txt
```

**What gets installed**:
- `flask` & `flask-cors` - Web server
- `py-clob-client` - Polymarket API
- `kalshi-python` - Kalshi API
- `rich` - Terminal UI
- `pandas` - Data analysis

### Step 2: Configure API Credentials (2 minutes)

```bash
# Copy the template
cp config_template.json config.json

# Edit with your credentials
nano config.json  # or use any text editor
```

**Edit config.json**:
```json
{
  "polymarket": {
    "api_key": "YOUR_POLYMARKET_API_KEY",
    "private_key": "YOUR_POLYMARKET_PRIVATE_KEY"
  },
  "kalshi": {
    "email": "your_kalshi_email@example.com",
    "password": "your_kalshi_password"
  },
  "settings": {
    "budget": 1000.0,
    "min_roi_threshold": 1.0,
    "refresh_seconds": 30
  }
}
```

**Where to get credentials**:

**Polymarket**:
1. Go to https://polymarket.com
2. Connect wallet
3. Go to Settings → API Keys
4. Create new API key
5. Save the key and private key

**Kalshi**:
1. Go to https://kalshi.com
2. Sign up / Log in
3. Use your email and password (API uses these)

**Optional**: You can test without credentials in limited mode!

### Step 3: Test the Core Engine (30 seconds)

Before starting the web app, verify the math engine works:

```bash
python3 arb_engine_bidirectional.py
```

**Expected output**:
```
=== Bidirectional Arbitrage Engine Test ===

Direction Comparison:
           Direction Poly Side Kalshi Side  ROI %
Poly YES + Kalshi NO       YES          NO 72.33%
Poly NO + Kalshi YES        NO         YES 81.95%

Best Opportunity: Poly NO + Kalshi YES
```

✅ **If you see this, the core is working!**

### Step 4: Start the Web App (30 seconds)

```bash
python3 web_app.py
```

**You should see**:
```
============================================================
🚀 Arbitrage Advisor Web Interface
============================================================

✓ Clients initialized successfully

📊 Starting web server...
🌐 Open your browser to: http://localhost:5000

Press Ctrl+C to stop
```

### Step 5: Open the Web Interface

Open your browser and go to:

```
http://localhost:5000
```

You should see a beautiful dark-themed dashboard!

---

## Using the Web Interface

### First-Time Workflow

1. **Click "🔍 Auto-Discover Markets"**
   - This scans both platforms for matching markets
   - Uses fuzzy matching to find similar markets
   - Saves results to `discovered_markets.json`
   - Takes 30-60 seconds

2. **Click "📊 Scan for Arbitrage"**
   - Fetches live prices for all discovered pairs
   - Calculates arbitrage in BOTH directions
   - Shows opportunities sorted by ROI
   - Updates every 30 seconds

3. **Click any opportunity to see details**
   - Shows exact quantities and prices
   - Displays expected profit for both outcomes
   - Provides manual execution instructions
   - Includes safety warnings

### Dashboard Controls

**Buttons**:
- 🔍 **Auto-Discover Markets** - Find all matching pairs automatically
- 📊 **Scan for Arbitrage** - Calculate opportunities for discovered pairs
- 🔄 **Refresh** - Update current opportunities

**Settings**:
- **Budget** - How much capital to allocate per opportunity
- **Use Auto-Discovered Markets** - Use automatically found pairs vs manual mapping

### Status Bar

Shows real-time information:
- **Status**: Current operation (Ready, Scanning, etc.)
- **Last Update**: When data was last refreshed
- **Markets**: Total markets being monitored
- **Profitable**: How many have positive ROI

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'flask'"

```bash
pip install flask flask-cors
```

### "ModuleNotFoundError: No module named 'py_clob_client'"

```bash
pip install py-clob-client kalshi-python
```

### "API authentication failed"

**Check**:
1. Is `config.json` in the same directory as `web_app.py`?
2. Are your credentials correct?
3. Are your API keys active?

**Solution**: You can still run in test mode without credentials!

### "No markets found"

**Possible causes**:
1. API rate limiting - wait 1 minute and try again
2. Network issues - check your connection
3. Platform maintenance - try later

### Web app won't start

**Check**:
1. Is port 5000 already in use?
   ```bash
   lsof -i :5000
   # If something is using it:
   kill -9 <PID>
   ```

2. Try a different port:
   ```python
   # Edit web_app.py, change last line:
   app.run(debug=True, host='0.0.0.0', port=5001)
   ```

### Browser shows "Connection refused"

Make sure the Flask server is running:
```bash
python3 web_app.py
# Should show "Running on http://0.0.0.0:5000"
```

---

## Testing Without API Credentials

You can test the system without real API credentials:

### Option 1: Use the CLI with Manual Prices

```bash
python3 arbitrage_advisor.py --manual \
  --poly-yes 0.52 --poly-no 0.49 \
  --kalshi-yes 54 --kalshi-no 46 \
  --budget 1000
```

### Option 2: Mock Data Mode (Coming Soon)

We can add a mock data mode that simulates API responses for testing.

---

## Architecture Overview

### How Auto-Discovery Works

1. **Fetch Markets**
   - Queries Polymarket for active markets
   - Queries Kalshi for open markets
   - Filters by minimum liquidity ($100+)

2. **Fuzzy Matching**
   - Normalizes market titles (lowercase, remove punctuation)
   - Extracts keywords (removes stop words)
   - Calculates similarity score using:
     - Jaccard similarity (keyword overlap)
     - Sequence similarity (text matching)
   - Threshold: 60% similarity minimum

3. **Pair Ranking**
   - Sorts by similarity score
   - Considers total liquidity
   - Saves top matches to JSON

4. **Example Matches**:
   - "Bitcoin to reach $100k by Dec 31" ↔ "BTC-24DEC31-T100000" (95% match)
   - "Trump wins 2024 election" ↔ "PRES-2024-TRUMP" (88% match)
   - "Ethereum above $5000" ↔ "ETH-24DEC-T5000" (92% match)

### How Arbitrage Detection Works

For each discovered pair:

1. **Fetch Prices**
   - Polymarket: YES and NO prices
   - Kalshi: YES and NO prices

2. **Test Both Directions**
   - Direction 1: Buy Poly YES + Kalshi NO
   - Direction 2: Buy Poly NO + Kalshi YES

3. **Calculate Sizing**
   - Determines quantities for perfect hedge
   - Accounts for different contract sizes
   - Respects liquidity constraints

4. **Apply Fees**
   - Polymarket: 0.1% taker fee
   - Kalshi: Tiered fee (5-14% based on payout)

5. **Return Best**
   - Selects higher ROI direction
   - Shows expected profit for both outcomes

---

## File Structure After Setup

```
kalshipolytest/
├── config.json                  # Your API credentials (gitignored)
├── discovered_markets.json      # Auto-discovered pairs (created by app)
├── market_mapping.json          # Manual pairs (optional)
│
├── web_app.py                   # Main web server
├── market_discovery.py          # Auto-discovery engine
├── arb_engine_bidirectional.py  # Core arbitrage math
├── api_client.py                # Platform API clients
│
├── templates/
│   └── index.html              # Web interface
├── static/
│   ├── css/
│   │   └── style.css          # Styling
│   └── js/
│       └── app.js             # Frontend logic
│
└── [documentation files...]
```

---

## Performance Tips

### Speed Up Discovery

```python
# In web_app.py, reduce max_markets for faster scanning
discovery_engine.discover_pairs(
    max_markets=25,  # Reduced from 50
    min_similarity=0.7,  # Increased threshold
    min_liquidity=500.0  # Higher liquidity requirement
)
```

### Optimize Refresh Rate

```python
# In static/js/app.js, change auto-refresh interval
setInterval(() => {
    app.refreshOpportunities();
}, 60000);  // Changed from 30000 (30s) to 60000 (60s)
```

### Reduce API Calls

```python
# In api_client.py, increase rate limiting
rate_limiter = RateLimiter(max_calls_per_second=1)  # Reduced from 2
```

---

## Security Best Practices

### Protect Your Credentials

1. **Never commit config.json**
   ```bash
   # It's already in .gitignore, but double-check:
   cat .gitignore | grep config.json
   ```

2. **Use environment variables** (advanced):
   ```bash
   export POLYMARKET_API_KEY="your_key_here"
   export KALSHI_EMAIL="your_email_here"
   ```

3. **Rotate keys regularly**
   - Change API keys every 90 days
   - Especially after testing/sharing code

### Network Security

1. **Use HTTPS in production**:
   ```python
   # For production, use gunicorn with SSL
   gunicorn --certfile=cert.pem --keyfile=key.pem web_app:app
   ```

2. **Restrict access**:
   ```python
   # Change from 0.0.0.0 to 127.0.0.1 for localhost only
   app.run(debug=False, host='127.0.0.1', port=5000)
   ```

---

## Advanced Configuration

### Custom Discovery Parameters

Edit `web_app.py` to customize discovery:

```python
pairs = discovery_engine.discover_pairs(
    max_markets=100,        # More markets (slower)
    min_similarity=0.7,     # Stricter matching
    min_liquidity=500.0,    # Higher liquidity requirement
    save_to_file='my_custom_markets.json'
)
```

### Custom Budget per Market

Edit the scan endpoint in `web_app.py`:

```python
@app.route('/api/scan', methods=['POST'])
def start_scan():
    data = request.json

    # Use different budget for different market types
    budget = data.get('budget', 1000.0)

    # Custom logic here
    if 'bitcoin' in market_name.lower():
        budget = 2000.0  # More capital for BTC markets
```

---

## What's Next?

### Phase 1: ✅ Complete
- ✅ Auto-discovery of market pairs
- ✅ Bidirectional arbitrage detection
- ✅ Web interface with live updates
- ✅ Manual execution instructions

### Phase 2: Future Enhancements
- ⬜ Auto-execution module (place orders automatically)
- ⬜ Webhook alerts (Discord, Telegram, SMS)
- ⬜ Historical tracking and analytics
- ⬜ Portfolio management across multiple accounts
- ⬜ Mobile app (React Native)

---

## Quick Command Reference

```bash
# Start web app
python3 web_app.py

# Test core engine
python3 arb_engine_bidirectional.py

# Manual CLI scan
python3 arbitrage_advisor.py --manual \
  --poly-yes 0.52 --poly-no 0.49 \
  --kalshi-yes 54 --kalshi-no 46 \
  --budget 1000

# Test API discovery (requires credentials)
python3 market_discovery.py

# Install/update dependencies
pip install -r requirements.txt --upgrade
```

---

## Support

**Getting Started**: This file (SETUP_GUIDE.md)
**Quick Start**: QUICK_START.md
**Advanced Usage**: USAGE_GUIDE.md
**Architecture**: PROJECT_STRUCTURE.md

---

## Success Checklist

Before your first real arbitrage trade:

- [ ] Tested core engine (`arb_engine_bidirectional.py`)
- [ ] Web app running (`http://localhost:5000`)
- [ ] API credentials configured
- [ ] Auto-discovery successfully found pairs
- [ ] Scan shows at least one opportunity
- [ ] Clicked opportunity to see details
- [ ] Understand both Polymarket and Kalshi interfaces
- [ ] Have funds on both platforms
- [ ] Read the safety warnings in the UI

**You're ready to find real arbitrage! 🚀**

./run.sh — install deps (if needed), copy config template, start the web app
./run.sh stop — kill all running processes and free port 8080
./run.sh restart