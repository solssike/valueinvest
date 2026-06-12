"""Tests for valueinvest.data.patch module."""

import json
import os
import tempfile

import pytest

from valueinvest.data.patch import (
    EarningsPatch,
    PatchResult,
    QuarterlyEarnings,
    apply_earnings_patch,
    compute_ttm,
    compute_ttm_eps,
    load_patch_from_json,
)
from valueinvest.stock import Stock


def _make_stock(
    revenue=20_000_000_000,
    net_income=5_000_000_000,
    eps=10.0,
    fcf=4_000_000_000,
    operating_cash_flow=6_000_000_000,
    capex=2_000_000_000,
    sbc=1_000_000_000,
    depreciation=1_200_000_000,
    ebit=7_000_000_000,
    ebitda=8_200_000_000,
    operating_margin=35.0,
    **kwargs,
) -> Stock:
    return Stock(
        ticker="TEST",
        current_price=100.0,
        shares_outstanding=500_000_000,
        revenue=revenue,
        net_income=net_income,
        eps=eps,
        fcf=fcf,
        operating_cash_flow=operating_cash_flow,
        capex=capex,
        sbc=sbc,
        depreciation=depreciation,
        ebit=ebit,
        ebitda=ebitda,
        operating_margin=operating_margin,
        **kwargs,
    )


class TestComputeTtm:
    """Test TTM computation logic."""

    def test_full_4_quarters(self):
        """With 4 quarters, TTM = sum of all quarters."""
        q1 = QuarterlyEarnings("Q1", "2025-03-31", revenue=5_000_000_000, net_income=1_200_000_000)
        q2 = QuarterlyEarnings("Q2", "2025-06-30", revenue=5_200_000_000, net_income=1_300_000_000)
        q3 = QuarterlyEarnings("Q3", "2025-09-30", revenue=4_800_000_000, net_income=1_100_000_000)
        q4 = QuarterlyEarnings("Q4", "2025-12-31", revenue=5_500_000_000, net_income=1_400_000_000)

        ttm = compute_ttm([q1, q2, q3, q4], "revenue", 20_000_000_000)
        assert ttm == 20_500_000_000

    def test_partial_1_quarter(self):
        """With 1 quarter, TTM = Q_new + API * 3/4."""
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000)
        ttm = compute_ttm([q1], "revenue", 20_000_000_000)
        expected = 5_500_000_000 + 20_000_000_000 * 3 / 4
        assert ttm == expected

    def test_partial_2_quarters(self):
        """With 2 quarters, TTM = Q1_new + Q2_new + API * 2/4."""
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000)
        q2 = QuarterlyEarnings("Q2 FY2026", "2026-03-31", revenue=5_800_000_000, net_income=1_600_000_000)
        ttm = compute_ttm([q1, q2], "revenue", 20_000_000_000)
        expected = 5_500_000_000 + 5_800_000_000 + 20_000_000_000 * 2 / 4
        assert ttm == expected


class TestComputeTtmEps:
    """Test TTM EPS computation."""

    def test_full_4_quarters(self):
        q1 = QuarterlyEarnings("Q1", "2025-03-31", revenue=1, net_income=1, eps=2.50)
        q2 = QuarterlyEarnings("Q2", "2025-06-30", revenue=1, net_income=1, eps=2.75)
        q3 = QuarterlyEarnings("Q3", "2025-09-30", revenue=1, net_income=1, eps=2.60)
        q4 = QuarterlyEarnings("Q4", "2025-12-31", revenue=1, net_income=1, eps=2.90)
        assert compute_ttm_eps([q1, q2, q3, q4]) == pytest.approx(10.75)

    def test_partial_quarters(self):
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=1, net_income=1, eps=3.00)
        assert compute_ttm_eps([q1]) == pytest.approx(3.00)


