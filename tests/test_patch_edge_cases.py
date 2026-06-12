"""
Edge-case and integration tests for valueinvest.data.patch module.

These tests complement the existing test_patch.py (which has 20 tests) and
cover integration with Stock properties, sequential patching, loss quarters,
seasonal spikes, partial data, serialization, and provenance round-trips.
"""

import json
import os
import tempfile

import pytest

from valueinvest.data.patch import (
    EarningsPatch,
    QuarterlyEarnings,
    apply_earnings_patch,
    load_patch_from_json,
)
from valueinvest.stock import Stock


def _make_stock(
    ticker="TEST",
    current_price=100.0,
    shares_outstanding=500_000_000,
    revenue=20_000_000_000,
    net_income=5_000_000_000,
    eps=10.0,
    bvps=40.0,
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
    """Create a Stock instance with sensible defaults."""
    return Stock(
        ticker=ticker,
        current_price=current_price,
        shares_outstanding=shares_outstanding,
        revenue=revenue,
        net_income=net_income,
        eps=eps,
        bvps=bvps,
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


# ---------------------------------------------------------------------------
# 1. Integration with Stock properties
# ---------------------------------------------------------------------------

class TestPatchStockPropertyIntegration:
    """After patching, verify that computed Stock properties reflect patched values."""

    def test_pe_ratio_reflects_patched_eps(self):
        """PE ratio should use the patched EPS."""
        stock = _make_stock(eps=10.0, current_price=100.0)
        # Pre-patch PE = 100/10 = 10
        assert stock.pe_ratio == pytest.approx(10.0)

        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000, eps=5.0)
        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        apply_earnings_patch(stock, patch)

        # TTM EPS = 5.0 + 10.0 * 3/4 = 12.5
        assert stock.eps == pytest.approx(12.5)
        assert stock.pe_ratio == pytest.approx(100.0 / 12.5)

    def test_pb_ratio_unchanged_by_earnings_patch(self):
        """PB ratio should not change from an earnings patch (BVPS is unchanged)."""
        stock = _make_stock(bvps=40.0, current_price=100.0)
        pre_pb = stock.pb_ratio

        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000, eps=3.0)
        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        apply_earnings_patch(stock, patch)

        assert stock.pb_ratio == pytest.approx(pre_pb)

    def test_market_cap_unchanged_by_earnings_patch(self):
        """Market cap depends on price and shares outstanding, not earnings."""
        stock = _make_stock(current_price=100.0, shares_outstanding=500_000_000)
        pre_mc = stock.market_cap

        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000)
        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        apply_earnings_patch(stock, patch)

        assert stock.market_cap == pytest.approx(pre_mc)

    def test_true_fcf_reflects_patched_fcf_and_sbc(self):
        """true_fcf = fcf - sbc should use patched values."""
        stock = _make_stock(fcf=4_000_000_000, sbc=1_000_000_000)
        q1 = QuarterlyEarnings(
            "Q1 FY2026", "2025-12-31",
            revenue=5_500_000_000, net_income=1_500_000_000,
            operating_cash_flow=1_800_000_000, capex=400_000_000, sbc=200_000_000,
        )
        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        apply_earnings_patch(stock, patch)

        ttm_fcf = stock.operating_cash_flow - stock.capex  # derived from OCF - capex
        expected_true_fcf = ttm_fcf - stock.sbc
        assert stock.true_fcf == pytest.approx(expected_true_fcf, rel=1e-4)

    def test_sbc_margin_reflects_patched_sbc_and_revenue(self):
        """sbc_margin = sbc / revenue * 100 should use patched values."""
        stock = _make_stock(sbc=1_000_000_000, revenue=20_000_000_000)
        q1 = QuarterlyEarnings(
            "Q1 FY2026", "2025-12-31",
            revenue=6_000_000_000, net_income=1_500_000_000, sbc=300_000_000,
        )
        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        apply_earnings_patch(stock, patch)

        expected_margin = stock.sbc / stock.revenue * 100
        assert stock.sbc_margin == pytest.approx(expected_margin, rel=1e-4)

    def test_sbc_as_pct_of_fcf_reflects_patched_values(self):
        """sbc_as_pct_of_fcf should use patched fcf and sbc."""
        stock = _make_stock(fcf=4_000_000_000, sbc=1_000_000_000)
        q1 = QuarterlyEarnings(
            "Q1 FY2026", "2025-12-31",
            revenue=5_500_000_000, net_income=1_500_000_000,
            operating_cash_flow=1_800_000_000, capex=400_000_000, sbc=200_000_000,
        )
        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        apply_earnings_patch(stock, patch)

        expected_pct = stock.sbc / stock.fcf * 100
        assert stock.sbc_as_pct_of_fcf == pytest.approx(expected_pct, rel=1e-4)

    def test_fcf_per_share_reflects_patched_fcf(self):
        """fcf_per_share = fcf / shares_outstanding should use patched fcf."""
        stock = _make_stock(fcf=4_000_000_000, shares_outstanding=500_000_000)
        q1 = QuarterlyEarnings(
            "Q1 FY2026", "2025-12-31",
            revenue=5_500_000_000, net_income=1_500_000_000,
            operating_cash_flow=1_800_000_000, capex=400_000_000,
        )
        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        apply_earnings_patch(stock, patch)

        expected_fps = stock.fcf / stock.shares_outstanding
        assert stock.fcf_per_share == pytest.approx(expected_fps, rel=1e-4)


