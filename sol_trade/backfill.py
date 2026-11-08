"""Αυτόματο γέμισμα του ιστορικού τιμών από ΔΩΡΕΑΝ δημόσια API (χωρίς κλειδί).

Γιατί υπάρχει: η στρατηγική (EMA 12/26 + RSI 14) χρειάζεται τουλάχιστον 28
τιμές πριν βγάλει το πρώτο σήμα. Με ένα tick την ώρα από το GitHub Actions
θα χρειαζόταν πάνω από μια μέρα αναμονή. Οι πηγές εδώ δίνουν ωριαίες τιμές
των τελευταίων ημερών, οπότε το ιστορικό «ζεσταίνεται» από την πρώτη κιόλας
εκτέλεση.

Πηγές (με σειρά προτεραιότητας, όλες δωρεάν & χωρίς εγγραφή):
  1. Coinbase Exchange  — αξιόπιστο από datacenter IPs (GitHub Actions)
  2. Kraken             — δημόσιο OHLC, 720+ ωριαίες τιμές
  3. CoinGecko          — id-based (π.χ. solana), μερικές φορές κάνει rate-limit

Αν αποτύχουν όλες, το bot συνεχίζει κανονικά χωρίς backfill.
"""

from __future__ import annotations

import requests

from .logger import setup_logger

log = setup_logger("sol_trade.backfill")

_TIMEOUT = 25


def _from_coinbase(hours: int, symbol: str) -> list[float]:
    """Coinbase Exchange: κεριά 1h, επιστρέφει newest-first — αντιστρέφουμε."""
    pair = f"{symbol}-USD"
    r = requests.get(
        f"https://api.exchange.coinbase.com/products/{pair}/candles",
        params={"granularity": 3600},
        timeout=_TIMEOUT,
        headers={"User-Agent": "sol_trade/2.1"},
    )
    r.raise_for_status()
    candles = r.json()  # [time, low, high, open, close, volume]
    closes = [float(c[4]) for c in candles]
    closes.reverse()  # παλαιότερη → νεότερη
    return closes[-hours:]


def _from_kraken(hours: int, symbol: str) -> list[float]:
    """Kraken δημόσιο OHLC: κεριά 1h, oldest→newest (το τελευταίο είναι ημιτελές)."""
    r = requests.get(
        "https://api.kraken.com/0/public/OHLC",
        params={"pair": f"{symbol}USD", "interval": 60},
        timeout=_TIMEOUT,
        headers={"User-Agent": "sol_trade/2.1"},
    )
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"Kraken error: {data['error']}")
    result = data.get("result", {})
    key = next((k for k in result if k != "last"), None)
    if not key:
        raise RuntimeError("Kraken: δεν βρέθηκαν δεδομένα")
    candles = result[key]  # [time, open, high, low, close, vwap, volume, count]
    return [float(c[4]) for c in candles[:-1]][-hours:]


def _from_coingecko(hours: int, coin_id: str) -> list[float]:
    """CoinGecko /market_chart: ωριαίες τιμές για days 2..90."""
    days = max(2, int(hours / 24) + 1)
    r = requests.get(
        f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
        params={"vs_currency": "usd", "days": days},
        timeout=_TIMEOUT,
        headers={"User-Agent": "sol_trade/2.1"},
    )
    r.raise_for_status()
    prices = [float(p) for _, p in r.json().get("prices", [])]
    return prices[-hours:]


def fetch_hourly_prices(hours: int = 72, coin_id: str = "solana",
                        symbol: str = "SOL") -> list[float]:
    """Επιστρέφει ωριαίες τιμές USD (παλαιότερη → νεότερη). Δοκιμάζει όλες τις πηγές."""
    attempts = [
        (f"Coinbase ({symbol}-USD)", lambda: _from_coinbase(hours, symbol)),
        (f"Kraken ({symbol}USD)", lambda: _from_kraken(hours, symbol)),
        (f"CoinGecko ({coin_id})", lambda: _from_coingecko(hours, coin_id)),
    ]
    last_err: Exception | None = None
    for name, fn in attempts:
        try:
            prices = fn()
            if len(prices) >= 2:
                log.info("Backfill από %s: %d ωριαίες τιμές", name, len(prices))
                return prices
            last_err = RuntimeError(f"{name}: λίγες τιμές ({len(prices)})")
        except Exception as e:  # noqa: BLE001 — δοκιμάζουμε την επόμενη πηγή
            last_err = e
            log.warning("Backfill πηγή %s απέτυχε: %s", name, e)
    raise RuntimeError(f"Καμία πηγή backfill δεν λειτούργησε (τελευταίο σφάλμα: {last_err})")
