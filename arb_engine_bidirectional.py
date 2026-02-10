"""
Bidirectional Arbitrage Engine for Polymarket vs. Kalshi
Detects arbitrage in BOTH directions:
1. Buy Poly YES + Kalshi NO
2. Buy Poly NO + Kalshi YES

This module extends the original engine to find the best opportunity regardless of direction.
"""

from decimal import Decimal, ROUND_DOWN, getcontext
from typing import Tuple, Optional, Dict
import pandas as pd
from arb_engine import FeeCalculator

# Set high precision for financial calculations
getcontext().prec = 28


class BidirectionalArbitrageCalculator:
    """Calculate optimal sizing for arbitrage in both directions"""

    # Kalshi contract payout is fixed at $100
    KALSHI_PAYOUT_PER_CONTRACT = Decimal('100')
    # Polymarket contract payout is $1
    POLYMARKET_PAYOUT_PER_CONTRACT = Decimal('1')

    @classmethod
    def calculate_direction_1(cls,
                             poly_yes_price: Decimal,
                             kalshi_no_price: Decimal,
                             total_budget: Decimal,
                             poly_yes_liquidity: Optional[int] = None,
                             kalshi_no_liquidity: Optional[int] = None) -> dict:
        """
        Direction 1: Buy YES on Polymarket + NO on Kalshi
        Win if outcome = YES (Poly pays) OR NO (Kalshi pays)

        Args:
            poly_yes_price: Polymarket YES price (0-1)
            kalshi_no_price: Kalshi NO price (0-100 cents)
            total_budget: Total capital available
            poly_yes_liquidity: Available YES contracts on Polymarket
            kalshi_no_liquidity: Available NO contracts on Kalshi

        Returns:
            Dictionary with sizing and profit analysis
        """
        # Convert to Decimal
        poly_yes_price = Decimal(str(poly_yes_price))
        kalshi_no_price = Decimal(str(kalshi_no_price)) / Decimal('100')  # cents to dollars
        total_budget = Decimal(str(total_budget))

        # Hedge ratio: 1 Polymarket contract = 0.01 Kalshi contracts
        kalshi_qty_per_poly = cls.POLYMARKET_PAYOUT_PER_CONTRACT / cls.KALSHI_PAYOUT_PER_CONTRACT

        # Cost per unit before fees
        cost_per_unit = poly_yes_price + (kalshi_no_price * kalshi_qty_per_poly)

        # Initial sizing estimate
        initial_poly_qty = total_budget / cost_per_unit
        initial_kalshi_qty = initial_poly_qty * kalshi_qty_per_poly

        # Apply liquidity constraints
        if poly_yes_liquidity is not None:
            initial_poly_qty = min(initial_poly_qty, Decimal(str(poly_yes_liquidity)))
        if kalshi_no_liquidity is not None:
            initial_kalshi_qty = min(initial_kalshi_qty, Decimal(str(kalshi_no_liquidity)))
            initial_poly_qty = min(initial_poly_qty, initial_kalshi_qty / kalshi_qty_per_poly)

        # Iteratively refine with fees
        poly_qty = initial_poly_qty
        kalshi_qty = initial_kalshi_qty

        for _ in range(5):
            poly_cost = poly_qty * poly_yes_price
            kalshi_cost = kalshi_qty * kalshi_no_price
            kalshi_expected_payout = kalshi_qty * cls.KALSHI_PAYOUT_PER_CONTRACT

            poly_total_cost, kalshi_total_cost, total_fees = \
                FeeCalculator.calculate_total_cost_with_fees(
                    poly_cost, kalshi_cost, kalshi_expected_payout
                )

            total_cost = poly_total_cost + kalshi_total_cost

            if total_cost > total_budget:
                scale_factor = total_budget / total_cost
                poly_qty = poly_qty * scale_factor
                kalshi_qty = kalshi_qty * scale_factor
            else:
                break

        # Round to integer contracts
        poly_qty_final = int(poly_qty.quantize(Decimal('1'), rounding=ROUND_DOWN))
        kalshi_qty_final = int(kalshi_qty.quantize(Decimal('1'), rounding=ROUND_DOWN))

        # Final costs
        poly_cost_final = Decimal(poly_qty_final) * poly_yes_price
        kalshi_cost_final = Decimal(kalshi_qty_final) * kalshi_no_price
        kalshi_expected_payout_final = Decimal(kalshi_qty_final) * cls.KALSHI_PAYOUT_PER_CONTRACT

        poly_total_cost_final, kalshi_total_cost_final, total_fees_final = \
            FeeCalculator.calculate_total_cost_with_fees(
                poly_cost_final, kalshi_cost_final, kalshi_expected_payout_final
            )

        total_cost_final = poly_total_cost_final + kalshi_total_cost_final

        # Payouts
        poly_payout = Decimal(poly_qty_final) * cls.POLYMARKET_PAYOUT_PER_CONTRACT
        kalshi_payout = Decimal(kalshi_qty_final) * cls.KALSHI_PAYOUT_PER_CONTRACT

        outcome_yes_profit = poly_payout - total_cost_final
        outcome_no_profit = kalshi_payout - total_cost_final

        avg_profit = (outcome_yes_profit + outcome_no_profit) / Decimal('2')
        roi = (avg_profit / total_cost_final * Decimal('100')) if total_cost_final > 0 else Decimal('0')

        return {
            'direction': 'Poly YES + Kalshi NO',
            'poly_side': 'YES',
            'kalshi_side': 'NO',
            'poly_quantity': poly_qty_final,
            'kalshi_quantity': kalshi_qty_final,
            'poly_price': float(poly_yes_price),
            'kalshi_price': float(kalshi_no_price * Decimal('100')),  # back to cents
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
            'is_profitable': avg_profit > 0
        }

    @classmethod
    def calculate_direction_2(cls,
                             poly_no_price: Decimal,
                             kalshi_yes_price: Decimal,
                             total_budget: Decimal,
                             poly_no_liquidity: Optional[int] = None,
                             kalshi_yes_liquidity: Optional[int] = None) -> dict:
        """
        Direction 2: Buy NO on Polymarket + YES on Kalshi
        Win if outcome = NO (Poly pays) OR YES (Kalshi pays)

        Args:
            poly_no_price: Polymarket NO price (0-1)
            kalshi_yes_price: Kalshi YES price (0-100 cents)
            total_budget: Total capital available
            poly_no_liquidity: Available NO contracts on Polymarket
            kalshi_yes_liquidity: Available YES contracts on Kalshi

        Returns:
            Dictionary with sizing and profit analysis
        """
        # Convert to Decimal
        poly_no_price = Decimal(str(poly_no_price))
        kalshi_yes_price = Decimal(str(kalshi_yes_price)) / Decimal('100')  # cents to dollars
        total_budget = Decimal(str(total_budget))

        # Hedge ratio: 1 Polymarket contract = 0.01 Kalshi contracts
        kalshi_qty_per_poly = cls.POLYMARKET_PAYOUT_PER_CONTRACT / cls.KALSHI_PAYOUT_PER_CONTRACT

        # Cost per unit before fees
        cost_per_unit = poly_no_price + (kalshi_yes_price * kalshi_qty_per_poly)

        # Initial sizing estimate
        initial_poly_qty = total_budget / cost_per_unit
        initial_kalshi_qty = initial_poly_qty * kalshi_qty_per_poly

        # Apply liquidity constraints
        if poly_no_liquidity is not None:
            initial_poly_qty = min(initial_poly_qty, Decimal(str(poly_no_liquidity)))
        if kalshi_yes_liquidity is not None:
            initial_kalshi_qty = min(initial_kalshi_qty, Decimal(str(kalshi_yes_liquidity)))
            initial_poly_qty = min(initial_poly_qty, initial_kalshi_qty / kalshi_qty_per_poly)

        # Iteratively refine with fees
        poly_qty = initial_poly_qty
        kalshi_qty = initial_kalshi_qty

        for _ in range(5):
            poly_cost = poly_qty * poly_no_price
            kalshi_cost = kalshi_qty * kalshi_yes_price
            kalshi_expected_payout = kalshi_qty * cls.KALSHI_PAYOUT_PER_CONTRACT

            poly_total_cost, kalshi_total_cost, total_fees = \
                FeeCalculator.calculate_total_cost_with_fees(
                    poly_cost, kalshi_cost, kalshi_expected_payout
                )

            total_cost = poly_total_cost + kalshi_total_cost

            if total_cost > total_budget:
                scale_factor = total_budget / total_cost
                poly_qty = poly_qty * scale_factor
                kalshi_qty = kalshi_qty * scale_factor
            else:
                break

        # Round to integer contracts
        poly_qty_final = int(poly_qty.quantize(Decimal('1'), rounding=ROUND_DOWN))
        kalshi_qty_final = int(kalshi_qty.quantize(Decimal('1'), rounding=ROUND_DOWN))

        # Final costs
        poly_cost_final = Decimal(poly_qty_final) * poly_no_price
        kalshi_cost_final = Decimal(kalshi_qty_final) * kalshi_yes_price
        kalshi_expected_payout_final = Decimal(kalshi_qty_final) * cls.KALSHI_PAYOUT_PER_CONTRACT

        poly_total_cost_final, kalshi_total_cost_final, total_fees_final = \
            FeeCalculator.calculate_total_cost_with_fees(
                poly_cost_final, kalshi_cost_final, kalshi_expected_payout_final
            )

        total_cost_final = poly_total_cost_final + kalshi_total_cost_final

        # Payouts
        poly_payout = Decimal(poly_qty_final) * cls.POLYMARKET_PAYOUT_PER_CONTRACT
        kalshi_payout = Decimal(kalshi_qty_final) * cls.KALSHI_PAYOUT_PER_CONTRACT

        outcome_no_profit = poly_payout - total_cost_final  # NO wins = Poly pays
        outcome_yes_profit = kalshi_payout - total_cost_final  # YES wins = Kalshi pays

        avg_profit = (outcome_yes_profit + outcome_no_profit) / Decimal('2')
        roi = (avg_profit / total_cost_final * Decimal('100')) if total_cost_final > 0 else Decimal('0')

        return {
            'direction': 'Poly NO + Kalshi YES',
            'poly_side': 'NO',
            'kalshi_side': 'YES',
            'poly_quantity': poly_qty_final,
            'kalshi_quantity': kalshi_qty_final,
            'poly_price': float(poly_no_price),
            'kalshi_price': float(kalshi_yes_price * Decimal('100')),  # back to cents
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
            'is_profitable': avg_profit > 0
        }

    @classmethod
    def find_best_arbitrage(cls,
                           poly_yes_price: float,
                           poly_no_price: float,
                           kalshi_yes_price: float,
                           kalshi_no_price: float,
                           total_budget: float,
                           poly_yes_liquidity: Optional[int] = None,
                           poly_no_liquidity: Optional[int] = None,
                           kalshi_yes_liquidity: Optional[int] = None,
                           kalshi_no_liquidity: Optional[int] = None) -> Dict:
        """
        Evaluate BOTH directions and return the best arbitrage opportunity

        Args:
            poly_yes_price: Polymarket YES price (0-1)
            poly_no_price: Polymarket NO price (0-1)
            kalshi_yes_price: Kalshi YES price (0-100 cents)
            kalshi_no_price: Kalshi NO price (0-100 cents)
            total_budget: Total capital available
            poly_yes_liquidity: Available YES contracts on Polymarket
            poly_no_liquidity: Available NO contracts on Polymarket
            kalshi_yes_liquidity: Available YES contracts on Kalshi
            kalshi_no_liquidity: Available NO contracts on Kalshi

        Returns:
            Best arbitrage opportunity dictionary
        """
        # Calculate both directions
        dir1 = cls.calculate_direction_1(
            poly_yes_price,
            kalshi_no_price,
            total_budget,
            poly_yes_liquidity,
            kalshi_no_liquidity
        )

        dir2 = cls.calculate_direction_2(
            poly_no_price,
            kalshi_yes_price,
            total_budget,
            poly_no_liquidity,
            kalshi_yes_liquidity
        )

        # Return the better opportunity
        if dir1['roi_percent'] >= dir2['roi_percent']:
            return dir1
        else:
            return dir2

    @classmethod
    def analyze_both_directions(cls,
                               poly_yes_price: float,
                               poly_no_price: float,
                               kalshi_yes_price: float,
                               kalshi_no_price: float,
                               total_budget: float) -> pd.DataFrame:
        """
        Analyze and compare both arbitrage directions

        Returns:
            DataFrame comparing both opportunities
        """
        dir1 = cls.calculate_direction_1(poly_yes_price, kalshi_no_price, total_budget)
        dir2 = cls.calculate_direction_2(poly_no_price, kalshi_yes_price, total_budget)

        data = [{
            'Direction': dir1['direction'],
            'Poly Side': dir1['poly_side'],
            'Kalshi Side': dir1['kalshi_side'],
            'Poly Qty': dir1['poly_quantity'],
            'Kalshi Qty': dir1['kalshi_quantity'],
            'Total Cost': f"${dir1['total_cost']:.2f}",
            'Avg Profit': f"${dir1['avg_profit']:.2f}",
            'ROI %': f"{dir1['roi_percent']:.2f}%",
            'Profitable': '✓' if dir1['is_profitable'] else '✗'
        }, {
            'Direction': dir2['direction'],
            'Poly Side': dir2['poly_side'],
            'Kalshi Side': dir2['kalshi_side'],
            'Poly Qty': dir2['poly_quantity'],
            'Kalshi Qty': dir2['kalshi_quantity'],
            'Total Cost': f"${dir2['total_cost']:.2f}",
            'Avg Profit': f"${dir2['avg_profit']:.2f}",
            'ROI %': f"{dir2['roi_percent']:.2f}%",
            'Profitable': '✓' if dir2['is_profitable'] else '✗'
        }]

        return pd.DataFrame(data)


