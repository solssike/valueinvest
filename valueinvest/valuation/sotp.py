"""
Sum of the Parts (SOTP) Valuation.

Values a conglomerate by valuing each business segment independently
using appropriate multiples, then summing segment values to derive
total enterprise and equity value.

Formula:
    Total EV = Σ(Segment Value)
    Equity Value = Total EV - Net Debt - Minority Interest ± Holdco Discount
    Fair Value per Share = Equity Value / Shares Outstanding
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from .base import BaseValuation, ValuationResult, ValuationRange, FieldRequirement


@dataclass
class SOTPSegment:
    """A single business segment for SOTP valuation."""
    name: str
    revenue: float = 0.0
    ebitda: float = 0.0
    net_income: float = 0.0
    assets: float = 0.0
    valuation_method: str = "ev_ebitda"  # ev_ebitda, ev_revenue, pe, book_value
    multiple: float = 0.0
    net_debt: float = 0.0
    notes: str = ""

    def validate(self) -> List[str]:
        """Return list of issues with this segment's data."""
        issues = []
        if not self.name:
            issues.append("Segment name is empty")
        if self.multiple <= 0:
            issues.append(f"Segment '{self.name}': multiple must be positive")
        if self.valuation_method == "ev_ebitda" and self.ebitda <= 0:
            issues.append(f"Segment '{self.name}': EBITDA required for ev_ebitda method")
        if self.valuation_method == "ev_revenue" and self.revenue <= 0:
            issues.append(f"Segment '{self.name}': Revenue required for ev_revenue method")
        if self.valuation_method == "pe" and self.net_income <= 0:
            issues.append(f"Segment '{self.name}': Net income required for pe method")
        if self.valuation_method == "book_value" and self.assets <= 0:
            issues.append(f"Segment '{self.name}': Assets required for book_value method")
        return issues

    def calculate_value(self, multiple_adj: float = 0.0) -> float:
        """Calculate segment enterprise value with optional multiple adjustment."""
        m = self.multiple + multiple_adj
        if m <= 0:
            return 0.0

        if self.valuation_method == "ev_ebitda":
            return self.ebitda * m if self.ebitda > 0 else 0.0
        elif self.valuation_method == "ev_revenue":
            return self.revenue * m if self.revenue > 0 else 0.0
        elif self.valuation_method == "pe":
            return self.net_income * m if self.net_income > 0 else 0.0
        elif self.valuation_method == "book_value":
            return self.assets * m if self.assets > 0 else 0.0
        return 0.0


