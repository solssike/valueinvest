"""DuPont Analysis Engine: orchestrates ROE decomposition and driver analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from .base import DuPontDriver, DuPontResult
from .five_step import calculate_five_step
from .three_step import calculate_three_step

if TYPE_CHECKING:
    from valueinvest.stock import Stock


class DuPontAnalysisEngine:
    """Decomposes ROE into driving factors using DuPont analysis."""

    def analyze(self, stock: Stock) -> DuPontResult:
        """Run full DuPont analysis on a stock.

        Args:
            stock: Stock instance with financial data

        Returns:
            DuPontResult with three-step, five-step decomposition and driver analysis
        """
        three = calculate_three_step(stock)
        five = calculate_five_step(stock)
        driver = self._identify_driver(stock, three, five)
        analysis = self._build_analysis(stock, three, five, driver)
        warnings = self._collect_warnings(stock, three, five)

        return DuPontResult(
            ticker=stock.ticker,
            roe_reported=stock.roe,
            three_step=three,
            five_step=five,
            driver=driver,
            analysis=analysis,
            warnings=warnings,
        )

    def _identify_driver(
        self, stock: Stock, three: "DuPontThreeStep", five: "DuPontFiveStep"
    ) -> DuPontDriver:
        """Identify the primary ROE driver and classify quality."""
        if not three.is_available:
            return DuPontDriver(
                primary_driver="Unknown",
                driver_quality="Poor",
                leverage_dependency=False,
                description="Insufficient data for DuPont decomposition",
            )

        npm = three.net_profit_margin
        at = three.asset_turnover
        em = three.equity_multiplier

        # Leverage dependency
        leverage_dependency = em > 3.0

        # Identify primary driver by comparing contribution levels
        # Normalize to comparable scales for ranking
        npm_contrib = abs(npm) / 100  # already a %
        at_contrib = abs(at)  # typically 0.3-3.0
        em_contrib = abs(em - 1)  # excess above 1.0 = leverage

        # Weight by typical ranges to make them comparable
        npm_score = npm_contrib / 0.15  # 15% NPM = score 1.0
        at_score = at_contrib / 1.0  # 1.0x turnover = score 1.0
        em_score = em_contrib / 1.5  # EM of 2.5 = score 1.0

        scores = {
            "Net Profit Margin": npm_score,
            "Asset Turnover": at_score,
            "Leverage": em_score,
        }
        primary_driver = max(scores, key=scores.get)

        # If two factors are very close, call it "Balanced"
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[0] > 0:
            ratio = sorted_scores[1] / sorted_scores[0]
            if ratio > 0.8:
                primary_driver = "Balanced"

        # Classify driver quality
        driver_quality = self._classify_quality(stock, npm, at, em, primary_driver)

        # Build description
        desc = self._describe_driver(npm, at, em, primary_driver, driver_quality, leverage_dependency)

        return DuPontDriver(
            primary_driver=primary_driver,
            driver_quality=driver_quality,
            leverage_dependency=leverage_dependency,
            description=desc,
        )

    def _classify_quality(
        self,
        stock: Stock,
        npm: float,
        at: float,
        em: float,
        primary_driver: str,
    ) -> str:
        """Classify the quality of ROE composition."""
        # Leverage-driven ROE is dangerous
        if em > 4.0:
            return "Dangerous"
        if em > 3.0:
            return "Poor"

        # High NPM + reasonable leverage = excellent
        if npm > 20.0 and em < 2.5:
            return "Excellent"
        if npm > 20.0:
            return "Good"

        # Moderate NPM + asset efficiency
        if npm > 10.0 and at > 0.8 and em < 2.5:
            return "Good"
        if npm > 10.0 and em < 2.5:
            return "Acceptable"

        # Low NPM but high turnover (retail/ volume business)
        if npm < 5.0 and at > 1.5 and em < 2.0:
            return "Good"

        # Low NPM with leverage
        if npm < 5.0 and em > 2.5:
            return "Poor"

        # Moderate NPM with leverage
        if em > 2.5:
            return "Acceptable"

        return "Acceptable"

    def _describe_driver(
        self,
        npm: float,
        at: float,
        em: float,
        primary_driver: str,
        quality: str,
        leverage_dep: bool,
    ) -> str:
        """Build human-readable driver description."""
        parts = []
        if primary_driver == "Net Profit Margin":
            parts.append(f"ROE primarily driven by profitability (NPM={npm:.1f}%)")
        elif primary_driver == "Asset Turnover":
            parts.append(f"ROE primarily driven by asset efficiency (AT={at:.2f}x)")
        elif primary_driver == "Leverage":
            parts.append(f"ROE primarily driven by financial leverage (EM={em:.1f}x)")
        else:
            parts.append("ROE driven by a balanced mix of profitability, efficiency, and leverage")

        if leverage_dep:
            parts.append("high leverage dependency is a risk factor")

        if quality in ("Poor", "Dangerous"):
            parts.append("ROE quality is concerning due to leverage or low profitability")

        return "; ".join(parts).capitalize() + "."

    def _build_analysis(
        self,
        stock: Stock,
        three: "DuPontThreeStep",
        five: "DuPontFiveStep",
        driver: DuPontDriver,
    ) -> List[str]:
        """Build analysis text lines."""
        lines = []

        if not three.is_available:
            lines.append(f"{stock.ticker}: insufficient data for DuPont decomposition")
            return lines

        # Three-step analysis
        lines.append(
            f"ROE = {three.net_profit_margin:.1f}% (NPM) × "
            f"{three.asset_turnover:.2f}x (AT) × "
            f"{three.equity_multiplier:.1f}x (EM) = "
            f"{three.roe_decomposed:.1f}%"
        )

        # Decomposition insight
        if three.equity_multiplier > 3.0:
            lines.append(
                f"High equity multiplier ({three.equity_multiplier:.1f}x) indicates "
                f"significant leverage — ROE is amplified by debt"
            )
        elif three.equity_multiplier < 1.5:
            lines.append(
                f"Low equity multiplier ({three.equity_multiplier:.1f}x) indicates "
                f"conservative capital structure"
            )

        if three.net_profit_margin < 5.0:
            lines.append(
                f"Low net profit margin ({three.net_profit_margin:.1f}%) suggests "
                f"pricing pressure or high cost structure"
            )
        elif three.net_profit_margin > 20.0:
            lines.append(
                f"Strong net profit margin ({three.net_profit_margin:.1f}%) indicates "
                f"pricing power or cost advantages"
            )

        if three.asset_turnover < 0.5:
            lines.append(
                f"Low asset turnover ({three.asset_turnover:.2f}x) suggests "
                f"capital-intensive business or underutilized assets"
            )
        elif three.asset_turnover > 2.0:
            lines.append(
                f"High asset turnover ({three.asset_turnover:.2f}x) indicates "
                f"efficient asset utilization"
            )

        # Five-step analysis
        if five.is_available:
            tax_drag = (1 - five.tax_burden) * 100
            interest_drag = (1 - five.interest_burden) * 100

            if tax_drag > 30:
                lines.append(f"High tax drag ({tax_drag:.0f}%) reduces ROE significantly")
            if interest_drag > 20:
                lines.append(
                    f"Significant interest burden ({interest_drag:.0f}%) — "
                    f"debt servicing consumes a large share of operating income"
                )
            elif interest_drag < 5:
                lines.append(f"Minimal interest burden ({interest_drag:.0f}%) — low debt cost")

        return lines

    def _collect_warnings(
        self,
        stock: Stock,
        three: "DuPontThreeStep",
        five: "DuPontFiveStep",
    ) -> List[str]:
        """Collect data quality and analysis warnings."""
        warnings = []

        if not three.is_available:
            warnings.append("Three-step decomposition unavailable: missing revenue, assets, or equity data")
            return warnings

        # Check decomposition vs reported ROE
        if stock.roe > 0 and abs(three.roe_decomposed - stock.roe) / stock.roe > 0.15:
            warnings.append(
                f"Decomposed ROE ({three.roe_decomposed:.1f}%) differs from "
                f"reported ROE ({stock.roe:.1f}%) by >15% — may use different averaging periods"
            )

        if not five.is_available:
            warnings.append("Five-step decomposition unavailable: EBIT data missing or non-positive")

        if three.equity_multiplier > 4.0:
            warnings.append(
                f"Very high equity multiplier ({three.equity_multiplier:.1f}x) — "
                f"ROE is heavily dependent on leverage and is fragile to earnings decline"
            )

        if three.net_profit_margin < 0:
            warnings.append("Negative net profit margin — company is currently loss-making")

        if three.equity_multiplier < 0:
            warnings.append("Negative equity — company has negative book value, DuPont analysis may not be meaningful")

        return warnings
