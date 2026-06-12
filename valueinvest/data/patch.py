"""
Earnings Patch Module
=====================

Patch a Stock object with manually collected latest quarterly earnings data.

When API data (e.g. yfinance) lags behind actual earnings releases, this module
allows injecting verified quarterly data and computing up-to-date TTM (Trailing
Twelve Months) metrics.

Usage::

    from valueinvest.data.patch import EarningsPatch, QuarterlyEarnings, apply_earnings_patch

    patch = EarningsPatch(
        ticker="ADBE",
        source_description="SEC 10-Q filed June 11, 2026",
        quarters=[
            QuarterlyEarnings(
                quarter_label="Q2 FY2026",
                end_date="2026-05-31",
                revenue=5_871_000_000,
                net_income=1_833_000_000,
                eps=4.06,
                operating_cash_flow=2_280_000_000,
                capex=85_000_000,
                sbc=380_000_000,
                depreciation=150_000_000,
                ebit=2_560_000_000,
                ebitda=2_710_000_000,
            ),
        ],
    )
    result = apply_earnings_patch(stock, patch)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class QuarterlyEarnings:
    """Single quarter of earnings data."""

    quarter_label: str  # e.g. "Q2 FY2026"
    end_date: str  # e.g. "2026-05-31"
    revenue: float
    net_income: float
    eps: float = 0.0
    operating_cash_flow: float = 0.0
    capex: float = 0.0
    sbc: float = 0.0
    depreciation: float = 0.0
    ebit: float = 0.0
    ebitda: float = 0.0
    fcf: float = 0.0  # if available directly; else derived from OCF - capex


@dataclass
class EarningsPatch:
    """Patch specification: one or more quarters of verified earnings data."""

    ticker: str
    source_description: str  # e.g. "SEC 10-Q filed June 11, 2026"
    quarters: List[QuarterlyEarnings]
    fiscal_year_end_month: int = 12  # month (1-12) of fiscal year end


@dataclass
class PatchResult:
    """Result of applying an earnings patch."""

    patched_fields: Dict[str, Any] = field(default_factory=dict)
    ttm_breakdown: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


# Fields that can be patched on the Stock object, in priority order.
# "eps" is a special case — it uses sum of per-quarter EPS, not annual scaling.
_PATCHABLE_FIELDS = [
    "revenue",
    "net_income",
    "operating_cash_flow",
    "fcf",
    "capex",
    "sbc",
    "depreciation",
    "ebit",
    "ebitda",
]

# Mapping from patch fields to their per-quarter source fields in QuarterlyEarnings.
_QUARTER_FIELD_MAP = {
    "revenue": "revenue",
    "net_income": "net_income",
    "operating_cash_flow": "operating_cash_flow",
    "fcf": "fcf",
    "capex": "capex",
    "sbc": "sbc",
    "depreciation": "depreciation",
    "ebit": "ebit",
    "ebitda": "ebitda",
}


def _sum_quarter_field(quarters: List[QuarterlyEarnings], field_name: str) -> float:
    """Sum a field across all quarters."""
    qfield = _QUARTER_FIELD_MAP[field_name]
    return sum(getattr(q, qfield, 0.0) for q in quarters)


def _has_any_data(quarters: List[QuarterlyEarnings], field_name: str) -> bool:
    """Check if any quarter has non-zero data for this field."""
    qfield = _QUARTER_FIELD_MAP[field_name]
    return any(getattr(q, qfield, 0.0) != 0.0 for q in quarters)


def compute_ttm(
    quarters: List[QuarterlyEarnings],
    field_name: str,
    api_annual_value: float,
) -> float:
    """
    Compute TTM value for a field using patch quarters and API data.

    - If 4 quarters provided: TTM = sum of all 4 quarters
    - If N < 4 quarters: TTM = sum(patch quarters) + api_annual * (4 - N) / 4
    """
    n = len(quarters)
    patch_sum = _sum_quarter_field(quarters, field_name)

    if n >= 4:
        return patch_sum
    else:
        # Partial TTM: use API annual value for the remaining (4-N) quarters
        remaining = api_annual_value * (4 - n) / 4
        return patch_sum + remaining


def compute_ttm_eps(quarters: List[QuarterlyEarnings]) -> float:
    """
    Compute TTM EPS from per-quarter EPS values.

    EPS is a per-share metric, not an aggregate — we sum quarters directly,
    then scale by shares_outstanding is not needed.
    """
    return sum(q.eps for q in quarters)


def apply_earnings_patch(
    stock: Any,
    patch: EarningsPatch,
) -> PatchResult:
    """
    Apply an earnings patch to a Stock object.

    Computes TTM metrics from the patch quarters (using partial TTM formula
    when fewer than 4 quarters are provided) and updates Stock fields in-place.

    Provenance metadata is stored in ``stock.extra["earnings_patch"]`` and a
    warning is appended to ``stock.warnings``.

    Args:
        stock: A Stock dataclass instance.
        patch: An EarningsPatch with one or more quarters of verified data.

    Returns:
        PatchResult with details of what was patched and how TTM was calculated.
    """
    result = PatchResult()
    n = len(patch.quarters)

    if n == 0:
        result.warnings.append("No quarters in patch; nothing to apply.")
        return result

    # Compute TTM for each patchable field
    ttm_breakdown = {}
    patched_fields = {}

    for field_name in _PATCHABLE_FIELDS:
        if not _has_any_data(patch.quarters, field_name):
            continue  # Skip fields with no data in any quarter

        api_value = getattr(stock, field_name, 0.0)
        ttm_value = compute_ttm(patch.quarters, field_name, api_value)

        if ttm_value != api_value:
            patched_fields[field_name] = {
                "api_value": api_value,
                "patched_value": ttm_value,
                "formula": (
                    f"sum({n}Q) = {ttm_value:,.0f}"
                    if n >= 4
                    else f"sum({n}Q) + API_annual*{(4-n)}/4 = {ttm_value:,.0f}"
                ),
            }
            # Apply the patch
            setattr(stock, field_name, ttm_value)

        ttm_breakdown[field_name] = {
            "quarter_sum": _sum_quarter_field(patch.quarters, field_name),
            "api_annual": api_value,
            "n_quarters": n,
            "ttm": ttm_value,
        }

    # Special handling for EPS
    eps_sum = compute_ttm_eps(patch.quarters)
    api_eps = getattr(stock, "eps", 0.0)
    if eps_sum > 0 and n < 4:
        # Partial TTM for EPS
        ttm_eps = eps_sum + api_eps * (4 - n) / 4
    elif eps_sum > 0:
        ttm_eps = eps_sum
    else:
        ttm_eps = api_eps

    if ttm_eps != api_eps:
        patched_fields["eps"] = {
            "api_value": api_eps,
            "patched_value": ttm_eps,
            "formula": (
                f"sum({n}Q) = {ttm_eps:.2f}"
                if n >= 4
                else f"sum({n}Q) + API_eps*{(4-n)}/4 = {ttm_eps:.2f}"
            ),
        }
        stock.eps = ttm_eps

    ttm_breakdown["eps"] = {
        "quarter_sum": eps_sum,
        "api_annual": api_eps,
        "n_quarters": n,
        "ttm": ttm_eps,
    }

    # Recompute operating_margin from patched data
    if "revenue" in patched_fields or "ebit" in patched_fields:
        new_revenue = getattr(stock, "revenue", 0.0)
        new_ebit = getattr(stock, "ebit", 0.0)
        if new_revenue > 0:
            new_margin = new_ebit / new_revenue * 100
            old_margin = getattr(stock, "operating_margin", 0.0)
            patched_fields["operating_margin"] = {
                "api_value": old_margin,
                "patched_value": new_margin,
                "formula": f"ebit/revenue = {new_margin:.1f}%",
            }
            stock.operating_margin = new_margin

    # Derive FCF from OCF - capex if not directly provided in any quarter
    if "fcf" not in patched_fields and "operating_cash_flow" in patched_fields:
        stock.fcf = stock.operating_cash_flow - stock.capex
        patched_fields["fcf"] = {
            "api_value": ttm_breakdown.get("fcf", {}).get("api_annual", 0.0),
            "patched_value": stock.fcf,
            "formula": f"OCF - capex = {stock.operating_cash_flow:,.0f} - {stock.capex:,.0f}",
        }

    # Store provenance metadata
    stock.extra["earnings_patch"] = {
        "source": patch.source_description,
        "quarters": [q.quarter_label for q in patch.quarters],
        "end_dates": [q.end_date for q in patch.quarters],
        "patched_fields": list(patched_fields.keys()),
        "ttm_breakdown": ttm_breakdown,
        "patch_quarters_used": n,
    }

    stock.warnings.append(
        f"Earnings data patched with {n} quarter(s) from: {patch.source_description}"
    )

    result.patched_fields = patched_fields
    result.ttm_breakdown = ttm_breakdown
    if not patched_fields:
        result.warnings.append(
            "Patch provided but no fields were modified (values identical to API)."
        )

    return result


def load_patch_from_json(path: Union[str, Path]) -> EarningsPatch:
    """
    Load an EarningsPatch from a JSON file.

    JSON schema::

        {
            "ticker": "ADBE",
            "source_description": "SEC 10-Q filed June 11, 2026",
            "quarters": [
                {
                    "quarter_label": "Q2 FY2026",
                    "end_date": "2026-05-31",
                    "revenue": 5871000000,
                    "net_income": 1833000000,
                    "eps": 4.06,
                    "operating_cash_flow": 2280000000,
                    "capex": 85000000,
                    "sbc": 380000000,
                    "depreciation": 150000000,
                    "ebit": 2560000000,
                    "ebitda": 2710000000
                }
            ]
        }

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed EarningsPatch instance.
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    quarters = []
    for q in data.get("quarters", []):
        quarters.append(
            QuarterlyEarnings(
                quarter_label=q.get("quarter_label", ""),
                end_date=q.get("end_date", ""),
                revenue=q.get("revenue", 0.0),
                net_income=q.get("net_income", 0.0),
                eps=q.get("eps", 0.0),
                operating_cash_flow=q.get("operating_cash_flow", 0.0),
                capex=q.get("capex", 0.0),
                sbc=q.get("sbc", 0.0),
                depreciation=q.get("depreciation", 0.0),
                ebit=q.get("ebit", 0.0),
                ebitda=q.get("ebitda", 0.0),
                fcf=q.get("fcf", 0.0),
            )
        )

    return EarningsPatch(
        ticker=data.get("ticker", ""),
        source_description=data.get("source_description", ""),
        quarters=quarters,
        fiscal_year_end_month=data.get("fiscal_year_end_month", 12),
    )
