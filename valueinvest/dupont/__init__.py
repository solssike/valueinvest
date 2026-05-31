"""DuPont ROE Decomposition Module.

Decomposes Return on Equity into driving factors:
- Three-step: ROE = Net Profit Margin × Asset Turnover × Equity Multiplier
- Five-step: ROE = Tax Burden × Interest Burden × Operating Margin × AT × EM
"""

from .base import DuPontDriver, DuPontFiveStep, DuPontResult, DuPontThreeStep
from .engine import DuPontAnalysisEngine


def analyze_dupont(stock, **kwargs):
    """Convenience function for DuPont ROE decomposition.

    Args:
        stock: Stock instance with financial data
        **kwargs: Reserved for future extensions

    Returns:
        DuPontResult with three-step, five-step decomposition and driver analysis
    """
    engine = DuPontAnalysisEngine()
    return engine.analyze(stock)


__all__ = [
    "DuPontThreeStep",
    "DuPontFiveStep",
    "DuPontDriver",
    "DuPontResult",
    "DuPontAnalysisEngine",
    "analyze_dupont",
]
