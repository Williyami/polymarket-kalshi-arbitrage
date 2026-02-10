"""
Market Mapper and Live Terminal Dashboard
Maps Polymarket markets to Kalshi markets and displays arbitrage opportunities
"""

import json
import time
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich import box
from rich.text import Text

from arb_engine import ArbitrageCalculator
from api_client import PolymarketClient, KalshiClient, RateLimiter

console = Console()


class MarketMapper:
    """Maps Polymarket markets to Kalshi markets"""

    def __init__(self, mapping_file: str = "market_mapping.json"):
        """
        Initialize market mapper

        Args:
            mapping_file: Path to JSON file containing market mappings
        """
        self.mapping_file = mapping_file
        self.mappings = self.load_mappings()

    def load_mappings(self) -> Dict:
        """
        Load market mappings from JSON file

        Expected format:
        {
            "BTC-100k": {
                "name": "Bitcoin to reach $100k",
                "polymarket_token_id": "0x123...",
                "kalshi_ticker": "INXD-24DEC31-T4500",
                "description": "BTC >= $100,000 by Dec 31, 2024"
            }
        }

        Returns:
            Dictionary of market mappings
        """
        try:
            with open(self.mapping_file, 'r') as f:
                mappings = json.load(f)
                console.log(f"Loaded {len(mappings)} market mappings")
                return mappings
        except FileNotFoundError:
            console.log(f"[yellow]Mapping file not found: {self.mapping_file}[/yellow]")
            console.log("Creating example mapping file...")
            self.create_example_mapping()
            return self.load_mappings()
        except json.JSONDecodeError as e:
            console.log(f"[red]Error parsing mapping file: {e}[/red]")
            return {}

    def create_example_mapping(self):
        """Create an example mapping file"""
        example = {
            "BTC-100k": {
                "name": "Bitcoin to reach $100k",
                "polymarket_token_id": "EXAMPLE_TOKEN_ID_1",
                "kalshi_ticker": "EXAMPLE_TICKER_1",
                "description": "Example market mapping"
            },
            "ETH-5k": {
                "name": "Ethereum to reach $5k",
                "polymarket_token_id": "EXAMPLE_TOKEN_ID_2",
                "kalshi_ticker": "EXAMPLE_TICKER_2",
                "description": "Example market mapping"
            }
        }

        with open(self.mapping_file, 'w') as f:
            json.dump(example, f, indent=2)

        console.log(f"[green]Created example mapping file: {self.mapping_file}[/green]")
        console.log("Please edit this file with your actual market IDs")

    def get_all_pairs(self) -> List[Dict]:
        """
        Get all market pairs

        Returns:
            List of market pair dictionaries
        """
        pairs = []
        for key, mapping in self.mappings.items():
            pairs.append({
                'key': key,
                'name': mapping.get('name', key),
                'poly_token': mapping.get('polymarket_token_id'),
                'kalshi_ticker': mapping.get('kalshi_ticker'),
                'description': mapping.get('description', '')
            })
        return pairs

    def add_mapping(self, key: str, name: str, poly_token: str, kalshi_ticker: str, description: str = ""):
        """Add a new market mapping"""
        self.mappings[key] = {
            'name': name,
            'polymarket_token_id': poly_token,
            'kalshi_ticker': kalshi_ticker,
            'description': description
        }
        self.save_mappings()

    def save_mappings(self):
        """Save mappings to file"""
        with open(self.mapping_file, 'w') as f:
            json.dump(self.mappings, f, indent=2)