# ---------------------------------------------------------------------------
# 2. Multiple patches applied sequentially
# ---------------------------------------------------------------------------

class TestSequentialPatches:
    """Apply Q1 patch, then Q2 patch -- second patch should override/extend."""

    def test_two_sequential_patches_update_values(self):
        """Applying a second patch should update stock with the new TTM."""
        stock = _make_stock(revenue=20_000_000_000, net_income=5_000_000_000, eps=10.0)

        # First patch: Q1 only
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000, eps=3.0)
        patch1 = EarningsPatch(ticker="TEST", source_description="Q1 filing", quarters=[q1])
        result1 = apply_earnings_patch(stock, patch1)

        revenue_after_q1 = stock.revenue
        # TTM = 5.5B + 20B * 3/4 = 5.5B + 15B = 20.5B
        assert revenue_after_q1 == pytest.approx(20_500_000_000)

        # Second patch: Q1+Q2 (this replaces the prior patch's effect).
        # The second patch uses stock's *current* values as "api_annual", which
        # are now the post-first-patch TTM values (20.5B revenue, 10.75 eps).
        q1_v2 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000, eps=3.0)
        q2_v2 = QuarterlyEarnings("Q2 FY2026", "2026-03-31", revenue=5_800_000_000, net_income=1_600_000_000, eps=3.2)
        patch2 = EarningsPatch(ticker="TEST", source_description="Q2 filing", quarters=[q1_v2, q2_v2])
        result2 = apply_earnings_patch(stock, patch2)

        # TTM revenue = 5.5B + 5.8B + 20.5B * 2/4 = 11.3B + 10.25B = 21.55B
        assert stock.revenue == pytest.approx(21_550_000_000)
        # After first patch, stock.eps = 3.0 + 10.0 * 3/4 = 10.5
        # Second patch: ttm_eps = 6.2 + 10.5 * 2/4 = 6.2 + 5.25 = 11.45
        assert stock.eps == pytest.approx(11.45)

        # Provenance should reflect the latest patch
        assert stock.extra["earnings_patch"]["source"] == "Q2 filing"
        assert stock.extra["earnings_patch"]["patch_quarters_used"] == 2

    def test_second_patch_only_one_quarter_overrides(self):
        """A single-quarter second patch should override, not add to first."""
        stock = _make_stock(revenue=20_000_000_000, eps=10.0)

        # First: 2 quarters
        q1 = QuarterlyEarnings("Q1", "2025-09-30", revenue=5_500_000_000, net_income=1_500_000_000, eps=3.0)
        q2 = QuarterlyEarnings("Q2", "2025-12-31", revenue=5_800_000_000, net_income=1_600_000_000, eps=3.2)
        apply_earnings_patch(stock, EarningsPatch(ticker="TEST", source_description="P1", quarters=[q1, q2]))

        after_first = stock.revenue

        # Second: just 1 new quarter (Q3)
        q3 = QuarterlyEarnings("Q3", "2026-03-31", revenue=6_000_000_000, net_income=1_700_000_000, eps=3.4)
        apply_earnings_patch(stock, EarningsPatch(ticker="TEST", source_description="P2", quarters=[q3]))

        # Second patch computes: 6B + (after_first) * 3/4
        # since after_first is now the "api_annual" from perspective of second patch
        expected = 6_000_000_000 + after_first * 3 / 4
        assert stock.revenue == pytest.approx(expected, rel=1e-4)
        assert stock.extra["earnings_patch"]["source"] == "P2"


