"""Tests για τη στρατηγική σήματος."""

from sol_trade.config import StrategyCfg
from sol_trade.strategy import evaluate


def make_cfg() -> StrategyCfg:
    return StrategyCfg(ema_fast=3, ema_slow=6, rsi_period=5,
                       rsi_oversold=30, rsi_overbought=70)


def test_insufficient_history_is_hold():
    cfg = make_cfg()
    sig = evaluate([100.0, 101.0, 102.0], cfg, position_open=False)
    assert sig.kind == "HOLD"


def test_cross_up_triggers_buy():
    cfg = make_cfg()
    # Πτώση μετά απότομη άνοδος -> σε κάποιο βήμα της ανόδου συμβαίνει cross-up
    prices = [100 - i * 1.0 for i in range(15)]          # 100 ... 86
    prices += [86 + i * 3.0 for i in range(1, 10)]        # απότομη άνοδος
    found = any(
        evaluate(prices[: i + 1], cfg, position_open=False).kind == "BUY"
        for i in range(10, len(prices))
    )
    assert found, "Δεν βρέθηκε BUY σήμα σε κανένα βήμα της ανόδου"


def test_cross_down_triggers_sell_when_position_open():
    cfg = make_cfg()
    prices = [100 + i * 1.0 for i in range(15)]           # άνοδος
    prices += [115 - i * 3.0 for i in range(1, 10)]       # απότομη πτώση
    found = any(
        evaluate(prices[: i + 1], cfg, position_open=True).kind == "SELL"
        for i in range(10, len(prices))
    )
    assert found, "Δεν βρέθηκε SELL σήμα σε κανένα βήμα της πτώσης"


def test_no_buy_signal_when_position_open():
    cfg = make_cfg()
    prices = [100 - i * 1.0 for i in range(15)]
    prices += [86 + i * 3.0 for i in range(1, 10)]
    sig = evaluate(prices, cfg, position_open=True)
    # Με ανοιχτή θέση το cross-up δεν δίνει BUY
    assert sig.kind != "BUY"


def test_rsi_overbought_triggers_sell():
    cfg = make_cfg()
    prices = [100 * (1.01 ** i) for i in range(20)]       # συνεχής άνοδος -> RSI 100
    sig = evaluate(prices, cfg, position_open=True)
    assert sig.kind == "SELL"