class SOTPValuation(BaseValuation):
    """
    Sum of the Parts (SOTP) / Break-up Valuation.

    Best for conglomerates, holding companies, and multi-segment
    corporations where aggregated valuation methods obscure the
    true value of individual businesses.
    """

    method_name = "SOTP (Sum of the Parts)"

    required_fields = [
        FieldRequirement("shares_outstanding", "Shares Outstanding", is_critical=True, min_value=0.01),
        FieldRequirement("current_price", "Current Stock Price", is_critical=True, min_value=0.01),
    ]

    best_for = [
        "Conglomerates (Berkshire, Samsung, Alibaba)",
        "Holding companies with diverse subsidiaries",
        "Multi-segment corporations (tech platforms, industrial groups)",
        "Companies with hidden or undervalued assets",
        "Spin-off / break-up analysis",
    ]
    not_for = [
        "Single-segment companies",
        "Companies without segment disclosure",
        "Early-stage startups with no segment history",
    ]

    DEFAULT_HOLDCO_DISCOUNT_PCT = 15.0

    def __init__(
        self,
        segments: Optional[List[SOTPSegment]] = None,
        holdco_discount_pct: Optional[float] = None,
        minority_interest: float = 0.0,
        unallocated_costs: float = 0.0,
    ):
        self.segments = segments
        self.holdco_discount_pct = (
            holdco_discount_pct
            if holdco_discount_pct is not None
            else self.DEFAULT_HOLDCO_DISCOUNT_PCT
        )
        self.minority_interest = minority_interest
        self.unallocated_costs = unallocated_costs

    def _get_segments(self, stock) -> List[SOTPSegment]:
        """Get segments from constructor or stock.extra."""
        if self.segments:
            return self.segments
        raw = stock.extra.get("sotp_segments", [])
        if not raw:
            return []
        result = []
        for s in raw:
            if isinstance(s, SOTPSegment):
                result.append(s)
            elif isinstance(s, dict):
                result.append(SOTPSegment(**s))
        return result

    def calculate(self, stock) -> ValuationResult:
        is_valid, missing, warnings = self.validate_data(stock)
        if not is_valid:
            return self._create_error_result(
                stock, f"Missing required data: {', '.join(missing)}", missing
            )

        segments = self._get_segments(stock)
        if not segments:
            return self._create_error_result(
                stock,
                "No segments provided. Pass segments via constructor or stock.extra['sotp_segments']",
                ["sotp_segments"],
            )

        # Validate all segments
        all_issues = []
        for seg in segments:
            all_issues.extend(seg.validate())
        if all_issues:
            return self._create_error_result(
                stock, f"Segment data issues: {'; '.join(all_issues)}", []
            )

        net_debt = stock.net_debt
        shares = stock.shares_outstanding

        # Calculate base case: sum of segment values
        segment_values = {}
        total_ev = 0.0
        for seg in segments:
            val = seg.calculate_value()
            segment_values[seg.name] = val
            total_ev += val

        # Apply segment-specific debt adjustments
        seg_debt_total = sum(seg.net_debt for seg in segments)
        corporate_debt = net_debt - seg_debt_total

        # Equity value = Total EV - corporate debt - minority interest - unallocated costs
        equity_value = (
            total_ev - corporate_debt - self.minority_interest - self.unallocated_costs
        )

        # Apply holdco discount
        holdco_discount = equity_value * (self.holdco_discount_pct / 100)
        equity_value_after_discount = equity_value - holdco_discount

        fair_price = (
            equity_value_after_discount / shares if shares > 0 else 0
        )

        if fair_price <= 0:
            return self._create_error_result(
                stock,
                f"Fair equity value is negative (Total EV: {total_ev/1e9:.2f}B, "
                f"Corp Debt: {corporate_debt/1e9:.2f}B, Holdco Discount: {holdco_discount/1e9:.2f}B)",
                [],
            )

        premium_discount = (
            ((fair_price - stock.current_price) / stock.current_price) * 100
        )

        # Sensitivity: low (max discount, lower multiples) and high (no discount, higher multiples)
        total_ev_low = sum(
            seg.calculate_value(multiple_adj=-seg.multiple * 0.15) for seg in segments
        )
        eq_low = (
            total_ev_low
            - corporate_debt
            - self.minority_interest
            - self.unallocated_costs
        )
        holdco_low = eq_low * (min(self.holdco_discount_pct + 5, 40) / 100)
        price_low = (eq_low - holdco_low) / shares if shares > 0 else 0

        total_ev_high = sum(
            seg.calculate_value(multiple_adj=seg.multiple * 0.15) for seg in segments
        )
        eq_high = (
            total_ev_high
            - corporate_debt
            - self.minority_interest
            - self.unallocated_costs
        )
        price_high = eq_high / shares if shares > 0 else 0

        # Build analysis notes
        segment_summaries = []
        for seg in segments:
            val = segment_values[seg.name]
            pct = (val / total_ev * 100) if total_ev > 0 else 0
            segment_summaries.append(
                f"{seg.name}: {val/1e9:.2f}B ({seg.valuation_method} @ {seg.multiple:.1f}x, {pct:.1f}%)"
            )

        analysis = [
            f"Total segments: {len(segments)}",
            f"Total EV (sum of parts): {total_ev/1e9:.2f}B",
        ]
        analysis.extend(segment_summaries)
        analysis.append(f"Corporate debt: {corporate_debt/1e9:.2f}B")
        if self.minority_interest > 0:
            analysis.append(f"Minority interest: {self.minority_interest/1e9:.2f}B")
        if self.unallocated_costs > 0:
            analysis.append(f"Unallocated costs: {self.unallocated_costs/1e9:.2f}B")
        analysis.append(
            f"Holdco discount: {self.holdco_discount_pct:.0f}% = {holdco_discount/1e9:.2f}B"
        )
        analysis.append(
            f"Equity value: {equity_value_after_discount/1e9:.2f}B → ${fair_price:.2f}/share"
        )

        if warnings:
            analysis.extend([f"Note: {w}" for w in warnings])

        confidence = (
            "High"
            if len(segments) >= 3 and all(seg.multiple > 0 for seg in segments)
            else ("Medium" if len(segments) >= 2 else "Low")
        )

        # Build details dict with per-segment breakdown
        details: Dict[str, Any] = {
            "total_enterprise_value": total_ev,
            "corporate_debt": corporate_debt,
            "minority_interest": self.minority_interest,
            "unallocated_costs": self.unallocated_costs,
            "holdco_discount_pct": self.holdco_discount_pct,
            "holdco_discount_value": holdco_discount,
            "equity_value": equity_value_after_discount,
        }
        for seg in segments:
            details[f"segment_{seg.name}_value"] = segment_values[seg.name]
            details[f"segment_{seg.name}_method"] = seg.valuation_method
            details[f"segment_{seg.name}_multiple"] = seg.multiple

        components = {f"segment_{seg.name}": segment_values[seg.name] for seg in segments}
        components["corporate_debt"] = corporate_debt
        components["holdco_discount"] = holdco_discount

        return ValuationResult(
            method=self.method_name,
            fair_value=round(fair_price, 2),
            current_price=stock.current_price,
            premium_discount=round(premium_discount, 1),
            assessment=self._assess(fair_price, stock.current_price),
            details=details,
            components=components,
            analysis=analysis,
            confidence=confidence,
            fair_value_range=ValuationRange(
                low=round(max(0, price_low), 2),
                base=round(fair_price, 2),
                high=round(price_high, 2),
            ),
            applicability="Applicable" if len(segments) >= 2 else "Limited",
        )