class TestApplyEarningsPatch:
    """Test the main apply_earnings_patch function."""

    def test_full_4_quarter_patch(self):
        """Full 4Q patch replaces all values."""
        stock = _make_stock()
        q1 = QuarterlyEarnings("Q1", "2025-03-31", revenue=5_000_000_000, net_income=1_200_000_000, eps=2.40)
        q2 = QuarterlyEarnings("Q2", "2025-06-30", revenue=5_200_000_000, net_income=1_300_000_000, eps=2.60)
        q3 = QuarterlyEarnings("Q3", "2025-09-30", revenue=4_800_000_000, net_income=1_100_000_000, eps=2.20)
        q4 = QuarterlyEarnings("Q4", "2025-12-31", revenue=5_500_000_000, net_income=1_400_000_000, eps=2.80)

        patch = EarningsPatch(
            ticker="TEST",
            source_description="SEC 10-K",
            quarters=[q1, q2, q3, q4],
        )
        result = apply_earnings_patch(stock, patch)

        assert stock.revenue == 20_500_000_000
        assert stock.net_income == 5_000_000_000
        assert stock.eps == pytest.approx(10.0)
        assert len(result.patched_fields) > 0

    def test_partial_1_quarter_patch(self):
        """1Q partial patch uses partial TTM formula."""
        stock = _make_stock(revenue=20_000_000_000, eps=10.0)
        q1 = QuarterlyEarnings(
            "Q2 FY2026",
            "2026-05-31",
            revenue=5_871_000_000,
            net_income=1_833_000_000,
            eps=4.06,
        )

        patch = EarningsPatch(
            ticker="TEST",
            source_description="SEC 10-Q",
            quarters=[q1],
        )
        result = apply_earnings_patch(stock, patch)

        # revenue TTM = 5.871B + 20B * 3/4 = 5.871B + 15B = 20.871B
        assert stock.revenue == pytest.approx(20_871_000_000)
        # eps TTM = 4.06 + 10.0 * 3/4 = 4.06 + 7.5 = 11.56
        assert stock.eps == pytest.approx(11.56)

    def test_partial_2_quarter_patch(self):
        """2Q partial patch."""
        stock = _make_stock(revenue=20_000_000_000, eps=10.0)
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-11-30", revenue=5_500_000_000, net_income=1_500_000_000, eps=3.00)
        q2 = QuarterlyEarnings("Q2 FY2026", "2026-02-28", revenue=5_800_000_000, net_income=1_600_000_000, eps=3.20)

        patch = EarningsPatch(
            ticker="TEST",
            source_description="SEC 10-Q",
            quarters=[q1, q2],
        )
        apply_earnings_patch(stock, patch)

        # revenue TTM = 5.5B + 5.8B + 20B * 2/4 = 11.3B + 10B = 21.3B
        assert stock.revenue == pytest.approx(21_300_000_000)
        # eps TTM = 3.0 + 3.2 + 10.0 * 2/4 = 6.2 + 5.0 = 11.2
        assert stock.eps == pytest.approx(11.2)

    def test_zero_fields_skipped(self):
        """Fields with all-zero values in patch quarters are not patched."""
        stock = _make_stock(revenue=20_000_000_000)
        q1 = QuarterlyEarnings(
            "Q1 FY2026",
            "2025-12-31",
            revenue=5_500_000_000,
            net_income=1_500_000_000,
            # All other fields left as 0.0 default
        )

        patch = EarningsPatch(
            ticker="TEST",
            source_description="Partial data",
            quarters=[q1],
        )
        result = apply_earnings_patch(stock, patch)

        # revenue and net_income should be patched
        assert "revenue" in result.patched_fields
        assert "net_income" in result.patched_fields
        # sbc, capex, etc. should NOT be patched (all zeros in quarter)
        assert "sbc" not in result.patched_fields
        assert "capex" not in result.patched_fields

    def test_provenance_stored_in_extra(self):
        """Patch metadata is stored in stock.extra."""
        stock = _make_stock()
        q1 = QuarterlyEarnings("Q2 FY2026", "2026-05-31", revenue=5_500_000_000, net_income=1_500_000_000, eps=3.0)

        patch = EarningsPatch(
            ticker="TEST",
            source_description="SEC 10-Q",
            quarters=[q1],
        )
        apply_earnings_patch(stock, patch)

        assert "earnings_patch" in stock.extra
        assert stock.extra["earnings_patch"]["source"] == "SEC 10-Q"
        assert stock.extra["earnings_patch"]["quarters"] == ["Q2 FY2026"]
        assert stock.extra["earnings_patch"]["patch_quarters_used"] == 1

    def test_warning_added(self):
        """Warning message added to stock.warnings."""
        stock = _make_stock()
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000)

        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        apply_earnings_patch(stock, patch)

        assert any("patched" in w.lower() for w in stock.warnings)

    def test_empty_patch_returns_no_changes(self):
        """Empty quarters list results in no changes and a warning."""
        stock = _make_stock()
        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[])
        result = apply_earnings_patch(stock, patch)

        assert len(result.patched_fields) == 0
        assert len(result.warnings) > 0
        assert not stock.is_patched

    def test_operating_margin_recomputed(self):
        """Operating margin is recomputed when revenue or ebit is patched."""
        stock = _make_stock(revenue=20_000_000_000, ebit=7_000_000_000, operating_margin=35.0)
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=6_000_000_000, net_income=2_000_000_000, ebit=2_200_000_000)

        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        result = apply_earnings_patch(stock, patch)

        assert "operating_margin" in result.patched_fields
        # TTM revenue = 6B + 20B*3/4 = 21B, TTM ebit = 2.2B + 7B*3/4 = 7.45B
        expected_margin = 7_450_000_000 / 21_000_000_000 * 100
        assert stock.operating_margin == pytest.approx(expected_margin, rel=1e-4)

    def test_fcf_derived_from_ocf_capex(self):
        """FCF is derived from OCF - capex when not directly provided."""
        stock = _make_stock(fcf=4_000_000_000, operating_cash_flow=6_000_000_000, capex=2_000_000_000)
        q1 = QuarterlyEarnings(
            "Q1 FY2026",
            "2025-12-31",
            revenue=5_500_000_000,
            net_income=1_500_000_000,
            operating_cash_flow=1_800_000_000,
            capex=400_000_000,
            # fcf left as 0.0
        )

        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        result = apply_earnings_patch(stock, patch)

        # FCF should be derived: TTM_OCF - TTM_capex
        ttm_ocf = 1_800_000_000 + 6_000_000_000 * 3 / 4
        ttm_capex = 400_000_000 + 2_000_000_000 * 3 / 4
        expected_fcf = ttm_ocf - ttm_capex
        assert stock.fcf == pytest.approx(expected_fcf, rel=1e-4)
        assert "fcf" in result.patched_fields