# ---------------------------------------------------------------------------
# 3. Patch with negative net_income (loss quarter)
# ---------------------------------------------------------------------------

class TestLossQuarter:
    """Ensure loss quarters don't break TTM calculation."""

    def test_negative_net_income_single_quarter(self):
        """A loss quarter should produce a reduced (or negative) TTM net_income."""
        stock = _make_stock(net_income=5_000_000_000, revenue=20_000_000_000, eps=10.0)

        q1 = QuarterlyEarnings(
            "Q1 FY2026", "2025-12-31",
            revenue=5_500_000_000,
            net_income=-500_000_000,  # loss!
            eps=-1.0,
        )
        patch = EarningsPatch(ticker="TEST", source_description="Loss quarter", quarters=[q1])
        result = apply_earnings_patch(stock, patch)

        # TTM net_income = -500M + 5B * 3/4 = -500M + 3.75B = 3.25B
        assert stock.net_income == pytest.approx(3_250_000_000)
        assert "net_income" in result.patched_fields

        # EPS with negative sum: code checks eps_sum > 0 before patching.
        # Since eps_sum = -1.0 <= 0, EPS is NOT patched (stays at API value 10.0)
        assert stock.eps == pytest.approx(10.0)
        assert "eps" not in result.patched_fields

    def test_multiple_loss_quarters(self):
        """Multiple loss quarters should work correctly."""
        stock = _make_stock(net_income=5_000_000_000, revenue=20_000_000_000)

        q1 = QuarterlyEarnings("Q1", "2025-09-30", revenue=4_000_000_000, net_income=-200_000_000)
        q2 = QuarterlyEarnings("Q2", "2025-12-31", revenue=3_500_000_000, net_income=-300_000_000)
        patch = EarningsPatch(ticker="TEST", source_description="Loss", quarters=[q1, q2])
        result = apply_earnings_patch(stock, patch)

        # TTM = (-200M + -300M) + 5B * 2/4 = -500M + 2.5B = 2.0B
        assert stock.net_income == pytest.approx(2_000_000_000)
        assert "net_income" in result.patched_fields

    def test_all_negative_quarters(self):
        """All 4 quarters with losses should produce negative TTM."""
        stock = _make_stock(net_income=5_000_000_000)

        quarters = [
            QuarterlyEarnings(f"Q{i}", "2025-03-31", revenue=3_000_000_000, net_income=-500_000_000)
            for i in range(1, 5)
        ]
        patch = EarningsPatch(ticker="TEST", source_description="All losses", quarters=quarters)
        result = apply_earnings_patch(stock, patch)

        assert stock.net_income == pytest.approx(-2_000_000_000)


# ---------------------------------------------------------------------------
# 4. Patch with very large quarter (seasonal spike)
# ---------------------------------------------------------------------------

class TestSeasonalSpike:
    """Verify formula handles very large seasonal quarters correctly."""

    def test_huge_single_quarter(self):
        """A very large quarter should inflate TTM appropriately."""
        stock = _make_stock(revenue=20_000_000_000)

        q1 = QuarterlyEarnings(
            "Q4 FY2025", "2025-12-31",
            revenue=30_000_000_000,  # 50% of annual in one quarter
            net_income=10_000_000_000,
        )
        patch = EarningsPatch(ticker="TEST", source_description="Holiday spike", quarters=[q1])
        result = apply_earnings_patch(stock, patch)

        # TTM = 30B + 20B * 3/4 = 30B + 15B = 45B
        assert stock.revenue == pytest.approx(45_000_000_000)
        # TTM = 10B + 5B * 3/4 = 10B + 3.75B = 13.75B
        assert stock.net_income == pytest.approx(13_750_000_000)

    def test_spike_with_existing_high_base(self):
        """Spike on top of already-high API values."""
        stock = _make_stock(revenue=100_000_000_000, net_income=30_000_000_000)

        q1 = QuarterlyEarnings(
            "Q1 FY2026", "2025-12-31",
            revenue=40_000_000_000,
            net_income=15_000_000_000,
        )
        patch = EarningsPatch(ticker="TEST", source_description="Spike", quarters=[q1])
        apply_earnings_patch(stock, patch)

        # TTM revenue = 40B + 100B * 3/4 = 40B + 75B = 115B
        assert stock.revenue == pytest.approx(115_000_000_000)
        # TTM net_income = 15B + 30B * 3/4 = 15B + 22.5B = 37.5B
        assert stock.net_income == pytest.approx(37_500_000_000)


