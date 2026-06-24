"""Phase 0: wires settings, the KILL switch, and the live-mode gate. Phase 0
ships no trading loop; `main()` only proves the gates work. Phase 1+ strategy
logic, Phase 2+ backtesting, and the Phase 4 live broker wiring slot in later
without changing this gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from config.settings import Settings


class LiveNotAllowedError(RuntimeError):
    """Raised when live trading is requested but the live-unlock conditions are not met."""


def assert_live_allowed(settings: Settings, report_path: str | Path = "validation_report.json") -> None:
    """No-op for backtest/paper. For live, raises unless `LIVE_CONFIRMED=true`
    AND a `validation_report.json` exists AND its metrics meet the Phase 3
    validation bar (`Settings.validation_*` fields). This is the one function
    standing between config and a live order, so live trading is physically
    unreachable until both the flag and a passing report exist.
    """
    if settings.trading_mode != "live":
        return

    if not settings.live_confirmed:
        raise LiveNotAllowedError("Live trading requires LIVE_CONFIRMED=true.")

    path = Path(report_path)
    if not path.exists():
        raise LiveNotAllowedError(f"Live trading requires a validation report at {path}; none found.")

    try:
        report = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise LiveNotAllowedError(f"Validation report at {path} is not valid JSON.") from exc

    failures: list[str] = []

    paper_sessions = report.get("paper_sessions_completed", 0)
    if paper_sessions < settings.validation_min_paper_sessions:
        failures.append(f"paper_sessions_completed={paper_sessions} < {settings.validation_min_paper_sessions}")

    total_trades = report.get("total_trades", 0)
    if total_trades < settings.validation_min_trades:
        failures.append(f"total_trades={total_trades} < {settings.validation_min_trades}")

    profit_factor = report.get("profit_factor", 0.0)
    if profit_factor <= settings.validation_min_profit_factor:
        failures.append(f"profit_factor={profit_factor} <= {settings.validation_min_profit_factor}")

    max_drawdown_pct = report.get("max_drawdown_pct", 100.0)
    if max_drawdown_pct >= settings.validation_max_drawdown_pct:
        failures.append(f"max_drawdown_pct={max_drawdown_pct} >= {settings.validation_max_drawdown_pct}")

    expectancy_r = report.get("expectancy_r", -1.0)
    if expectancy_r <= settings.validation_min_expectancy_r:
        failures.append(f"expectancy_r={expectancy_r} <= {settings.validation_min_expectancy_r}")

    if failures:
        raise LiveNotAllowedError(
            "Validation report does not meet the live-unlock bar: " + "; ".join(failures)
        )


def main() -> None:
    settings = Settings()

    if settings.kill:
        print("KILL flag is set; refusing to start a session.", file=sys.stderr)
        sys.exit(1)

    assert_live_allowed(settings)

    print(f"Session starting in {settings.trading_mode!r} mode. No trading loop in Phase 0.")


if __name__ == "__main__":
    main()
