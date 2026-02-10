#!/usr/bin/env python3
"""
Polymarket vs. Kalshi Arbitrage Advisor
Main entry point for scanning and displaying arbitrage opportunities

This is a READ-ONLY advisor that does NOT execute trades.
It only displays recommended positions for manual review.
"""

import argparse
import json
import sys
from typing import Dict, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from arb_engine_bidirectional import BidirectionalArbitrageCalculator
from api_client import PolymarketClient, KalshiClient, load_config
from market_mapper import MarketMapper

console = Console()


def display_opportunity(result: Dict, market_name: str):
    """
    Display a single arbitrage opportunity in a beautiful format

    Args:
        result: Result dictionary from BidirectionalArbitrageCalculator
        market_name: Name of the market
    """
    if not result['is_profitable']:
        console.print(f"[dim]No profitable arbitrage found for {market_name}[/dim]\n")
        return

    # Create detailed output
    table = Table(
        title=f"🎯 Arbitrage Opportunity: {market_name}",
        box=box.DOUBLE_EDGE,
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Metric", style="yellow", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Strategy", result['direction'])
    table.add_row("Net ROI", f"{result['roi_percent']:.2f}%")
    table.add_row("Expected Profit", f"${result['avg_profit']:.2f}")
    table.add_row("", "")  # Spacer

    table.add_row("[bold]Polymarket Position[/bold]", "")
    table.add_row("  Side", result['poly_side'])
    table.add_row("  Quantity", str(result['poly_quantity']))
    table.add_row("  Price", f"${result['poly_price']:.4f}")
    table.add_row("  Cost", f"${result['poly_cost']:.2f}")
    table.add_row("  Fee", f"${result['poly_fee']:.2f}")
    table.add_row("", "")  # Spacer

    table.add_row("[bold]Kalshi Position[/bold]", "")
    table.add_row("  Side", result['kalshi_side'])
    table.add_row("  Quantity", str(result['kalshi_quantity']))
    table.add_row("  Price", f"{result['kalshi_price']:.1f}¢")
    table.add_row("  Cost", f"${result['kalshi_cost']:.2f}")
    table.add_row("  Fee", f"${result['kalshi_fee']:.2f}")
    table.add_row("", "")  # Spacer

    table.add_row("[bold]Total Investment[/bold]", f"[bold]${result['total_cost']:.2f}[/bold]")
    table.add_row("Total Fees", f"${result['total_fees']:.2f}")
    table.add_row("", "")  # Spacer

    table.add_row("Profit if YES", f"${result['outcome_yes_profit']:.2f}")
    table.add_row("Profit if NO", f"${result['outcome_no_profit']:.2f}")

    console.print(table)

    # Create action panel
    if result['roi_percent'] >= 1.0:
        action_text = f"""
[bold yellow]RECOMMENDED LIMIT ORDERS:[/bold yellow]

1. [bold cyan]Polymarket[/bold cyan]
   → Buy {result['poly_quantity']} {result['poly_side']} contracts
   → Limit Price: ${result['poly_price']:.4f}
   → Total: ${result['poly_cost']:.2f} + ${result['poly_fee']:.2f} fee

2. [bold cyan]Kalshi[/bold cyan]
   → Buy {result['kalshi_quantity']} {result['kalshi_side']} contracts
   → Limit Price: {result['kalshi_price']:.1f}¢
   → Total: ${result['kalshi_cost']:.2f} + ${result['kalshi_fee']:.2f} fee

[bold red]⚠ IMPORTANT:[/bold red] Use LIMIT orders only, not market orders!
This ensures you get the exact prices calculated above.
"""
        console.print(Panel(
            action_text,
            border_style="bold green",
            title="📋 Manual Execution Instructions",
            title_align="left"
        ))

    console.print()


def scan_single_market(poly_yes: float,
                      poly_no: float,
                      kalshi_yes: float,
                      kalshi_no: float,
                      budget: float,
                      market_name: str = "Manual Entry"):
    """
    Scan a single market pair and display results

    Args:
        poly_yes: Polymarket YES price (0-1)
        poly_no: Polymarket NO price (0-1)
        kalshi_yes: Kalshi YES price (0-100 cents)
        kalshi_no: Kalshi NO price (0-100 cents)
        budget: Total capital available
        market_name: Name of the market
    """
    console.print(f"\n[bold cyan]Analyzing: {market_name}[/bold cyan]")
    console.print(f"Polymarket: YES=${poly_yes:.3f}, NO=${poly_no:.3f}")
    console.print(f"Kalshi: YES={kalshi_yes:.1f}¢, NO={kalshi_no:.1f}¢")
    console.print(f"Budget: ${budget:.2f}\n")

    # Find best opportunity
    result = BidirectionalArbitrageCalculator.find_best_arbitrage(
        poly_yes_price=poly_yes,
        poly_no_price=poly_no,
        kalshi_yes_price=kalshi_yes,
        kalshi_no_price=kalshi_no,
        total_budget=budget
    )

    display_opportunity(result, market_name)


