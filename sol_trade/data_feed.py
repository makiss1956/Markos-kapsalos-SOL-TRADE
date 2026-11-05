"""Τροφοδοσία τιμών: πραγματικές από Jupiter API ή συνθετικές (offline)."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod

from .config import Config
from .jupiter_client import JupiterClient, JupiterError
from .logger import setup_logger

log = setup_logger("sol_trade.feed")


class PriceFeed(ABC):
    """Βασική κλάση τροφοδότη τιμών."""

    @abstractmethod
    def next_price(self) -> float:
        """Επιστρέφει την επόμενη τιμή του token σε USD."""
        ...

    @property
    @abstractmethod
    def label(self) -> str: ...


class JupiterFeed(PriceFeed):
    """Πραγματικές τιμές από το Jupiter Price API v3."""

    def __init__(self, cfg: Config, client: JupiterClient | None = None):
        self.cfg = cfg
        self.client = client or JupiterClient(api_key=cfg.jupiter_api_key)
        self._failures = 0

    @property
    def label(self) -> str:
        return "Jupiter Price API v3"

    def next_price(self) -> float:
        prices = self.client.get_prices([self.cfg.token.mint])
        price = prices[self.cfg.token.mint]
        self._failures = 0
        return price


class SyntheticFeed(PriceFeed):
    """Τυχαία πορεία τιμής (random walk) — ΜΟΝΟ για δοκιμές χωρίς internet.

    Παράγει ρεαλιστικές μικρές διακυμάνσεις γύρω από αρχική τιμή,
    με περιστασιακά «σπρωξίματα» τάσης ώστε η στρατηγική να βρίσκει σήματα.
    """

    def __init__(self, start_price: float = 100.0, seed: int | None = None):
        self._rng = random.Random(seed)
        self._price = start_price
        self._trend = 0.0

    @property
    def label(self) -> str:
        return "Συνθετική τιμή (SIMULATED)"

    def next_price(self) -> float:
        # Κατά διαστήματα αλλάζει η τάση ώστε να σχηματίζονται τάσεις/ανατροπές
        if self._rng.random() < 0.05:
            self._trend = self._rng.uniform(-0.15, 0.15)
        shock = self._rng.gauss(0, 0.25) + self._trend
        self._price = max(0.01, self._price * (1 + shock / 100.0))
        return round(self._price, 6)


class ResilientFeed(PriceFeed):
    """Δοκιμάζει πραγματικές τιμές· αν αποτύχουν συνεχόμενα, πέφτει σε συνθετικές."""

    def __init__(self, primary: PriceFeed, fallback: PriceFeed, max_failures: int = 5):
        self.primary = primary
        self.fallback = fallback
        self.max_failures = max_failures
        self._consecutive_failures = 0

    @property
    def label(self) -> str:
        if self._consecutive_failures >= self.max_failures:
            return f"{self.fallback.label} (fallback)"
        return self.primary.label

    def next_price(self) -> float:
        try:
            price = self.primary.next_price()
            self._consecutive_failures = 0
            return price
        except Exception as e:  # noqa: BLE001
            self._consecutive_failures += 1
            if self._consecutive_failures == 1:
                log.warning("Αποτυχία τροφοδότη (%s)", e)
            if self._consecutive_failures >= self.max_failures:
                if self._consecutive_failures == self.max_failures:
                    log.error(
                        "%d συνεχόμενες αποτυχίες — μετάβαση σε %s",
                        self._consecutive_failures, self.fallback.label,
                    )
                return self.fallback.next_price()
            raise


def make_feed(cfg: Config, offline: bool = False, seed: int | None = None) -> PriceFeed:
    """Δημιουργεί τον κατάλληλο τροφοδότη βάσει ρυθμίσεων."""
    if offline:
        start = 100.0  # ουδέτερη συνθετική τιμή
        return SyntheticFeed(start_price=start, seed=seed)
    primary = JupiterFeed(cfg)
    fallback = SyntheticFeed(start_price=100.0, seed=seed)
    return ResilientFeed(primary, fallback)
