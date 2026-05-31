"""Five-step DuPont decomposition: ROE = Tax×Interest×OpMargin×AT×EM."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import DuPontFiveStep

if TYPE_CHECKING:
    from valueinvest.stock import Stock


def calculate_five_step(stock: Stock) -> DuPontFiveStep:
    """Calculate five-step DuPont decomposition.

    ROE = Tax Burden × Interest Burden × Operating Margin × Asset Turnover × Equity Multiplier
        = (NI/EBT) × (EBT/EBIT) × (EBIT/Revenue) × (Revenue/Assets) × (Assets/Equity)
    """
    revenue = stock.revenue
    net_income = stock.net_income
    ebit = stock.ebit
    total_assets = stock.total_assets
    equity = total_assets - stock.total_liabilities
    interest_expense = stock.interest_expense

    # Need EBIT for five-step; fall back gracefully
    if revenue <= 0 or total_assets <= 0 or equity <= 0:
        return _unavailable()

    if ebit <= 0:
        # Can't decompose meaningfully without positive EBIT
        return _unavailable()

    ebt = ebit - interest_expense  # Earnings Before Tax

    # Tax burden: Net Income / EBT
    if ebt <= 0:
        # Negative EBT means losses; tax burden not meaningful
        return _unavailable()
    tax_burden = net_income / ebt

    # Interest burden: EBT / EBIT
    interest_burden = ebt / ebit

    # Operating margin: EBIT / Revenue (%)
    operating_margin = ebit / revenue * 100

    # Asset turnover
    asset_turnover = revenue / total_assets

    # Equity multiplier
    equity_multiplier = total_assets / equity

    # Composed ROE
    roe_decomposed = tax_burden * interest_burden * operating_margin * asset_turnover * equity_multiplier

    return DuPontFiveStep(
        tax_burden=tax_burden,
        interest_burden=interest_burden,
        operating_margin=operating_margin,
        asset_turnover=asset_turnover,
        equity_multiplier=equity_multiplier,
        roe_decomposed=roe_decomposed,
        is_available=True,
    )


def _unavailable() -> DuPontFiveStep:
    return DuPontFiveStep(
        tax_burden=0.0,
        interest_burden=0.0,
        operating_margin=0.0,
        asset_turnover=0.0,
        equity_multiplier=0.0,
        roe_decomposed=0.0,
        is_available=False,
    )
