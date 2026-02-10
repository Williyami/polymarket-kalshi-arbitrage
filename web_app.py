"""
Flask Web Application for Arbitrage Advisor
Beautiful web interface with live updates and auto-discovery
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import threading
import time
from datetime import datetime
from typing import Dict, List

from arb_engine_bidirectional import BidirectionalArbitrageCalculator
from api_client import PolymarketClient, KalshiClient, load_config
from market_discovery import MarketPairDiscovery

app = Flask(__name__)
CORS(app)

# Global state
scan_results = []
scan_status = {
    'scanning': False,
    'last_update': None,
    'total_markets': 0,
    'profitable_count': 0,
    'error': None
}

# API clients (initialized on startup)
poly_client = None
kalshi_client = None
discovery_engine = None


def initialize_clients():
    """Initialize API clients from config"""
    global poly_client, kalshi_client, discovery_engine

    errors = []
    config = load_config('config.json')

    try:
        poly_config = config.get('polymarket', {})
        poly_client = PolymarketClient(
            api_key=poly_config.get('api_key'),
            private_key=poly_config.get('private_key')
        )
    except Exception as e:
        errors.append(f"Polymarket: {e}")

    try:
        kalshi_config = config.get('kalshi', {})
        kalshi_client = KalshiClient(
            api_key_id=kalshi_config.get('api_key_id'),
            private_key_path=kalshi_config.get('private_key_path')
        )
    except Exception as e:
        errors.append(f"Kalshi: {e}")

    if poly_client and kalshi_client:
        try:
            discovery_engine = MarketPairDiscovery(poly_client, kalshi_client)
        except Exception as e:
            errors.append(f"Discovery engine: {e}")

    if not errors:
        return True, "All clients initialized successfully"
    elif discovery_engine:
        return True, f"Clients initialized with warnings: {'; '.join(errors)}"
    else:
        return False, '; '.join(errors)


def scan_single_pair(pair: Dict, budget: float) -> Dict:
    """
    Scan a single market pair for arbitrage

    Args:
        pair: Market pair dictionary
        budget: Budget to use

    Returns:
        Arbitrage opportunity dictionary
    """
    try:
        # Fetch prices from both platforms
        poly_yes = poly_client.get_best_yes_price_and_liquidity(pair['poly_id'])
        kalshi_no = kalshi_client.get_best_no_price_and_liquidity(pair['kalshi_ticker'])

        if not poly_yes['best_price'] or not kalshi_no['best_price']:
            return None

        # Calculate NO prices (approximation)
        poly_no_price = 1.0 - poly_yes['best_price']
        kalshi_yes_price = 100 - kalshi_no['best_price']

        # Find best arbitrage direction
        result = BidirectionalArbitrageCalculator.find_best_arbitrage(
            poly_yes_price=poly_yes['best_price'],
            poly_no_price=poly_no_price,
            kalshi_yes_price=kalshi_yes_price,
            kalshi_no_price=kalshi_no['best_price'],
            total_budget=budget,
            poly_yes_liquidity=poly_yes['liquidity'],
            poly_no_liquidity=poly_yes['liquidity'],  # Approximation
            kalshi_yes_liquidity=kalshi_no['liquidity'],  # Approximation
            kalshi_no_liquidity=kalshi_no['liquidity']
        )

        # Add market info
        result['market_name'] = pair.get('name', pair.get('poly_title', 'Unknown'))
        result['poly_id'] = pair['poly_id']
        result['kalshi_ticker'] = pair['kalshi_ticker']
        result['timestamp'] = datetime.now().isoformat()

        return result

    except Exception as e:
        print(f"Error scanning {pair.get('name', 'unknown')}: {e}")
        return None


def background_scanner(pairs: List[Dict], budget: float, auto_refresh: bool = True):
    """
    Background thread for continuous market scanning

    Args:
        pairs: List of market pairs to scan
        budget: Budget per opportunity
        auto_refresh: Whether to continuously refresh
    """
    global scan_results, scan_status

    while True:
        try:
            scan_status['scanning'] = True
            scan_status['error'] = None

            results = []
            for pair in pairs:
                result = scan_single_pair(pair, budget)
                if result:
                    results.append(result)
                time.sleep(1)  # Rate limiting

            # Update global state
            scan_results = sorted(results, key=lambda x: x['roi_percent'], reverse=True)
            scan_status['last_update'] = datetime.now().isoformat()
            scan_status['total_markets'] = len(results)
            scan_status['profitable_count'] = len([r for r in results if r['roi_percent'] > 0])
            scan_status['scanning'] = False

            if not auto_refresh:
                break

            # Wait before next scan
            time.sleep(30)

        except Exception as e:
            scan_status['error'] = str(e)
            scan_status['scanning'] = False
            break


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Get scan status"""
    return jsonify(scan_status)


@app.route('/api/opportunities')
def get_opportunities():
    """Get current arbitrage opportunities"""
    return jsonify({
        'opportunities': scan_results,
        'count': len(scan_results),
        'profitable': len([r for r in scan_results if r['roi_percent'] > 0])
    })


@app.route('/api/scan', methods=['POST'])
def start_scan():
    """Start a new scan"""
    global scan_results

    data = request.json
    budget = data.get('budget', 1000.0)
    use_discovered = data.get('use_discovered', False)

    try:
        # Load market pairs
        if use_discovered:
            with open('discovered_markets.json', 'r') as f:
                mapping = json.load(f)
        else:
            with open('market_mapping.json', 'r') as f:
                mapping = json.load(f)

        pairs = []
        for key, pair in mapping.items():
            pairs.append({
                'name': pair.get('name', key),
                'poly_id': pair.get('polymarket_token_id'),
                'kalshi_ticker': pair.get('kalshi_ticker')
            })

        # Start background scanner
        thread = threading.Thread(
            target=background_scanner,
            args=(pairs, budget, False),
            daemon=True
        )
        thread.start()

        return jsonify({'success': True, 'message': 'Scan started'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/discover', methods=['POST'])
def discover_markets():
    """Discover new market pairs"""
    data = request.json or {}
    max_markets = data.get('max_markets', 500)
    min_similarity = data.get('min_similarity', 0.35)
    min_liquidity = data.get('min_liquidity', 0)

    try:
        if not discovery_engine:
            return jsonify({'success': False, 'error': 'Discovery engine not initialized'})

        # Run discovery
        pairs = discovery_engine.discover_pairs(
            max_markets=max_markets,
            min_similarity=min_similarity,
            min_liquidity=min_liquidity,
            save_to_file='discovered_markets.json'
        )

        return jsonify({
            'success': True,
            'pairs_found': len(pairs),
            'pairs': pairs[:10]  # Return top 10
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    try:
        config = load_config('config.json')
        return jsonify({
            'budget': config.get('settings', {}).get('budget', 1000.0),
            'min_roi_threshold': config.get('settings', {}).get('min_roi_threshold', 1.0),
            'has_poly_credentials': bool(config.get('polymarket', {}).get('api_key')),
            'has_kalshi_credentials': bool(config.get('kalshi', {}).get('api_key_id'))
        })
    except Exception as e:
        return jsonify({'error': str(e)})


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Arbitrage Advisor Web Interface")
    print("="*60 + "\n")

    # Initialize clients
    success, message = initialize_clients()
    if success:
        print(f"✓ {message}")
    else:
        print(f"⚠ Warning: {message}")
        print("  Running in limited mode (manual prices only)\n")

    print("\n📊 Starting web server...")
    print("🌐 Open your browser to: http://localhost:8080\n")
    print("Press Ctrl+C to stop\n")

    app.run(debug=True, host='0.0.0.0', port=8080)