# ---------------------------------------------------------------------------
# 5. Patch where values match API (no change)
# ---------------------------------------------------------------------------

class TestPatchMatchesApiValues:
    """When patch produces values identical to API, no fields should be in patched_fields."""

    def test_no_change_when_ttm_equals_api(self):
        """If the TTM result equals the API annual value, nothing should be patched."""
        # API annual revenue = 20B.  If we provide 1 quarter of exactly 5B,
        # TTM = 5B + 20B * 3/4 = 5B + 15B = 20B (same as API)
        stock = _make_stock(revenue=20_000_000_000, net_income=5_000_000_000, eps=10.0)

        q1 = QuarterlyEarnings("Q1", "2025-12-31", revenue=5_000_000_000, net_income=1_250_000_000, eps=2.5)
        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        result = apply_earnings_patch(stock, patch)

        # All TTM values should match API, so patched_fields should be empty
        # for revenue: TTM = 5B + 20B*3/4 = 20B == API
        assert "revenue" not in result.patched_fields
        # for net_income: TTM = 1.25B + 5B*3/4 = 1.25B + 3.75B = 5B == API
        assert "net_income" not in result.patched_fields
        # for eps: TTM = 2.5 + 10*3/4 = 10 == API
        assert "eps" not in result.patched_fields

        # But provenance should still be stored (patch was applied, just no changes)
        assert "earnings_patch" in stock.extra
        assert any("no fields were modified" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# 6. Patch with only EPS data
# ---------------------------------------------------------------------------

class TestEpsOnlyPatch:
    """Patch with revenue=0, net_income=0 -- only EPS should be patched."""

    def test_only_eps_patched_when_revenue_and_income_zero(self):
        """If only EPS is provided, only EPS field should be patched."""
        stock = _make_stock(revenue=20_000_000_000, net_income=5_000_000_000, eps=10.0)

        q1 = QuarterlyEarnings(
            "Q1 FY2026", "2025-12-31",
            revenue=0.0,
            net_income=0.0,
            eps=3.0,
        )
        patch = EarningsPatch(ticker="TEST", source_description="EPS only", quarters=[q1])
        result = apply_earnings_patch(stock, patch)

        # revenue and net_income should NOT be patched (all zeros -> _has_any_data = False)
        assert "revenue" not in result.patched_fields
        assert "net_income" not in result.patched_fields
        # EPS should be patched
        assert "eps" in result.patched_fields
        assert stock.eps == pytest.approx(3.0 + 10.0 * 3 / 4)  # 10.5

        # stock.revenue and stock.net_income should be unchanged
        assert stock.revenue == 20_000_000_000
        assert stock.net_income == 5_000_000_000


# ---------------------------------------------------------------------------
# 7. Patch with 3 quarters
# ---------------------------------------------------------------------------

class TestThreeQuarterPatch:
    """Verify partial TTM formula with N=3."""

    def test_three_quarters_partial_ttm(self):
        """3 quarters: TTM = sum(3Q) + API_annual * 1/4."""
        stock = _make_stock(revenue=20_000_000_000, net_income=5_000_000_000, eps=10.0)

        q1 = QuarterlyEarnings("Q2 FY2025", "2025-05-31", revenue=5_000_000_000, net_income=1_200_000_000, eps=2.40)
        q2 = QuarterlyEarnings("Q3 FY2025", "2025-08-31", revenue=4_800_000_000, net_income=1_100_000_000, eps=2.20)
        q3 = QuarterlyEarnings("Q4 FY2025", "2025-11-30", revenue=5_500_000_000, net_income=1_400_000_000, eps=2.80)

        patch = EarningsPatch(ticker="TEST", source_description="3Q", quarters=[q1, q2, q3])
        result = apply_earnings_patch(stock, patch)

        # revenue TTM = (5B + 4.8B + 5.5B) + 20B * 1/4 = 15.3B + 5B = 20.3B
        assert stock.revenue == pytest.approx(20_300_000_000)
        # net_income TTM = (1.2B + 1.1B + 1.4B) + 5B * 1/4 = 3.7B + 1.25B = 4.95B
        assert stock.net_income == pytest.approx(4_950_000_000)
        # eps TTM = (2.4 + 2.2 + 2.8) + 10 * 1/4 = 7.4 + 2.5 = 9.9
        assert stock.eps == pytest.approx(9.9)

        # Formula in ttm_breakdown should show (4-3)=1 remaining quarter
        breakdown = result.ttm_breakdown["revenue"]
        assert breakdown["n_quarters"] == 3


# ---------------------------------------------------------------------------
# 8. Stock.to_dict() after patch
# ---------------------------------------------------------------------------

class TestPatchAndToDict:
    """Verify patched values appear in serialization."""

    def test_basic_to_dict_has_patched_eps_and_revenue(self):
        """to_dict() (non-full) should show patched EPS and revenue."""
        stock = _make_stock(eps=10.0, revenue=20_000_000_000)
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000, eps=3.0)
        patch = EarningsPatch(ticker="TEST", source_description="Test", quarters=[q1])
        apply_earnings_patch(stock, patch)

        d = stock.to_dict()
        assert d["eps"] == pytest.approx(10.5)  # 3.0 + 10.0*3/4 = 10.5
        # TTM revenue = 5.5B + 20B * 3/4 = 5.5B + 15B = 20.5B
        assert d["revenue"] == pytest.approx(20_500_000_000)
        # PE = 100 / 10.5
        assert d["pe_ratio"] == pytest.approx(100.0 / 10.5)

    def test_full_to_dict_includes_extra_with_patch_info(self):
        """to_dict(full=True) should include extra dict with earnings_patch metadata."""
        stock = _make_stock()
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000)
        patch = EarningsPatch(ticker="TEST", source_description="SEC 10-Q", quarters=[q1])
        apply_earnings_patch(stock, patch)

        d = stock.to_dict(full=True)
        assert "extra" in d
        assert "earnings_patch" in d["extra"]
        assert d["extra"]["earnings_patch"]["source"] == "SEC 10-Q"
        assert d["extra"]["earnings_patch"]["patch_quarters_used"] == 1


