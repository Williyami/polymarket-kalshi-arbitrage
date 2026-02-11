"""
API Client for Polymarket and Kalshi
Handles authentication, order book fetching, and volume calculations

Requirements:
    pip install py-clob-client kalshi-python requests
"""

import json
import time
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PolymarketClient:
    """Client for Polymarket API using py-clob-client"""

    def __init__(self, api_key: Optional[str] = None, private_key: Optional[str] = None):
        """
        Initialize Polymarket client

        Args:
            api_key: Polymarket API key (optional for read-only)
            private_key: Private key for signing (optional for read-only)
        """
        try:
            from py_clob_client.client import ClobClient

            # Always start with read-only client
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                chain_id=137  # Polygon mainnet
            )
            self.creds = None

            # Try to set up authenticated access if keys provided
            if api_key and private_key:
                try:
                    from py_clob_client.clob_types import ApiCreds
                    self.creds = ApiCreds(
                        api_key=api_key,
                        api_secret=private_key,
                        api_passphrase=""
                    )
                    self.client = ClobClient(
                        host="https://clob.polymarket.com",
                        key=api_key,
                        chain_id=137
                    )
                    logger.info("Polymarket client initialized with authentication")
                except Exception as e:
                    logger.warning(f"Polymarket auth failed ({e}), using read-only mode")
                    self.creds = None
            else:
                logger.info("Polymarket client initialized in read-only mode")

        except ImportError:
            logger.error("py-clob-client not installed. Run: pip install py-clob-client")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Polymarket client: {e}")
            raise

    def get_order_book(self, token_id: str, depth: int = 5) -> Dict:
        """
        Fetch order book for a specific token

        Args:
            token_id: Polymarket token ID (condition_id)
            depth: Number of price levels to fetch (default 5)

        Returns:
            Dictionary with bids and asks
        """
        try:
            # Fetch order book
            order_book = self.client.get_order_book(token_id)

            # Parse and structure data
            bids = []
            asks = []

            if 'bids' in order_book:
                for i, bid in enumerate(order_book['bids'][:depth]):
                    bids.append({
                        'price': Decimal(str(bid['price'])),
                        'size': int(bid['size']),
                        'level': i + 1
                    })

            if 'asks' in order_book:
                for i, ask in enumerate(order_book['asks'][:depth]):
                    asks.append({
                        'price': Decimal(str(ask['price'])),
                        'size': int(ask['size']),
                        'level': i + 1
                    })

            return {
                'token_id': token_id,
                'bids': bids,  # People buying YES
                'asks': asks,  # People selling YES
                'timestamp': time.time()
            }

        except Exception as e:
            logger.error(f"Failed to fetch Polymarket order book for {token_id}: {e}")
            return {'token_id': token_id, 'bids': [], 'asks': [], 'error': str(e)}

    def calculate_weighted_average_price(self,
                                        orders: List[Dict],
                                        desired_size: int) -> Tuple[Decimal, int]:
        """
        Calculate weighted average price for a given size

        Args:
            orders: List of order levels (bids or asks)
            desired_size: Number of contracts to buy/sell

        Returns:
            Tuple of (weighted_avg_price, actual_size_available)
        """
        if not orders:
            return Decimal('0'), 0

        total_cost = Decimal('0')
        total_size = 0

        for order in orders:
            price = order['price']
            size = order['size']

            # How much of this level can we fill?
            size_to_take = min(size, desired_size - total_size)

            total_cost += price * Decimal(size_to_take)
            total_size += size_to_take

            if total_size >= desired_size:
                break

        if total_size == 0:
            return Decimal('0'), 0

        weighted_avg = total_cost / Decimal(total_size)
        return weighted_avg, total_size

    def get_best_yes_price_and_liquidity(self, token_id: str, desired_size: int = None) -> Dict:
        """
        Get best YES price (from asks) and available liquidity

        Args:
            token_id: Polymarket token ID
            desired_size: Desired contract quantity (optional)

        Returns:
            Dictionary with price and liquidity info
        """
        order_book = self.get_order_book(token_id)

        if 'error' in order_book or not order_book.get('asks'):
            return {
                'best_price': None,
                'liquidity': 0,
                'weighted_avg_price': None,
                'available_size': 0,
                'error': order_book.get('error', 'No order book available')
            }

        best_price = order_book['asks'][0]['price']
        total_liquidity = sum(ask['size'] for ask in order_book['asks'])

        result = {
            'best_price': float(best_price),
            'liquidity': total_liquidity,
        }

        if desired_size:
            weighted_avg, available = self.calculate_weighted_average_price(
                order_book['asks'],
                desired_size
            )
            result['weighted_avg_price'] = float(weighted_avg) if weighted_avg else None
            result['available_size'] = available

        return result


