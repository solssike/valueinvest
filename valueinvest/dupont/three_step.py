"""Three-step DuPont decomposition: ROE = NPM × AT × EM."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import DuPontThreeStep

if TYPE_CHECKING:
    from valueinvest.stock import Stock


def calculate_three_step(stock: Stock) -> DuPontThreeStep:
    """Calculate three-step DuPont decomposition.

    ROE = Net Profit Margin × Asset Turnover × Equity Multiplier
        = (Net Income / Revenue) × (Revenue / Total Assets) × (Total Assets / Equity)
    """
    revenue = stock.revenue
    net_income = stock.net_income
    total_assets = stock.total_assets
    equity = total_assets - stock.total_liabilities

    if revenue <= 0 or total_assets <= 0 or equity <= 0:
        return DuPontThreeStep(
            net_profit_margin=0.0,
            asset_turnover=0.0,
            equity_multiplier=0.0,
            roe_decomposed=0.0,
            is_available=False,
        )

    net_profit_margin = net_income / revenue * 100
    asset_turnover = revenue / total_assets
    equity_multiplier = total_assets / equity
    roe_decomposed = net_profit_margin * asset_turnover * equity_multiplier

    return DuPontThreeStep(
        net_profit_margin=net_profit_margin,
        asset_turnover=asset_turnover,
        equity_multiplier=equity_multiplier,
        roe_decomposed=roe_decomposed,
        is_available=True,
    )
