"""Στρατηγική: συνδυάζει δείκτες για σήματα BUY / SELL / HOLD."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .config import StrategyCfg
from .indicators import ema, rsi


@dataclass
class Signal:
    kind: str                     # "BUY" | "SELL" | "HOLD"
    reason: str
    price: float
    indicators: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.kind} @ {self.price:.4f} ({self.reason})"


@dataclass
class MarketSnapshot:
    """Έτοιμοι δείκτες για την τρέχουσα στιγμή — χρήσιμοι για logs."""
    price: float
    ema_fast: Optional[float]
    ema_slow: Optional[float]
    rsi: Optional[float]


def compute_snapshot(prices: list[float], cfg: StrategyCfg) -> MarketSnapshot:
    """Υπολογίζει όλους τους δείκτες και επιστρέφει τις τελευταίες τιμές."""
    ema_f = ema(prices, cfg.ema_fast)
    ema_s = ema(prices, cfg.ema_slow)
    rsi_s = rsi(prices, cfg.rsi_period)

    def _last(series):
        for v in reversed(series):
            if v is not None:
                return v
        return None

    return MarketSnapshot(
        price=prices[-1],
        ema_fast=_last(ema_f),
        ema_slow=_last(ema_s),
        rsi=_last(rsi_s),
    )


def evaluate(prices: list[float], cfg: StrategyCfg, position_open: bool) -> Signal:
    """Βγάζει σήμα από την ιστορία τιμών.

    Λογική:
      BUY  — χωρίς ανοιχτή θέση, όταν η γρήγορη EMA διασχίζει ΠΑΝΩ από την αργή
             (φρέσκο crossover) και το RSI ΔΕΝ είναι σε υπεραγορά.
      SELL — με ανοιχτή θέση, όταν η γρήγορη EMA διασχίζει ΚΑΤΩ από την αργή
             ή το RSI βρίσκεται σε υπεραγορά.
      HOLD — σε κάθε άλλη περίπτωση.
    """
    min_len = max(cfg.ema_slow, cfg.rsi_period + 2) + 2
    if len(prices) < min_len:
        return Signal("HOLD", "ανεπαρκής ιστορία τιμών", prices[-1])

    ema_f = ema(prices, cfg.ema_fast)
    ema_s = ema(prices, cfg.ema_slow)
    rsi_s = rsi(prices, cfg.rsi_period)

    f_prev, f_cur = ema_f[-2], ema_f[-1]
    s_prev, s_cur = ema_s[-2], ema_s[-1]
    r_cur = rsi_s[-1]

    snap = {
        "ema_fast": round(f_cur, 6) if f_cur is not None else None,
        "ema_slow": round(s_cur, 6) if s_cur is not None else None,
        "rsi": round(r_cur, 2) if r_cur is not None else None,
    }
    price = prices[-1]

    if None in (f_prev, f_cur, s_prev, s_cur, r_cur):
        return Signal("HOLD", "οι δείκτες δεν έχουν ζεσταθεί ακόμα", price, snap)

    cross_up = f_prev <= s_prev and f_cur > s_cur
    cross_down = f_prev >= s_prev and f_cur < s_cur

    if not position_open and cross_up and r_cur < cfg.rsi_overbought:
        return Signal("BUY", f"EMA{cfg.ema_fast} ανέβηκε πάνω από EMA{cfg.ema_slow}, RSI={r_cur:.1f}", price, snap)

    if position_open:
        if cross_down:
            return Signal("SELL", f"EMA{cfg.ema_fast} κατέβηκε κάτω από EMA{cfg.ema_slow}, RSI={r_cur:.1f}", price, snap)
        if r_cur > cfg.rsi_overbought:
            return Signal("SELL", f"RSI σε υπεραγορά ({r_cur:.1f})", price, snap)

    return Signal("HOLD", "κανένα σήμα", price, snap)
