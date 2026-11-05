"""Tests για τη διαχείριση ρίσκου."""

from sol_trade.config import RiskCfg
from sol_trade.risk import Position, RiskManager


def make_cfg(**kw) -> RiskCfg:
    defaults = dict(trade_amount_usd=50.0, max_position_usd=100.0,
                    stop_loss_pct=3.0, take_profit_pct=5.0,
                    trailing_stop_pct=2.0, max_daily_trades=10)
    defaults.update(kw)
    return RiskCfg(**defaults)


def make_position(entry: float = 100.0) -> Position:
    return Position(entry_price=entry, size_token=0.5, size_usd=entry * 0.5,
                    opened_at="2026-01-01T00:00:00Z")


# ------------------------------- ΕΙΣΟΔΟΣ
def test_entry_ok():
    rm = RiskManager(make_cfg())
    d = rm.check_entry(100.0, None, cash_usd=1000.0)
    assert d.allowed


def test_entry_blocked_with_open_position():
    rm = RiskManager(make_cfg())
    d = rm.check_entry(100.0, make_position(), cash_usd=1000.0)
    assert not d.allowed


def test_entry_blocked_insufficient_cash():
    rm = RiskManager(make_cfg(trade_amount_usd=500.0))
    d = rm.check_entry(100.0, None, cash_usd=100.0)
    assert not d.allowed


def test_entry_blocked_daily_limit():
    rm = RiskManager(make_cfg(max_daily_trades=2))
    rm.register_trade()
    rm.register_trade()
    d = rm.check_entry(100.0, None, cash_usd=1000.0)
    assert not d.allowed


def test_position_size_includes_fee():
    rm = RiskManager(make_cfg(trade_amount_usd=100.0))
    size = rm.position_size_token(50.0, fee_pct=0.1, slippage_pct=0.05)
    # effective price = 50 * 1.0015 -> 100 / 50.075 = 1.997...
    assert size < 100.0 / 50.0
    assert size == (100.0 / (50.0 * 1.0015))


# ------------------------------- ΕΞΟΔΟΣ
def test_stop_loss_triggers():
    rm = RiskManager(make_cfg(stop_loss_pct=3.0))
    pos = make_position(100.0)
    d = rm.check_exit(pos, price=96.9)  # -3.1%
    assert d.allowed and "STOP-LOSS" in d.reason


def test_take_profit_triggers():
    rm = RiskManager(make_cfg(take_profit_pct=5.0))
    pos = make_position(100.0)
    d = rm.check_exit(pos, price=105.1)  # +5.1%
    assert d.allowed and "TAKE-PROFIT" in d.reason


def test_trailing_stop_after_gain():
    rm = RiskManager(make_cfg(trailing_stop_pct=2.0, take_profit_pct=50.0))  # υψηλό TP για απομόνωση του trailing
    pos = make_position(100.0)
    rm.check_exit(pos, price=110.0)            # κορυφή 110 (+10%), δεν φτάνει το TP
    d = rm.check_exit(pos, price=107.5)        # -2.27% από κορυφή
    assert d.allowed and "TRAILING-STOP" in d.reason


def test_no_trailing_stop_without_gain():
    rm = RiskManager(make_cfg(trailing_stop_pct=2.0))
    pos = make_position(100.0)
    d = rm.check_exit(pos, price=99.0)         # κάτω από είσοδο, χωρίς κέρδος
    assert not d.allowed


def test_position_tracks_peak():
    pos = make_position(100.0)
    pos.update_peak(120.0)
    assert pos.highest_price == 120.0
    pos.update_peak(110.0)
    assert pos.highest_price == 120.0
