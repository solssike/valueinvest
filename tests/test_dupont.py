"""Tests for DuPont ROE decomposition analysis module."""
import pytest

from valueinvest.stock import Stock
from valueinvest.dupont.three_step import calculate_three_step
from valueinvest.dupont.five_step import calculate_five_step
from valueinvest.dupont.engine import DuPontAnalysisEngine
from valueinvest.dupont import analyze_dupont


@pytest.fixture
def high_quality_stock():
    """High NPM, moderate leverage: ROE driven by profitability."""
    return Stock(
        ticker="GOODCO",
        name="Good Company",
        current_price=150.0,
        shares_outstanding=1_000_000_000,
        revenue=80_000_000_000,
        net_income=20_000_000_000,
        ebit=25_000_000_000,
        interest_expense=1_000_000_000,
        tax_rate=20.0,
        roe=25.0,
        total_assets=100_000_000_000,
        total_liabilities=20_000_000_000,
        cost_of_capital=10.0,
        currency="USD",
    )


@pytest.fixture
def leveraged_stock():
    """High leverage, low NPM: ROE driven by leverage."""
    return Stock(
        ticker="LEVCO",
        name="Leveraged Co",
        current_price=50.0,
        shares_outstanding=500_000_000,
        revenue=30_000_000_000,
        net_income=3_000_000_000,
        ebit=5_000_000_000,
        interest_expense=2_000_000_000,
        tax_rate=25.0,
        roe=15.0,
        total_assets=80_000_000_000,
        total_liabilities=60_000_000_000,
        cost_of_capital=10.0,
        currency="USD",
    )


@pytest.fixture
def zero_ebit_stock():
    """Stock with no EBIT — five-step should be unavailable."""
    return Stock(
        ticker="NOEBIT",
        name="No EBIT Co",
        revenue=10_000_000_000,
        net_income=500_000_000,
        ebit=0.0,
        roe=8.0,
        total_assets=20_000_000_000,
        total_liabilities=13_750_000_000,
        cost_of_capital=10.0,
    )


@pytest.fixture
def missing_data_stock():
    """Stock with zero revenue — decomposition should be unavailable."""
    return Stock(
        ticker="NODATA",
        name="No Data Co",
        revenue=0.0,
        net_income=0.0,
        roe=0.0,
        total_assets=10_000_000_000,
        total_liabilities=5_000_000_000,
        cost_of_capital=10.0,
    )


# === Three-Step Tests ===


class TestThreeStep:
    def test_high_quality_decomposition(self, high_quality_stock):
        result = calculate_three_step(high_quality_stock)

        assert result.is_available is True
        # NPM = 20B / 80B * 100 = 25.0%
        assert result.net_profit_margin == pytest.approx(25.0)
        # AT = 80B / 100B = 0.80x
        assert result.asset_turnover == pytest.approx(0.80)
        # EM = 100B / 80B = 1.25x
        assert result.equity_multiplier == pytest.approx(1.25)
        # ROE = 25 * 0.80 * 1.25 / 100 = 25.0%
        assert result.roe_decomposed == pytest.approx(25.0)

    def test_leveraged_decomposition(self, leveraged_stock):
        result = calculate_three_step(leveraged_stock)

        assert result.is_available is True
        # NPM = 3B / 30B * 100 = 10.0%
        assert result.net_profit_margin == pytest.approx(10.0)
        # AT = 30B / 80B = 0.375x
        assert result.asset_turnover == pytest.approx(0.375)
        # EM = 80B / 20B = 4.0x
        assert result.equity_multiplier == pytest.approx(4.0)
        # ROE = 10 * 0.375 * 4.0 / 100 = 15.0%
        assert result.roe_decomposed == pytest.approx(15.0)

    def test_missing_data(self, missing_data_stock):
        result = calculate_three_step(missing_data_stock)
        assert result.is_available is False

    def test_negative_equity(self):
        stock = Stock(
            ticker="NEGEQUITY",
            revenue=5_000_000_000,
            net_income=-500_000_000,
            total_assets=10_000_000_000,
            total_liabilities=12_000_000_000,  # equity = -2B
            cost_of_capital=10.0,
        )
        result = calculate_three_step(stock)
        assert result.is_available is False


# === Five-Step Tests ===