class TestStockProperties:
    """Test is_patched and data_provenance properties on Stock."""

    def test_is_patched_false_default(self):
        stock = _make_stock()
        assert not stock.is_patched

    def test_is_patched_true_after_patch(self):
        stock = _make_stock()
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000)
        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        apply_earnings_patch(stock, patch)
        assert stock.is_patched

    def test_data_provenance_empty_default(self):
        stock = _make_stock()
        assert stock.data_provenance == {}

    def test_data_provenance_lists_patched_fields(self):
        stock = _make_stock()
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000, eps=3.0)
        patch = EarningsPatch(ticker="TEST", source_description="SEC 10-Q", quarters=[q1])
        apply_earnings_patch(stock, patch)

        provenance = stock.data_provenance
        assert "revenue" in provenance
        assert "SEC 10-Q" in provenance["revenue"]
        assert "net_income" in provenance


class TestLoadPatchFromJson:
    """Test JSON loading."""

    def test_load_valid_json(self):
        data = {
            "ticker": "TEST",
            "source_description": "SEC 10-Q",
            "quarters": [
                {
                    "quarter_label": "Q1 FY2026",
                    "end_date": "2025-12-31",
                    "revenue": 5500000000,
                    "net_income": 1500000000,
                    "eps": 3.0,
                    "operating_cash_flow": 1800000000,
                    "capex": 400000000,
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            patch = load_patch_from_json(f.name)

        assert patch.ticker == "TEST"
        assert patch.source_description == "SEC 10-Q"
        assert len(patch.quarters) == 1
        assert patch.quarters[0].revenue == 5_500_000_000
        assert patch.quarters[0].eps == 3.0
        os.unlink(f.name)

    def test_load_missing_optional_fields(self):
        """Optional fields default to 0.0 when missing from JSON."""
        data = {
            "ticker": "TEST",
            "source_description": "Test",
            "quarters": [
                {
                    "quarter_label": "Q1",
                    "end_date": "2025-03-31",
                    "revenue": 1000,
                    "net_income": 100,
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            patch = load_patch_from_json(f.name)

        assert patch.quarters[0].eps == 0.0
        assert patch.quarters[0].operating_cash_flow == 0.0
        assert patch.quarters[0].sbc == 0.0
        os.unlink(f.name)
