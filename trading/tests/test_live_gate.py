from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.settings import Settings
from run_session import LiveNotAllowedError, assert_live_allowed

VALID_REPORT = {
    "paper_sessions_completed": 25,
    "total_trades": 40,
    "profit_factor": 1.5,
    "max_drawdown_pct": 5.0,
    "expectancy_r": 0.2,
}


def test_paper_mode_never_checks_for_a_report() -> None:
    settings = Settings(trading_mode="paper", live_confirmed=False)
    assert_live_allowed(settings, report_path="this-file-does-not-exist.json")


def test_backtest_mode_never_checks_for_a_report() -> None:
    settings = Settings(trading_mode="backtest", live_confirmed=False)
    assert_live_allowed(settings, report_path="this-file-does-not-exist.json")


def test_live_mode_blocked_without_live_confirmed() -> None:
    settings = Settings(trading_mode="live", live_confirmed=False)
    with pytest.raises(LiveNotAllowedError, match="LIVE_CONFIRMED"):
        assert_live_allowed(settings)


def test_live_mode_blocked_when_confirmed_but_report_missing(tmp_path: Path) -> None:
    settings = Settings(trading_mode="live", live_confirmed=True)
    missing_report = tmp_path / "validation_report.json"

    with pytest.raises(LiveNotAllowedError, match="validation report"):
        assert_live_allowed(settings, report_path=missing_report)


def test_live_mode_blocked_when_report_misses_the_bar(tmp_path: Path) -> None:
    settings = Settings(trading_mode="live", live_confirmed=True)
    report_path = tmp_path / "validation_report.json"
    failing_report = dict(VALID_REPORT, profit_factor=1.0)
    report_path.write_text(json.dumps(failing_report))

    with pytest.raises(LiveNotAllowedError, match="profit_factor"):
        assert_live_allowed(settings, report_path=report_path)


def test_live_mode_blocked_on_malformed_report(tmp_path: Path) -> None:
    settings = Settings(trading_mode="live", live_confirmed=True)
    report_path = tmp_path / "validation_report.json"
    report_path.write_text("not valid json")

    with pytest.raises(LiveNotAllowedError, match="not valid JSON"):
        assert_live_allowed(settings, report_path=report_path)


def test_live_mode_allowed_when_confirmed_and_report_meets_the_bar(tmp_path: Path) -> None:
    settings = Settings(trading_mode="live", live_confirmed=True)
    report_path = tmp_path / "validation_report.json"
    report_path.write_text(json.dumps(VALID_REPORT))

    assert_live_allowed(settings, report_path=report_path)