class TestFiveStep:
    def test_high_quality_five_step(self, high_quality_stock):
        result = calculate_five_step(high_quality_stock)

        assert result.is_available is True
        # EBT = 25B - 1B = 24B
        # Tax Burden = 20B / 24B ≈ 0.8333
        assert result.tax_burden == pytest.approx(20 / 24)
        # Interest Burden = 24B / 25B = 0.96
        assert result.interest_burden == pytest.approx(24 / 25)
        # OpMargin = 25B / 80B * 100 = 31.25%
        assert result.operating_margin == pytest.approx(31.25)
        # AT = 80B / 100B = 0.80x
        assert result.asset_turnover == pytest.approx(0.80)
        # EM = 100B / 80B = 1.25x
        assert result.equity_multiplier == pytest.approx(1.25)

    def test_zero_ebit_unavailable(self, zero_ebit_stock):
        result = calculate_five_step(zero_ebit_stock)
        assert result.is_available is False

    def test_missing_data(self, missing_data_stock):
        result = calculate_five_step(missing_data_stock)
        assert result.is_available is False

    def test_five_step_composition(self, high_quality_stock):
        """Verify five-step composition equals three-step ROE."""
        three = calculate_three_step(high_quality_stock)
        five = calculate_five_step(high_quality_stock)

        assert five.is_available is True
        assert five.roe_decomposed == pytest.approx(three.roe_decomposed, rel=1e-6)


# === Engine Tests ===


class TestDuPontEngine:
    def test_high_quality_driver(self, high_quality_stock):
        engine = DuPontAnalysisEngine()
        result = engine.analyze(high_quality_stock)

        assert result.ticker == "GOODCO"
        assert result.roe_reported == 25.0
        assert result.three_step.is_available is True
        assert result.five_step.is_available is True
        assert result.driver.primary_driver in ("Net Profit Margin", "Balanced")
        assert result.driver.driver_quality in ("Excellent", "Good")
        assert result.driver.leverage_dependency is False

    def test_leveraged_driver(self, leveraged_stock):
        engine = DuPontAnalysisEngine()
        result = engine.analyze(leveraged_stock)

        assert result.driver.leverage_dependency is True
        assert result.driver.driver_quality in ("Poor", "Dangerous")
        assert result.three_step.equity_multiplier > 3.0

    def test_analysis_contains_key_info(self, high_quality_stock):
        engine = DuPontAnalysisEngine()
        result = engine.analyze(high_quality_stock)

        assert len(result.analysis) > 0
        assert any("ROE" in line for line in result.analysis)

    def test_warnings_on_missing_data(self, missing_data_stock):
        engine = DuPontAnalysisEngine()
        result = engine.analyze(missing_data_stock)

        assert len(result.warnings) > 0
        assert result.three_step.is_available is False

    def test_warnings_on_negative_equity(self):
        stock = Stock(
            ticker="NEGEQ",
            revenue=1_000_000_000,
            net_income=-100_000_000,
            total_assets=5_000_000_000,
            total_liabilities=6_000_000_000,
            roe=0.0,
            cost_of_capital=10.0,
        )
        engine = DuPontAnalysisEngine()
        result = engine.analyze(stock)

        assert result.three_step.is_available is False

    def test_zero_ebit_warning(self, zero_ebit_stock):
        engine = DuPontAnalysisEngine()
        result = engine.analyze(zero_ebit_stock)

        assert result.five_step.is_available is False
        assert any("EBIT" in w for w in result.warnings)


# === Convenience Function Tests ===


class TestConvenience:
    def test_analyze_dupont(self, high_quality_stock):
        result = analyze_dupont(high_quality_stock)

        assert result.ticker == "GOODCO"
        assert result.three_step.is_available is True
        assert result.five_step.is_available is True

    def test_top_level_import(self):
        """DuPont classes are importable from top-level package."""
        from valueinvest import DuPontAnalysisEngine, DuPontResult

        assert DuPontAnalysisEngine is not None
        assert DuPontResult is not None


# === Output Format Tests ===


class TestOutputFormats:
    def test_to_summary(self, high_quality_stock):
        engine = DuPontAnalysisEngine()
        result = engine.analyze(high_quality_stock)

        summary = result.to_summary()
        assert "GOODCO" in summary
        assert "Three-Step" in summary
        assert "Five-Step" in summary
        assert "Primary Driver" in summary

    def test_str_output(self, high_quality_stock):
        engine = DuPontAnalysisEngine()
        result = engine.analyze(high_quality_stock)

        s = str(result)
        assert "GOODCO" in s
        assert "ROE=" in s
        assert "NPM=" in s

    def test_three_step_summary(self, high_quality_stock):
        result = calculate_three_step(high_quality_stock)
        summary = result.to_summary()
        assert "Net Profit Margin" in summary
        assert "Asset Turnover" in summary
        assert "Equity Multiplier" in summary

    def test_five_step_summary(self, high_quality_stock):
        result = calculate_five_step(high_quality_stock)
        summary = result.to_summary()
        assert "Tax Burden" in summary
        assert "Interest Burden" in summary
        assert "Operating Margin" in summary