class KalshiClient:
    """Client for Kalshi API using kalshi-python"""

    def __init__(self, email: Optional[str] = None, password: Optional[str] = None,
                 api_key_id: Optional[str] = None, private_key_path: Optional[str] = None):
        """
        Initialize Kalshi client

        Args:
            email: Deprecated, ignored (kept for config compat)
            password: Deprecated, ignored (kept for config compat)
            api_key_id: Kalshi API key ID (optional, for authenticated access)
            private_key_path: Path to RSA private key PEM file (optional, for authenticated access)
        """
        try:
            import kalshi_python

            config = kalshi_python.Configuration()
            config.host = 'https://api.elections.kalshi.com/trade-api/v2'

            if api_key_id and private_key_path:
                import os
                key_path = os.path.expanduser(private_key_path)
                with open(key_path, 'r') as f:
                    private_key_pem = f.read()
                config.api_key_id = api_key_id
                config.private_key_pem = private_key_pem
                self.client = kalshi_python.KalshiClient(configuration=config)
                logger.info("Kalshi client initialized with API key authentication")
            else:
                self.client = kalshi_python.ApiClient(configuration=config)
                logger.info("Kalshi client initialized in read-only mode")

            self.markets_api = kalshi_python.MarketsApi(self.client)

        except ImportError:
            logger.error("kalshi-python not installed. Run: pip install kalshi-python")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Kalshi client: {e}")
            raise

    def get_order_book(self, ticker: str, depth: int = 5) -> Dict:
        """
        Fetch order book for a specific market

        Args:
            ticker: Kalshi market ticker
            depth: Number of price levels to fetch

        Returns:
            Dictionary with bids and asks for YES and NO
        """
        try:
            response = self.markets_api.get_market_orderbook(ticker, depth=depth)
            orderbook = response.orderbook

            yes_bids = []
            yes_asks = []
            no_bids = []
            no_asks = []

            # Kalshi returns flat lists [price, quantity] as bids/asks
            # We need to convert these to proper YES/NO sides
            # In Kalshi: buying YES = yes_bid, selling YES = yes_ask
            #           buying NO = no_bid, selling NO = no_ask

            # Parse YES side if available
            if hasattr(orderbook, 'yes') and orderbook.yes:
                for i, level in enumerate(orderbook.yes[:depth]):
                    if isinstance(level, (list, tuple)) and len(level) >= 2:
                        price = Decimal(str(level[0])) / Decimal('100')  # Convert cents to dollars
                        size = int(level[1])
                        yes_bids.append({'price': price, 'size': size, 'level': i + 1})

            # Parse NO side if available
            if hasattr(orderbook, 'no') and orderbook.no:
                for i, level in enumerate(orderbook.no[:depth]):
                    if isinstance(level, (list, tuple)) and len(level) >= 2:
                        price = Decimal(str(level[0])) / Decimal('100')
                        size = int(level[1])
                        no_bids.append({'price': price, 'size': size, 'level': i + 1})

            return {
                'ticker': ticker,
                'yes_bids': yes_bids,
                'yes_asks': yes_asks,
                'no_bids': no_bids,
                'no_asks': no_asks,
                'timestamp': time.time()
            }

        except AttributeError as e:
            logger.warning(f"Kalshi order book structure issue for {ticker}: {e}. Market may not support order books.")
            return {
                'ticker': ticker,
                'yes_bids': [],
                'yes_asks': [],
                'no_bids': [],
                'no_asks': [],
                'error': f'Market does not support order books: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Failed to fetch Kalshi order book for {ticker}: {e}")
            return {
                'ticker': ticker,
                'yes_bids': [],
                'yes_asks': [],
                'no_bids': [],
                'no_asks': [],
                'error': str(e)
            }

    def calculate_weighted_average_price(self,
                                        orders: List[Dict],
                                        desired_size: int) -> Tuple[Decimal, int]:
        """
        Calculate weighted average price for a given size

        Args:
            orders: List of order levels (bids or asks)
            desired_size: Number of contracts to buy/sell

        Returns:
            Tuple of (weighted_avg_price, actual_size_available)
        """
        if not orders:
            return Decimal('0'), 0

        total_cost = Decimal('0')
        total_size = 0

        for order in orders:
            price = order['price']
            size = order['size']

            size_to_take = min(size, desired_size - total_size)

            total_cost += price * Decimal(size_to_take)
            total_size += size_to_take

            if total_size >= desired_size:
                break

        if total_size == 0:
            return Decimal('0'), 0

        weighted_avg = total_cost / Decimal(total_size)
        return weighted_avg, total_size

    def get_best_no_price_and_liquidity(self, ticker: str, desired_size: int = None) -> Dict:
        """
        Get best NO price (from bids) and available liquidity

        Args:
            ticker: Kalshi market ticker
            desired_size: Desired contract quantity (optional)

        Returns:
            Dictionary with price and liquidity info
        """
        order_book = self.get_order_book(ticker)

        if 'error' in order_book or not order_book.get('no_bids'):
            return {
                'best_price': None,
                'liquidity': 0,
                'weighted_avg_price': None,
                'available_size': 0,
                'error': order_book.get('error', 'No order book available')
            }

        # For buying NO, we look at NO bids (people selling NO to us)
        best_price = order_book['no_bids'][0]['price']
        total_liquidity = sum(bid['size'] for bid in order_book['no_bids'])

        result = {
            'best_price': float(best_price * Decimal('100')),  # Return in cents for consistency
            'liquidity': total_liquidity,
        }

        if desired_size:
            weighted_avg, available = self.calculate_weighted_average_price(
                order_book['no_bids'],
                desired_size
            )
            result['weighted_avg_price'] = float(weighted_avg * Decimal('100')) if weighted_avg else None
            result['available_size'] = available

        return result


class RateLimiter:
    """Simple rate limiter for API calls"""

    def __init__(self, max_calls_per_second: int = 2):
        """
        Initialize rate limiter

        Args:
            max_calls_per_second: Maximum API calls per second
        """
        self.max_calls = max_calls_per_second
        self.calls = []

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()

        # Remove calls older than 1 second
        self.calls = [call_time for call_time in self.calls if now - call_time < 1.0]

        # If at limit, wait
        if len(self.calls) >= self.max_calls:
            sleep_time = 1.0 - (now - self.calls[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
            self.calls = []

        self.calls.append(time.time())


# Example configuration template
def load_config(config_path: str = "config.json") -> Dict:
    """
    Load API credentials from config file

    Example config.json:
    {
        "polymarket": {
            "api_key": "your_api_key_here",
            "private_key": "your_private_key_here"
        },
        "kalshi": {
            "api_key_id": "your_api_key_id",
            "private_key_path": "~/path/to/kalshi_private_key.pem"
        }
    }

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Config file not found: {config_path}")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in config file: {config_path}")
        return {}


if __name__ == "__main__":
    print("=== API Client Test ===\n")

    # Test without authentication (read-only)
    print("Initializing clients in read-only mode...\n")

    try:
        poly_client = PolymarketClient()
        print("✓ Polymarket client ready")
    except Exception as e:
        print(f"✗ Polymarket client failed: {e}")

    try:
        kalshi_client = KalshiClient()
        print("✓ Kalshi client ready")
    except Exception as e:
        print(f"✗ Kalshi client failed: {e}")

    print("\nTo enable authenticated access:")
    print("1. Create a config.json file with your API credentials")
    print("2. Use load_config() to load credentials")
    print("3. Pass credentials to client constructors")
