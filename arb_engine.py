"""
Arbitrage Engine for Polymarket vs. Kalshi
Risk-Neutral Synthetic Arbitrage with 100% hedge

This module provides the core mathematical functions for calculating
arbitrage opportunities between Polymarket and Kalshi prediction markets.
"""

from decimal import Decimal, ROUND_DOWN, getcontext
from typing import Tuple, Optional
import pandas as pd

# Set high precision for financial calculations
getcontext().prec = 28


class FeeCalculator:
    """Calculate platform-specific fees for Polymarket and Kalshi"""

    # Polymarket constants
    POLYMARKET_TAKER_FEE_RATE = Decimal('0.001')  # 0.1%

    # Kalshi fee tiers (based on expected payout)
    KALSHI_FEE_TIERS = [
        (Decimal('0'), Decimal('7')),      # $0-$7: flat $1
        (Decimal('7'), Decimal('25')),     # $7-$25: 14%
        (Decimal('25'), Decimal('100')),   # $25-$100: 10%
        (Decimal('100'), Decimal('1000')), # $100-$1000: 7%
        (Decimal('1000'), None)            # $1000+: 5%
    ]

    KALSHI_FEE_RATES = {
        0: (Decimal('1'), None),           # Flat $1
        1: (None, Decimal('0.14')),        # 14%
        2: (None, Decimal('0.10')),        # 10%
        3: (None, Decimal('0.07')),        # 7%
        4: (None, Decimal('0.05'))         # 5%
    }

    @classmethod
    def calculate_polymarket_fee(cls, cost: Decimal) -> Decimal:
        """
        Calculate Polymarket taker fee

        Args:
            cost: Total cost of contracts (price * quantity)

        Returns:
            Fee amount in dollars
        """
        return cost * cls.POLYMARKET_TAKER_FEE_RATE

    @classmethod
    def calculate_kalshi_fee(cls, expected_payout: Decimal) -> Decimal:
        """
        Calculate Kalshi fee based on expected payout

        Args:
            expected_payout: Expected payout amount ($100 per contract)

        Returns:
            Fee amount in dollars
        """
        # Determine fee tier
        tier = 0
        for i, (lower, upper) in enumerate(cls.KALSHI_FEE_TIERS):
            if upper is None:
                tier = i
                break
            if lower <= expected_payout < upper:
                tier = i
                break

        # Calculate fee
        flat_fee, percentage_fee = cls.KALSHI_FEE_RATES[tier]

        if flat_fee is not None:
            return flat_fee
        else:
            return expected_payout * percentage_fee

    @classmethod
    def calculate_total_cost_with_fees(cls,
                                       poly_cost: Decimal,
                                       kalshi_cost: Decimal,
                                       kalshi_expected_payout: Decimal) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate total costs including all fees

        Args:
            poly_cost: Cost of Polymarket contracts (before fees)
            kalshi_cost: Cost of Kalshi contracts (before fees)
            kalshi_expected_payout: Expected payout from Kalshi position

        Returns:
            Tuple of (poly_total_cost, kalshi_total_cost, total_fees)
        """
        poly_fee = cls.calculate_polymarket_fee(poly_cost)
        kalshi_fee = cls.calculate_kalshi_fee(kalshi_expected_payout)

        poly_total = poly_cost + poly_fee
        kalshi_total = kalshi_cost + kalshi_fee
        total_fees = poly_fee + kalshi_fee

        return poly_total, kalshi_total, total_fees


class ArbitrageCalculator:
    """Calculate optimal sizing for risk-neutral arbitrage opportunities"""

    # Kalshi contract payout is fixed at $100
    KALSHI_PAYOUT_PER_CONTRACT = Decimal('100')
    # Polymarket contract payout is $1
    POLYMARKET_PAYOUT_PER_CONTRACT = Decimal('1')

    @classmethod
    def calculate_no_arbitrage_sizing(cls,
                                     poly_yes_price: Decimal,
                                     kalshi_no_price: Decimal,
                                     total_budget: Decimal,
                                     poly_liquidity: Optional[int] = None,
                                     kalshi_liquidity: Optional[int] = None) -> dict:
        """
        Calculate exact contract quantities for perfectly hedged arbitrage

        Strategy: Buy YES on Polymarket, buy NO on Kalshi
        Goal: Same profit regardless of outcome

        Args:
            poly_yes_price: Price per YES contract on Polymarket (0-1)
            kalshi_no_price: Price per NO contract on Kalshi (0-100 cents)
            total_budget: Total capital available for the trade
            poly_liquidity: Maximum contracts available on Polymarket
            kalshi_liquidity: Maximum contracts available on Kalshi

        Returns:
            Dictionary containing sizing, costs, and profit analysis
        """
        # Convert to Decimal for precision
        poly_yes_price = Decimal(str(poly_yes_price))
        kalshi_no_price = Decimal(str(kalshi_no_price))
        total_budget = Decimal(str(total_budget))

        # Convert Kalshi price from cents to dollars
        kalshi_no_price_dollars = kalshi_no_price / Decimal('100')

        # Calculate cost per 1 Polymarket contract + equivalent Kalshi contracts
        # For perfect hedge: Poly payout ($1) = Kalshi payout ($100 * qty)
        # Therefore: kalshi_qty = 1/100 per 1 Polymarket contract
        kalshi_qty_per_poly = cls.POLYMARKET_PAYOUT_PER_CONTRACT / cls.KALSHI_PAYOUT_PER_CONTRACT

        # Cost for 1 Polymarket + equivalent Kalshi (before fees)
        cost_per_unit = poly_yes_price + (kalshi_no_price_dollars * kalshi_qty_per_poly)

        # Initial sizing estimate (will refine with fees)
        initial_poly_qty = total_budget / cost_per_unit
        initial_kalshi_qty = initial_poly_qty * kalshi_qty_per_poly

        # Apply liquidity constraints
        if poly_liquidity is not None:
            initial_poly_qty = min(initial_poly_qty, Decimal(str(poly_liquidity)))

        if kalshi_liquidity is not None:
            initial_kalshi_qty = min(initial_kalshi_qty, Decimal(str(kalshi_liquidity)))
            # Recalculate poly quantity to maintain hedge ratio
            initial_poly_qty = min(initial_poly_qty, initial_kalshi_qty / kalshi_qty_per_poly)

        # Iteratively refine sizing to account for fees
        poly_qty = initial_poly_qty
        kalshi_qty = initial_kalshi_qty

        for _ in range(5):  # Converges quickly
            # Calculate costs
            poly_cost = poly_qty * poly_yes_price
            kalshi_cost = kalshi_qty * kalshi_no_price_dollars
            kalshi_expected_payout = kalshi_qty * cls.KALSHI_PAYOUT_PER_CONTRACT

            # Calculate fees
            poly_total_cost, kalshi_total_cost, total_fees = \
                FeeCalculator.calculate_total_cost_with_fees(
                    poly_cost, kalshi_cost, kalshi_expected_payout
                )

            total_cost = poly_total_cost + kalshi_total_cost

            # Adjust if over budget
            if total_cost > total_budget:
                scale_factor = total_budget / total_cost
                poly_qty = poly_qty * scale_factor
                kalshi_qty = kalshi_qty * scale_factor
            else:
                break

        # Round down to integer contracts
        poly_qty_final = int(poly_qty.quantize(Decimal('1'), rounding=ROUND_DOWN))
        kalshi_qty_final = int(kalshi_qty.quantize(Decimal('1'), rounding=ROUND_DOWN))

        # Recalculate with final quantities
        poly_cost_final = Decimal(poly_qty_final) * poly_yes_price
        kalshi_cost_final = Decimal(kalshi_qty_final) * kalshi_no_price_dollars
        kalshi_expected_payout_final = Decimal(kalshi_qty_final) * cls.KALSHI_PAYOUT_PER_CONTRACT

        poly_total_cost_final, kalshi_total_cost_final, total_fees_final = \
            FeeCalculator.calculate_total_cost_with_fees(
                poly_cost_final, kalshi_cost_final, kalshi_expected_payout_final
            )

        total_cost_final = poly_total_cost_final + kalshi_total_cost_final

        # Calculate payouts for both outcomes
        # Outcome 1: YES wins (Poly pays, Kalshi loses)
        poly_payout = Decimal(poly_qty_final) * cls.POLYMARKET_PAYOUT_PER_CONTRACT
        outcome_yes_profit = poly_payout - total_cost_final

        # Outcome 2: NO wins (Poly loses, Kalshi pays)
        kalshi_payout = Decimal(kalshi_qty_final) * cls.KALSHI_PAYOUT_PER_CONTRACT
        outcome_no_profit = kalshi_payout - total_cost_final

        # Calculate net profit (should be similar for both outcomes)
        avg_profit = (outcome_yes_profit + outcome_no_profit) / Decimal('2')
        roi = (avg_profit / total_cost_final * Decimal('100')) if total_cost_final > 0 else Decimal('0')

        # Check if arbitrage exists
        is_profitable = avg_profit > 0

        # Calculate hedge quality (how close outcomes are)
        hedge_imbalance = abs(outcome_yes_profit - outcome_no_profit)
        hedge_quality = Decimal('100') - (hedge_imbalance / avg_profit * Decimal('100')) if avg_profit > 0 else Decimal('0')

        return {
            'poly_quantity': poly_qty_final,
            'kalshi_quantity': kalshi_qty_final,
            'poly_cost': float(poly_cost_final),
            'kalshi_cost': float(kalshi_cost_final),
            'poly_fee': float(FeeCalculator.calculate_polymarket_fee(poly_cost_final)),
            'kalshi_fee': float(FeeCalculator.calculate_kalshi_fee(kalshi_expected_payout_final)),
            'total_cost': float(total_cost_final),
            'total_fees': float(total_fees_final),
            'outcome_yes_profit': float(outcome_yes_profit),
            'outcome_no_profit': float(outcome_no_profit),
            'avg_profit': float(avg_profit),
            'roi_percent': float(roi),
            'is_profitable': is_profitable,
            'hedge_quality_percent': float(hedge_quality),
            'capital_used': float(total_cost_final),
            'capital_remaining': float(total_budget - total_cost_final)
        }

    @classmethod
    def analyze_opportunity(cls,
                          poly_yes_price: float,
                          kalshi_no_price: float,
                          total_budget: float,
                          poly_liquidity: Optional[int] = None,
                          kalshi_liquidity: Optional[int] = None) -> pd.DataFrame:
        """
        Analyze an arbitrage opportunity and return formatted results

        Args:
            poly_yes_price: Price per YES contract on Polymarket (0-1)
            kalshi_no_price: Price per NO contract on Kalshi (0-100 cents)
            total_budget: Total capital available
            poly_liquidity: Maximum contracts available on Polymarket
            kalshi_liquidity: Maximum contracts available on Kalshi

        Returns:
            pandas DataFrame with analysis results
        """
        result = cls.calculate_no_arbitrage_sizing(
            poly_yes_price,
            kalshi_no_price,
            total_budget,
            poly_liquidity,
            kalshi_liquidity
        )

        df = pd.DataFrame([{
            'Metric': 'Position Sizing',
            'Polymarket': f"{result['poly_quantity']} contracts",
            'Kalshi': f"{result['kalshi_quantity']} contracts"
        }, {
            'Metric': 'Entry Cost',
            'Polymarket': f"${result['poly_cost']:.2f}",
            'Kalshi': f"${result['kalshi_cost']:.2f}"
        }, {
            'Metric': 'Platform Fees',
            'Polymarket': f"${result['poly_fee']:.2f}",
            'Kalshi': f"${result['kalshi_fee']:.2f}"
        }, {
            'Metric': 'Total Investment',
            'Polymarket': f"${result['total_cost']:.2f}",
            'Kalshi': ''
        }, {
            'Metric': 'Profit if YES',
            'Polymarket': f"${result['outcome_yes_profit']:.2f}",
            'Kalshi': ''
        }, {
            'Metric': 'Profit if NO',
            'Polymarket': f"${result['outcome_no_profit']:.2f}",
            'Kalshi': ''
        }, {
            'Metric': 'Net ROI',
            'Polymarket': f"{result['roi_percent']:.2f}%",
            'Kalshi': ''
        }, {
            'Metric': 'Hedge Quality',
            'Polymarket': f"{result['hedge_quality_percent']:.1f}%",
            'Kalshi': ''
        }])

        return df


if __name__ == "__main__":
    # Example usage
    print("=== Arbitrage Engine Test ===\n")

    # Test scenario
    poly_yes = 0.52  # 52 cents
    kalshi_no = 46   # 46 cents
    budget = 1000.00

    print(f"Scenario:")
    print(f"  Polymarket YES: ${poly_yes}")
    print(f"  Kalshi NO: {kalshi_no}¢")
    print(f"  Budget: ${budget}\n")

    result = ArbitrageCalculator.analyze_opportunity(
        poly_yes_price=poly_yes,
        kalshi_no_price=kalshi_no,
        total_budget=budget,
        poly_liquidity=5000,
        kalshi_liquidity=50
    )

    print(result.to_string(index=False))