if __name__ == "__main__":
    print("=== Bidirectional Arbitrage Engine Test ===\n")

    # Example scenario
    poly_yes = 0.52
    poly_no = 0.49  # Note: Poly YES + NO may not equal 1.00 due to spread
    kalshi_yes = 54
    kalshi_no = 46
    budget = 1000.00

    print(f"Market Prices:")
    print(f"  Polymarket: YES=${poly_yes:.2f}, NO=${poly_no:.2f}")
    print(f"  Kalshi: YES={kalshi_yes}¢, NO={kalshi_no}¢")
    print(f"  Budget: ${budget:.2f}\n")

    # Analyze both directions
    comparison = BidirectionalArbitrageCalculator.analyze_both_directions(
        poly_yes_price=poly_yes,
        poly_no_price=poly_no,
        kalshi_yes_price=kalshi_yes,
        kalshi_no_price=kalshi_no,
        total_budget=budget
    )

    print("Direction Comparison:")
    print(comparison.to_string(index=False))

    print("\n" + "="*80)

    # Find best opportunity
    best = BidirectionalArbitrageCalculator.find_best_arbitrage(
        poly_yes_price=poly_yes,
        poly_no_price=poly_no,
        kalshi_yes_price=kalshi_yes,
        kalshi_no_price=kalshi_no,
        total_budget=budget
    )

    print(f"\nBest Opportunity: {best['direction']}")
    print(f"ROI: {best['roi_percent']:.2f}%")
    print(f"Expected Profit: ${best['avg_profit']:.2f}")
    print(f"\nAction:")
    print(f"  1. Buy {best['poly_quantity']} {best['poly_side']} on Polymarket @ ${best['poly_price']:.4f}")
    print(f"  2. Buy {best['kalshi_quantity']} {best['kalshi_side']} on Kalshi @ {best['kalshi_price']:.1f}¢")