# ---------------------------------------------------------------------------
# 9. Stock.summary() after patch
# ---------------------------------------------------------------------------

class TestPatchAndSummary:
    """Verify summary includes patched data."""

    def test_summary_shows_patched_values(self):
        """summary() should reflect patched revenue, net_income, EPS."""
        stock = _make_stock(name="Test Corp", eps=10.0, revenue=20_000_000_000, net_income=5_000_000_000, fcf=4_000_000_000)
        q1 = QuarterlyEarnings(
            "Q1 FY2026", "2025-12-31",
            revenue=5_871_000_000, net_income=1_833_000_000, eps=4.06,
            operating_cash_flow=2_280_000_000, capex=85_000_000,
        )
        patch = EarningsPatch(ticker="TEST", source_description="SEC 10-Q", quarters=[q1])
        apply_earnings_patch(stock, patch)

        summary = stock.summary()
        # Should contain patched revenue
        assert "20,871,000,000" in summary or "20,871,000" in summary.replace(",", "")
        # Should contain warning about patching
        assert "patched" in summary.lower()

    def test_summary_shows_warning(self):
        """summary() should show the earnings patch warning."""
        stock = _make_stock(name="Test Corp")
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000)
        patch = EarningsPatch(ticker="TEST", source_description="Manual", quarters=[q1])
        apply_earnings_patch(stock, patch)

        summary = stock.summary()
        assert "Warnings:" in summary
        assert "patched" in summary.lower()


# ---------------------------------------------------------------------------
# 10. load_patch_from_json with empty quarters array
# ---------------------------------------------------------------------------

