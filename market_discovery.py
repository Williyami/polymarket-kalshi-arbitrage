"""
Intelligent Market Pair Discovery
Automatically finds matching markets between Polymarket and Kalshi
Uses fuzzy matching and semantic analysis to pair similar markets
"""

import json
import logging
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
from datetime import datetime
import re

from api_client import PolymarketClient, KalshiClient, RateLimiter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketPairDiscovery:
    """Automatically discover matching market pairs"""

    def __init__(self, poly_client: PolymarketClient, kalshi_client: KalshiClient):
        """
        Initialize discovery engine

        Args:
            poly_client: Polymarket API client
            kalshi_client: Kalshi API client
        """
        self.poly_client = poly_client
        self.kalshi_client = kalshi_client
        self.rate_limiter = RateLimiter(max_calls_per_second=2)

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize market title for comparison

        Args:
            text: Raw market title

        Returns:
            Normalized lowercase text with standardized terms
        """
        if not text:
            return ""

        text = text.lower()

        # Remove special characters but keep spaces
        text = re.sub(r'[^\w\s]', ' ', text)

        # Standardize common terms
        replacements = {
            'bitcoin': 'btc',
            'ethereum': 'eth',
            'president': 'pres',
            'election': 'elect',
            'december': 'dec',
            'november': 'nov',
            'october': 'oct',
            'september': 'sep',
            'january': 'jan',
            'february': 'feb',
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        # Remove extra whitespace
        text = ' '.join(text.split())

        return text

    @staticmethod
    def extract_keywords(text: str) -> set:
        """
        Extract important keywords from market title

        Args:
            text: Market title

        Returns:
            Set of keywords
        """
        normalized = MarketPairDiscovery.normalize_text(text)

        # Remove common stop words
        stop_words = {'will', 'the', 'be', 'at', 'on', 'by', 'to', 'a', 'an',
                     'in', 'for', 'of', 'and', 'or', 'is', 'was', 'are'}

        words = set(normalized.split())
        keywords = words - stop_words

        return keywords

    @staticmethod
    def calculate_similarity(text1: str, text2: str) -> float:
        """
        Calculate similarity score between two market titles

        Args:
            text1: First market title
            text2: Second market title

        Returns:
            Similarity score (0-1)
        """
        # Normalize texts
        norm1 = MarketPairDiscovery.normalize_text(text1)
        norm2 = MarketPairDiscovery.normalize_text(text2)

        # Get keyword sets
        keywords1 = MarketPairDiscovery.extract_keywords(text1)
        keywords2 = MarketPairDiscovery.extract_keywords(text2)

        # Calculate Jaccard similarity for keywords
        if not keywords1 or not keywords2:
            keyword_similarity = 0
        else:
            intersection = len(keywords1 & keywords2)
            union = len(keywords1 | keywords2)
            keyword_similarity = intersection / union if union > 0 else 0

        # Calculate sequence similarity for full text
        sequence_similarity = SequenceMatcher(None, norm1, norm2).ratio()

        # Weighted combination (keywords are more important)
        final_similarity = (keyword_similarity * 0.7) + (sequence_similarity * 0.3)

        return final_similarity

    def fetch_polymarket_markets(self, limit: int = 100) -> List[Dict]:
        """
        Fetch active markets from Polymarket using the Gamma API,
        sorted by liquidity to get the most relevant current markets.

        Args:
            limit: Maximum number of active markets to collect

        Returns:
            List of market dictionaries
        """
        try:
            import requests
            logger.info("Fetching Polymarket markets...")
            active_markets = []
            offset = 0
            page_size = min(limit, 100)

            while len(active_markets) < limit:
                self.rate_limiter.wait_if_needed()
                resp = requests.get('https://gamma-api.polymarket.com/markets', params={
                    'active': 'true',
                    'closed': 'false',
                    'limit': page_size,
                    'offset': offset,
                    'order': 'liquidityClob',
                    'ascending': 'false',
                })
                if not resp.ok:
                    logger.error(f"Gamma API error: {resp.status_code}")
                    break

                markets = resp.json()
                if not markets:
                    break

                for market in markets:
                    title = market.get('question', '')
                    if not title:
                        continue
                    clob_ids = market.get('clobTokenIds', '').strip('[]').split(',')
                    token_id = clob_ids[0].strip().strip('"') if clob_ids else ''
                    active_markets.append({
                        'id': market.get('conditionId') or market.get('id'),
                        'title': title,
                        'liquidity': float(market.get('liquidityNum', 0) or 0),
                        'volume': float(market.get('volumeNum', 0) or 0),
                        'end_date': market.get('endDateIso'),
                        'tokens': [{'token_id': token_id}] if token_id else [],
                    })

                offset += page_size
                if len(markets) < page_size:
                    break

            active_markets = active_markets[:limit]
            logger.info(f"Found {len(active_markets)} active Polymarket markets")
            return active_markets

        except Exception as e:
            logger.error(f"Error fetching Polymarket markets: {e}")
            return []

    def fetch_kalshi_markets(self, limit: int = 100) -> List[Dict]:
        """
        Fetch active markets from Kalshi using the Events API with
        nested markets for meaningful titles and fast pagination.

        Args:
            limit: Maximum number of markets to fetch

        Returns:
            List of market dictionaries
        """
        try:
            import requests as req
            logger.info("Fetching Kalshi events and markets...")

            base_url = 'https://api.elections.kalshi.com/trade-api/v2'
            active_markets = []
            cursor = None
            page_size = min(limit, 200)

            while len(active_markets) < limit:
                self.rate_limiter.wait_if_needed()
                params = {
                    'limit': page_size,
                    'status': 'open',
                    'with_nested_markets': 'true',
                }
                if cursor:
                    params['cursor'] = cursor

                resp = req.get(f'{base_url}/events', params=params)
                if not resp.ok:
                    logger.warning(f"Kalshi API {resp.status_code}, stopping")
                    break

                data = resp.json()
                events = data.get('events', [])
                if not events:
                    break

                for event in events:
                    event_title = event.get('title', '')
                    for market in event.get('markets', []):
                        title = market.get('title') or event_title
                        active_markets.append({
                            'ticker': market.get('ticker', ''),
                            'title': title,
                            'event_title': event_title,
                            'liquidity': market.get('volume', 0) or 0,
                            'volume': market.get('volume', 0) or 0,
                            'expiration': market.get('expiration_time'),
                            'category': event.get('category', '')
                        })

                cursor = data.get('cursor')
                if not cursor:
                    break

            active_markets = active_markets[:limit]
            logger.info(f"Found {len(active_markets)} active Kalshi markets")
            return active_markets

        except Exception as e:
            logger.error(f"Error fetching Kalshi markets: {e}")
            return []

    def find_matching_pairs(self,
                          poly_markets: List[Dict],
                          kalshi_markets: List[Dict],
                          min_similarity: float = 0.6,
                          min_liquidity: float = 100.0) -> List[Dict]:
        """
        Find matching market pairs using fuzzy matching

        Args:
            poly_markets: List of Polymarket markets
            kalshi_markets: List of Kalshi markets
            min_similarity: Minimum similarity score (0-1)
            min_liquidity: Minimum liquidity on BOTH sides

        Returns:
            List of matched pair dictionaries
        """
        logger.info("Matching markets...")
        matched_pairs = []

        for poly in poly_markets:
            # Skip if insufficient liquidity
            if poly.get('liquidity', 0) < min_liquidity:
                continue

            best_match = None
            best_score = 0

            for kalshi in kalshi_markets:
                # Skip if insufficient liquidity
                if kalshi.get('liquidity', 0) < min_liquidity:
                    continue

                # Calculate similarity using best of title and event_title
                similarity = self.calculate_similarity(
                    poly['title'],
                    kalshi['title']
                )
                event_title = kalshi.get('event_title', '')
                if event_title:
                    event_sim = self.calculate_similarity(poly['title'], event_title)
                    similarity = max(similarity, event_sim)

                if similarity > best_score and similarity >= min_similarity:
                    best_score = similarity
                    best_match = kalshi

            if best_match:
                matched_pairs.append({
                    'poly_id': poly['id'],
                    'poly_title': poly['title'],
                    'poly_liquidity': poly['liquidity'],
                    'kalshi_ticker': best_match['ticker'],
                    'kalshi_title': best_match['title'],
                    'kalshi_liquidity': best_match['liquidity'],
                    'similarity_score': best_score,
                    'combined_liquidity': poly['liquidity'] + best_match['liquidity']
                })

        # Sort by similarity score and liquidity
        matched_pairs.sort(
            key=lambda x: (x['similarity_score'], x['combined_liquidity']),
            reverse=True
        )

        logger.info(f"Found {len(matched_pairs)} matching pairs")
        return matched_pairs

    def discover_pairs(self,
                      max_markets: int = 500,
                      min_similarity: float = 0.35,
                      min_liquidity: float = 0,
                      save_to_file: Optional[str] = None) -> List[Dict]:
        """
        Main discovery pipeline - fetch and match all markets

        Args:
            max_markets: Maximum markets to fetch from each platform
            min_similarity: Minimum similarity threshold
            min_liquidity: Minimum liquidity requirement
            save_to_file: Optional path to save discovered pairs

        Returns:
            List of discovered matching pairs
        """
        logger.info("Starting market pair discovery...")

        # Fetch markets from both platforms
        poly_markets = self.fetch_polymarket_markets(limit=max_markets)
        kalshi_markets = self.fetch_kalshi_markets(limit=max_markets)

        if not poly_markets or not kalshi_markets:
            logger.error("Failed to fetch markets from one or both platforms")
            return []

        # Find matching pairs
        pairs = self.find_matching_pairs(
            poly_markets,
            kalshi_markets,
            min_similarity=min_similarity,
            min_liquidity=min_liquidity
        )

        # Save to file if requested
        if save_to_file and pairs:
            self.save_pairs_to_mapping(pairs, save_to_file)

        return pairs

    def save_pairs_to_mapping(self, pairs: List[Dict], filepath: str = "discovered_markets.json"):
        """
        Save discovered pairs to market mapping format

        Args:
            pairs: List of discovered pairs
            filepath: Output file path
        """
        mapping = {}

        for i, pair in enumerate(pairs):
            key = f"auto_discovered_{i+1}"
            mapping[key] = {
                'name': pair['poly_title'][:60],  # Truncate long titles
                'polymarket_token_id': pair['poly_id'],
                'kalshi_ticker': pair['kalshi_ticker'],
                'description': f"Auto-discovered pair (similarity: {pair['similarity_score']:.2%})",
                'poly_liquidity': pair['poly_liquidity'],
                'kalshi_liquidity': pair['kalshi_liquidity'],
                'discovery_date': datetime.now().isoformat()
            }

        with open(filepath, 'w') as f:
            json.dump(mapping, f, indent=2)

        logger.info(f"Saved {len(pairs)} pairs to {filepath}")


if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()

    console.print("\n[bold cyan]Market Pair Discovery System[/bold cyan]\n")

    # Initialize clients (read-only mode for testing)
    try:
        poly_client = PolymarketClient()
        kalshi_client = KalshiClient()

        discovery = MarketPairDiscovery(poly_client, kalshi_client)

        console.print("[yellow]Discovering market pairs...[/yellow]\n")
        console.print("[dim]This may take 30-60 seconds...[/dim]\n")

        # Discover pairs
        pairs = discovery.discover_pairs(
            max_markets=50,
            min_similarity=0.6,
            min_liquidity=100.0,
            save_to_file="discovered_markets.json"
        )

        if pairs:
            # Display results
            table = Table(
                title="🔍 Discovered Market Pairs",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold cyan"
            )

            table.add_column("#", style="dim", width=4)
            table.add_column("Polymarket", style="green", width=30)
            table.add_column("Kalshi", style="blue", width=30)
            table.add_column("Match", justify="right", style="yellow")
            table.add_column("Liquidity", justify="right", style="magenta")

            for i, pair in enumerate(pairs[:20], 1):  # Show top 20
                table.add_row(
                    str(i),
                    pair['poly_title'][:28],
                    pair['kalshi_title'][:28],
                    f"{pair['similarity_score']:.0%}",
                    f"${pair['combined_liquidity']:,.0f}"
                )

            console.print(table)
            console.print(f"\n[green]✓ Saved {len(pairs)} pairs to discovered_markets.json[/green]")

        else:
            console.print("[red]No matching pairs found[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("\n[yellow]Note: This requires API access to work properly[/yellow]")