def scan_all_markets(config_path: str = "config.json",
                    mapping_path: str = "market_mapping.json"):
    """
    Scan all markets in mapping file using API clients

    Args:
        config_path: Path to config file with API credentials
        mapping_path: Path to market mapping file
    """
    # Load config
    config = load_config(config_path)
    if not config:
        console.print("[red]Error: Could not load config file[/red]")
        console.print("Create config.json with your API credentials")
        return

    budget = config.get('settings', {}).get('budget', 1000.0)

    # Initialize clients
    try:
        poly_config = config.get('polymarket', {})
        poly_client = PolymarketClient(
            api_key=poly_config.get('api_key'),
            private_key=poly_config.get('private_key')
        )

        kalshi_config = config.get('kalshi', {})
        kalshi_client = KalshiClient(
            email=kalshi_config.get('email'),
            password=kalshi_config.get('password')
        )

        console.print("[green]✓ API clients initialized[/green]\n")

    except Exception as e:
        console.print(f"[red]Error initializing API clients: {e}[/red]")
        return

    # Load market mappings
    mapper = MarketMapper(mapping_path)
    pairs = mapper.get_all_pairs()

    if not pairs:
        console.print("[yellow]No market pairs found in mapping file[/yellow]")
        return

    console.print(f"[cyan]Scanning {len(pairs)} market pairs...[/cyan]\n")

    # Scan each pair
    opportunities = []

    for pair in pairs:
        try:
            # Fetch Polymarket data
            poly_data_yes = poly_client.get_best_yes_price_and_liquidity(pair['poly_token'])
            poly_data_no = poly_client.get_best_yes_price_and_liquidity(pair['poly_token'])

            # Fetch Kalshi data
            kalshi_data_yes = kalshi_client.get_best_no_price_and_liquidity(pair['kalshi_ticker'])
            kalshi_data_no = kalshi_client.get_best_no_price_and_liquidity(pair['kalshi_ticker'])

            if not all([
                poly_data_yes['best_price'],
                poly_data_no['best_price'],
                kalshi_data_yes['best_price'],
                kalshi_data_no['best_price']
            ]):
                console.print(f"[yellow]Skipping {pair['name']}: Missing price data[/yellow]")
                continue

            # Calculate arbitrage
            result = BidirectionalArbitrageCalculator.find_best_arbitrage(
                poly_yes_price=poly_data_yes['best_price'],
                poly_no_price=1.0 - poly_data_yes['best_price'],  # Approximation
                kalshi_yes_price=100 - kalshi_data_no['best_price'],  # Approximation
                kalshi_no_price=kalshi_data_no['best_price'],
                total_budget=budget
            )

            result['market_name'] = pair['name']
            opportunities.append(result)

            display_opportunity(result, pair['name'])

        except Exception as e:
            console.print(f"[red]Error scanning {pair['name']}: {e}[/red]")
            continue

    # Summary
    console.print("\n" + "="*80)
    console.print("[bold cyan]Scan Complete[/bold cyan]")
    console.print(f"Total markets scanned: {len(opportunities)}")
    profitable = [o for o in opportunities if o['is_profitable']]
    console.print(f"Profitable opportunities: {len(profitable)}")

    if profitable:
        best = max(profitable, key=lambda x: x['roi_percent'])
        console.print(f"\n[bold green]Best Opportunity:[/bold green]")
        console.print(f"  {best['market_name']}")
        console.print(f"  ROI: {best['roi_percent']:.2f}%")
        console.print(f"  Profit: ${best['avg_profit']:.2f}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Polymarket vs. Kalshi Arbitrage Advisor (READ-ONLY)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan a single market with manual prices
  python arbitrage_advisor.py --manual \\
    --poly-yes 0.52 --poly-no 0.49 \\
    --kalshi-yes 54 --kalshi-no 46 \\
    --budget 1000

  # Scan all markets using API
  python arbitrage_advisor.py --scan-all

  # Use custom config and mapping files
  python arbitrage_advisor.py --scan-all \\
    --config my_config.json \\
    --mapping my_markets.json
        """
    )

    parser.add_argument(
        '--manual',
        action='store_true',
        help='Manual mode: enter prices directly'
    )

    parser.add_argument(
        '--scan-all',
        action='store_true',
        help='Scan all markets from mapping file using API'
    )

    parser.add_argument(
        '--poly-yes',
        type=float,
        help='Polymarket YES price (0-1)'
    )

    parser.add_argument(
        '--poly-no',
        type=float,
        help='Polymarket NO price (0-1)'
    )

    parser.add_argument(
        '--kalshi-yes',
        type=float,
        help='Kalshi YES price (0-100 cents)'
    )

    parser.add_argument(
        '--kalshi-no',
        type=float,
        help='Kalshi NO price (0-100 cents)'
    )

    parser.add_argument(
        '--budget',
        type=float,
        default=1000.0,
        help='Total budget (default: 1000.0)'
    )

    parser.add_argument(
        '--market-name',
        type=str,
        default='Manual Entry',
        help='Name of the market'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config.json',
        help='Path to config file (default: config.json)'
    )

    parser.add_argument(
        '--mapping',
        type=str,
        default='market_mapping.json',
        help='Path to market mapping file (default: market_mapping.json)'
    )

    args = parser.parse_args()

    # Display header
    console.print()
    console.print(Panel.fit(
        "[bold cyan]Polymarket vs. Kalshi Arbitrage Advisor[/bold cyan]\n"
        "[dim]Risk-Neutral Synthetic Arbitrage Scanner[/dim]\n"
        "[yellow]⚠ READ-ONLY: Does not execute trades[/yellow]",
        border_style="cyan"
    ))

    if args.manual:
        # Manual mode
        if not all([args.poly_yes, args.poly_no, args.kalshi_yes, args.kalshi_no]):
            console.print("[red]Error: Manual mode requires all price arguments[/red]")
            parser.print_help()
            sys.exit(1)

        scan_single_market(
            poly_yes=args.poly_yes,
            poly_no=args.poly_no,
            kalshi_yes=args.kalshi_yes,
            kalshi_no=args.kalshi_no,
            budget=args.budget,
            market_name=args.market_name
        )

    elif args.scan_all:
        # API mode
        scan_all_markets(
            config_path=args.config,
            mapping_path=args.mapping
        )

    else:
        console.print("[yellow]Please specify --manual or --scan-all[/yellow]")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