class TestLoadPatchEmptyQuarters:
    """load_patch_from_json with empty quarters array."""

    def test_empty_quarters_returns_valid_patch(self):
        """Should return valid EarningsPatch with 0 quarters."""
        data = {
            "ticker": "EMPTY",
            "source_description": "No data yet",
            "quarters": [],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            patch = load_patch_from_json(f.name)

        assert patch.ticker == "EMPTY"
        assert len(patch.quarters) == 0
        os.unlink(f.name)

    def test_missing_quarters_key_returns_valid_patch(self):
        """If 'quarters' key is missing entirely, should still work."""
        data = {
            "ticker": "MISSING",
            "source_description": "No quarters key",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            patch = load_patch_from_json(f.name)

        assert patch.ticker == "MISSING"
        assert len(patch.quarters) == 0
        os.unlink(f.name)


# ---------------------------------------------------------------------------
# 11. load_patch_from_json with extra unknown fields
# ---------------------------------------------------------------------------

class TestLoadPatchUnknownFields:
    """Extra unknown fields in JSON should not crash."""

    def test_extra_toplevel_fields_ignored(self):
        """Unknown top-level fields are silently ignored."""
        data = {
            "ticker": "EXTRA",
            "source_description": "Test",
            "quarters": [
                {
                    "quarter_label": "Q1",
                    "end_date": "2025-12-31",
                    "revenue": 5_500_000_000,
                    "net_income": 1_500_000_000,
                    "unknown_field": "should_be_ignored",
                    "another_unknown": 42,
                }
            ],
            "extra_metadata": "ignored",
            "version": "9.9.9",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            patch = load_patch_from_json(f.name)

        assert patch.ticker == "EXTRA"
        assert len(patch.quarters) == 1
        assert patch.quarters[0].revenue == 5_500_000_000
        # Unknown fields are not attributes of QuarterlyEarnings
        assert not hasattr(patch.quarters[0], "unknown_field")
        os.unlink(f.name)

    def test_fiscal_year_end_month_parsed(self):
        """fiscal_year_end_month should be parsed from JSON."""
        data = {
            "ticker": "FISCAL",
            "source_description": "Test",
            "fiscal_year_end_month": 6,
            "quarters": [],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            patch = load_patch_from_json(f.name)

        assert patch.fiscal_year_end_month == 6
        os.unlink(f.name)


# ---------------------------------------------------------------------------
# 12. Patch provenance round-trip
# ---------------------------------------------------------------------------

class TestProvenanceRoundTrip:
    """Apply patch, check is_patched, data_provenance, extra["earnings_patch"]."""

    def test_provenance_consistency_after_patch(self):
        """All provenance indicators should be consistent."""
        stock = _make_stock()
        q1 = QuarterlyEarnings("Q1 FY2026", "2025-12-31", revenue=5_500_000_000, net_income=1_500_000_000, eps=3.0)
        q2 = QuarterlyEarnings("Q2 FY2026", "2026-03-31", revenue=5_800_000_000, net_income=1_600_000_000, eps=3.2)

        patch = EarningsPatch(
            ticker="TEST",
            source_description="SEC 10-Q Q2 FY2026",
            quarters=[q1, q2],
        )
        result = apply_earnings_patch(stock, patch)

        # 1. is_patched should be True
        assert stock.is_patched is True

        # 2. data_provenance should list all patched fields
        provenance = stock.data_provenance
        assert "revenue" in provenance
        assert "net_income" in provenance
        assert "eps" in provenance
        # Each provenance entry should mention the source
        for field, source in provenance.items():
            assert "SEC 10-Q Q2 FY2026" in source
            assert "patched" in source

        # 3. extra["earnings_patch"] should have complete metadata
        patch_info = stock.extra["earnings_patch"]
        assert patch_info["source"] == "SEC 10-Q Q2 FY2026"
        assert patch_info["quarters"] == ["Q1 FY2026", "Q2 FY2026"]
        assert patch_info["end_dates"] == ["2025-12-31", "2026-03-31"]
        assert patch_info["patch_quarters_used"] == 2
        assert "patched_fields" in patch_info
        assert "ttm_breakdown" in patch_info

        # 4. Patched fields in extra should match result.patched_fields keys
        assert set(patch_info["patched_fields"]) == set(result.patched_fields.keys())

        # 5. Warning should be present
        assert any("patched" in w.lower() for w in stock.warnings)
        assert any("SEC 10-Q Q2 FY2026" in w for w in stock.warnings)

    def test_provenance_cleared_on_new_stock(self):
        """A new stock should not have any provenance data."""
        stock = _make_stock()
        assert not stock.is_patched
        assert stock.data_provenance == {}
        assert "earnings_patch" not in stock.extra
