"""Base data classes for DuPont ROE decomposition analysis."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class DuPontThreeStep:
    """Three-step DuPont decomposition: ROE = NPM × AT × EM."""

    net_profit_margin: float  # Net Income / Revenue (%)
    asset_turnover: float  # Revenue / Total Assets (x)
    equity_multiplier: float  # Total Assets / Equity (x)
    roe_decomposed: float  # NPM × AT × EM (%)
    is_available: bool

    def to_summary(self) -> str:
        if not self.is_available:
            return "Three-step: data unavailable"
        lines = [
            f"  Net Profit Margin: {self.net_profit_margin:.2f}%",
            f"  Asset Turnover:    {self.asset_turnover:.3f}x",
            f"  Equity Multiplier: {self.equity_multiplier:.2f}x",
            f"  ROE (decomposed):  {self.roe_decomposed:.2f}%",
        ]
        return "\n".join(lines)


@dataclass
class DuPontFiveStep:
    """Five-step DuPont decomposition: ROE = Tax×Interest×OpMargin×AT×EM."""

    tax_burden: float  # Net Income / EBT (ratio, ≤1.0 means tax drag)
    interest_burden: float  # EBT / EBIT (ratio, ≤1.0 means interest drag)
    operating_margin: float  # EBIT / Revenue (%)
    asset_turnover: float  # Revenue / Total Assets (x)
    equity_multiplier: float  # Total Assets / Equity (x)
    roe_decomposed: float  # Product of five (%)
    is_available: bool

    def to_summary(self) -> str:
        if not self.is_available:
            return "Five-step: EBIT data unavailable"
        lines = [
            f"  Tax Burden:        {self.tax_burden:.3f}",
            f"  Interest Burden:   {self.interest_burden:.3f}",
            f"  Operating Margin:  {self.operating_margin:.2f}%",
            f"  Asset Turnover:    {self.asset_turnover:.3f}x",
            f"  Equity Multiplier: {self.equity_multiplier:.2f}x",
            f"  ROE (decomposed):  {self.roe_decomposed:.2f}%",
        ]
        return "\n".join(lines)


@dataclass
class DuPontDriver:
    """Identifies the dominant ROE driver and its quality."""

    primary_driver: str  # "Net Profit Margin", "Asset Turnover", "Leverage", "Balanced"
    driver_quality: str  # "Excellent", "Good", "Acceptable", "Poor", "Dangerous"
    leverage_dependency: bool  # True if equity_multiplier > 3.0
    description: str


@dataclass
class DuPontResult:
    """Complete DuPont analysis result."""

    ticker: str
    roe_reported: float  # From stock.roe
    three_step: DuPontThreeStep
    five_step: DuPontFiveStep
    driver: DuPontDriver
    analysis: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_summary(self) -> str:
        lines = [
            f"=== {self.ticker} DuPont Analysis ===",
            f"Reported ROE: {self.roe_reported:.2f}%",
            "",
            "Three-Step Decomposition:",
            self.three_step.to_summary(),
        ]
        if self.five_step.is_available:
            lines += [
                "",
                "Five-Step Decomposition:",
                self.five_step.to_summary(),
            ]
        lines += [
            "",
            f"Primary Driver: {self.driver.primary_driver} ({self.driver.driver_quality})",
            f"Leverage Dependency: {'Yes' if self.driver.leverage_dependency else 'No'}",
        ]
        if self.warnings:
            lines.append(f"Warnings: {'; '.join(self.warnings)}")
        return "\n".join(lines)

    def __str__(self) -> str:
        driver_str = f"{self.driver.primary_driver} ({self.driver.driver_quality})"
        parts = [
            f"{self.ticker}: ROE={self.roe_reported:.1f}%",
            f"Driver={driver_str}",
            f"Leverage={'High' if self.driver.leverage_dependency else 'Normal'}",
        ]
        if self.three_step.is_available:
            parts.append(
                f"NPM={self.three_step.net_profit_margin:.1f}% "
                f"AT={self.three_step.asset_turnover:.2f}x "
                f"EM={self.three_step.equity_multiplier:.1f}x"
            )
        return " | ".join(parts)
