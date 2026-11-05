"""Τεχνικοί δείκτες — καθαρές συναρτήσεις πάνω σε λίστες τιμών.

Όλες οι συναρτήσεις επιστρέφουν λίστα με το ίδιο μήκος με την είσοδο,
όπου τα πρώτα (period-1) στοιχεία είναι None (δεν υπάρχει αρκετή ιστορία).
"""

from __future__ import annotations

from typing import Optional

Series = list[Optional[float]]


def sma(values: list[float], period: int) -> Series:
    """Απλός κινούμενος μέσος όρος."""
    if period <= 0:
        raise ValueError("Το period πρέπει να είναι >= 1")
    out: Series = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


def ema(values: list[float], period: int) -> Series:
    """Εκθετικός κινούμενος μέσος όρος (πρώτη τιμή = SMA της περιόδου)."""
    if period <= 0:
        raise ValueError("Το period πρέπει να είναι >= 1")
    out: Series = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(values: list[float], period: int = 14) -> Series:
    """RSI με τη μέθοδο Wilder (κλασικός ορισμός)."""
    if period <= 0:
        raise ValueError("Το period πρέπει να είναι >= 1")
    n = len(values)
    out: Series = [None] * n
    if n <= period:
        return out

    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        if change >= 0:
            gains += change
        else:
            losses -= change
    avg_gain = gains / period
    avg_loss = losses / period

    def _rsi(g: float, l: float) -> float:
        if l == 0:
            return 100.0
        rs = g / l
        return 100.0 - 100.0 / (1.0 + rs)

    out[period] = _rsi(avg_gain, avg_loss)

    for i in range(period + 1, n):
        change = values[i] - values[i - 1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = _rsi(avg_gain, avg_loss)
    return out


def volatility_pct(values: list[float], period: int = 20) -> Series:
    """Τυπική απόκλιση των % μεταβολών (μέτρο μεταβλητότητας), σε %."""
    out: Series = [None] * len(values)
    if len(values) <= period:
        return out
    returns = [0.0]
    for i in range(1, len(values)):
        returns.append((values[i] - values[i - 1]) / values[i - 1] * 100.0)
    for i in range(period, len(values)):
        window = returns[i - period + 1 : i + 1]
        mean = sum(window) / period
        var = sum((r - mean) ** 2 for r in window) / period
        out[i] = var ** 0.5
    return out


def last(series: Series) -> Optional[float]:
    """Τελευταία μη-None τιμή μιας σειράς."""
    for v in reversed(series):
        if v is not None:
            return v
    return None