class ArbitrageDashboard:
    """Live terminal dashboard for arbitrage opportunities"""

    def __init__(self,
                 poly_client: PolymarketClient,
                 kalshi_client: KalshiClient,
                 market_mapper: MarketMapper,
                 budget: float = 1000.0,
                 min_roi_threshold: float = 1.0):
        """
        Initialize dashboard

        Args:
            poly_client: Polymarket API client
            kalshi_client: Kalshi API client
            market_mapper: Market mapper instance
            budget: Total budget for arbitrage
            min_roi_threshold: Minimum ROI % to trigger alert
        """
        self.poly_client = poly_client
        self.kalshi_client = kalshi_client
        self.market_mapper = market_mapper
        self.budget = budget
        self.min_roi_threshold = min_roi_threshold
        self.rate_limiter = RateLimiter(max_calls_per_second=2)
        self.opportunities = []
        self.last_update = None

    def fetch_opportunity(self, market_pair: Dict) -> Optional[Dict]:
        """
        Fetch and analyze a single arbitrage opportunity

        Args:
            market_pair: Market pair dictionary

        Returns:
            Opportunity dictionary or None if error
        """
        try:
            # Rate limit API calls
            self.rate_limiter.wait_if_needed()

            # Fetch Polymarket data
            poly_data = self.poly_client.get_best_yes_price_and_liquidity(
                market_pair['poly_token']
            )

            # Rate limit
            self.rate_limiter.wait_if_needed()

            # Fetch Kalshi data
            kalshi_data = self.kalshi_client.get_best_no_price_and_liquidity(
                market_pair['kalshi_ticker']
            )

            # Check if data is valid
            if poly_data['best_price'] is None or kalshi_data['best_price'] is None:
                return None

            # Calculate arbitrage
            result = ArbitrageCalculator.calculate_no_arbitrage_sizing(
                poly_yes_price=poly_data['best_price'],
                kalshi_no_price=kalshi_data['best_price'],
                total_budget=self.budget,
                poly_liquidity=poly_data['liquidity'],
                kalshi_liquidity=kalshi_data['liquidity']
            )

            # Add market info
            result['market_name'] = market_pair['name']
            result['market_key'] = market_pair['key']
            result['poly_price'] = poly_data['best_price']
            result['kalshi_price'] = kalshi_data['best_price']
            result['poly_liquidity'] = poly_data['liquidity']
            result['kalshi_liquidity'] = kalshi_data['liquidity']

            return result

        except Exception as e:
            console.log(f"[red]Error fetching {market_pair['name']}: {e}[/red]")
            return None

    def scan_all_markets(self):
        """Scan all mapped markets for opportunities"""
        self.opportunities = []
        pairs = self.market_mapper.get_all_pairs()

        for pair in pairs:
            opportunity = self.fetch_opportunity(pair)
            if opportunity:
                self.opportunities.append(opportunity)

        self.last_update = datetime.now()

    def create_table(self) -> Table:
        """Create Rich table with opportunities"""
        table = Table(
            title="🔍 Arbitrage Opportunities Scanner",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )

        # Add columns
        table.add_column("Market", style="cyan", no_wrap=True)
        table.add_column("Poly YES", justify="right", style="green")
        table.add_column("Kalshi NO", justify="right", style="blue")
        table.add_column("ROI %", justify="right", style="yellow")
        table.add_column("Poly Qty", justify="right")
        table.add_column("Kalshi Qty", justify="right")
        table.add_column("Capital", justify="right", style="white")
        table.add_column("Profit", justify="right", style="green")
        table.add_column("Status", justify="center")

        # Sort by ROI
        sorted_opps = sorted(
            self.opportunities,
            key=lambda x: x['roi_percent'],
            reverse=True
        )

        for opp in sorted_opps:
            # Determine status
            if opp['roi_percent'] >= self.min_roi_threshold:
                status = "🚨 ALERT"
                status_style = "bold red"
            elif opp['roi_percent'] > 0:
                status = "✓ Arb"
                status_style = "green"
            else:
                status = "✗ None"
                status_style = "dim"

            # Format ROI with color
            roi_str = f"{opp['roi_percent']:.2f}%"
            if opp['roi_percent'] >= self.min_roi_threshold:
                roi_style = "bold red"
            elif opp['roi_percent'] > 0:
                roi_style = "green"
            else:
                roi_style = "dim"

            table.add_row(
                opp['market_name'][:25],
                f"${opp['poly_price']:.3f}",
                f"{opp['kalshi_price']:.1f}¢",
                Text(roi_str, style=roi_style),
                str(opp['poly_quantity']),
                str(opp['kalshi_quantity']),
                f"${opp['total_cost']:.2f}",
                f"${opp['avg_profit']:.2f}",
                Text(status, style=status_style)
            )

        return table

    def create_alert_panel(self) -> Optional[Panel]:
        """Create alert panel for high-ROI opportunities"""
        alerts = [opp for opp in self.opportunities if opp['roi_percent'] >= self.min_roi_threshold]

        if not alerts:
            return None

        # Get best opportunity
        best = max(alerts, key=lambda x: x['roi_percent'])

        alert_text = f"""
[bold red]ARBITRAGE OPPORTUNITY DETECTED[/bold red]

Market: [cyan]{best['market_name']}[/cyan]
Net ROI: [bold green]{best['roi_percent']:.2f}%[/bold green]
Expected Profit: [green]${best['avg_profit']:.2f}[/green]

[bold yellow]SUGGESTED LIMIT ORDERS:[/bold yellow]

1. Polymarket: Buy [green]{best['poly_quantity']}[/green] YES contracts
   → Limit Price: [green]${best['poly_price']:.4f}[/green]
   → Total Cost: ${best['poly_cost']:.2f} + ${best['poly_fee']:.2f} fee

2. Kalshi: Buy [blue]{best['kalshi_quantity']}[/blue] NO contracts
   → Limit Price: [blue]{best['kalshi_price']:.1f}¢[/blue]
   → Total Cost: ${best['kalshi_cost']:.2f} + ${best['kalshi_fee']:.2f} fee

[bold]Total Capital Required:[/bold] ${best['total_cost']:.2f}
[bold]Profit if YES:[/bold] ${best['outcome_yes_profit']:.2f}
[bold]Profit if NO:[/bold] ${best['outcome_no_profit']:.2f}
"""

        return Panel(
            alert_text,
            border_style="bold red",
            title="🚨 ACTION REQUIRED 🚨",
            title_align="center"
        )

    def create_footer(self) -> Text:
        """Create footer with status info"""
        timestamp = self.last_update.strftime("%Y-%m-%d %H:%M:%S") if self.last_update else "Never"
        profitable_count = len([o for o in self.opportunities if o['roi_percent'] > 0])

        footer = Text()
        footer.append(f"Last Update: {timestamp} | ", style="dim")
        footer.append(f"Markets: {len(self.opportunities)} | ", style="cyan")
        footer.append(f"Profitable: {profitable_count} | ", style="green")
        footer.append(f"Budget: ${self.budget:.2f}", style="yellow")

        return footer

    def run_live_dashboard(self, refresh_seconds: int = 30):
        """
        Run live updating dashboard

        Args:
            refresh_seconds: Seconds between updates
        """
        console.print("\n[bold green]Starting Arbitrage Dashboard...[/bold green]\n")

        try:
            with Live(console=console, refresh_per_second=1) as live:
                while True:
                    # Scan markets
                    self.scan_all_markets()

                    # Create layout
                    layout = Layout()

                    # Add alert panel if needed
                    alert = self.create_alert_panel()
                    if alert:
                        layout.split_column(
                            Layout(alert, size=18),
                            Layout(self.create_table()),
                            Layout(self.create_footer(), size=1)
                        )
                    else:
                        layout.split_column(
                            Layout(self.create_table()),
                            Layout(self.create_footer(), size=1)
                        )

                    live.update(layout)

                    # Wait before next update
                    time.sleep(refresh_seconds)

        except KeyboardInterrupt:
            console.print("\n[yellow]Dashboard stopped by user[/yellow]")


if __name__ == "__main__":
    # Example usage
    console.print("[bold cyan]Arbitrage Advisor - Market Mapper & Dashboard[/bold cyan]\n")

    # Initialize components
    mapper = MarketMapper()
    poly_client = PolymarketClient()
    kalshi_client = KalshiClient()

    # Create dashboard
    dashboard = ArbitrageDashboard(
        poly_client=poly_client,
        kalshi_client=kalshi_client,
        market_mapper=mapper,
        budget=1000.0,
        min_roi_threshold=1.0
    )

    console.print("Dashboard initialized. Starting live monitoring...\n")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    # Run dashboard (this will fail without valid API setup, but shows structure)
    # dashboard.run_live_dashboard(refresh_seconds=30)

    console.print("[yellow]Note: Configure API clients and market mappings to run live dashboard[/yellow]")
