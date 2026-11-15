"""Διαχείριση ρίσκου: μέγεθος θέσης, stop-loss, take-profit, trailing stop."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .config import RiskCfg
import json
from datetime import datetime
from pathlib import Path



@dataclass
class Position:
    entry_price: float
    size_token: float          # ποσό token που κατέχουμε
    size_usd: float            # αξία εισόδου σε USD
    opened_at: str
    highest_price: float = 0.0  # μηδενίζεται στο __post_init__ στην τιμή εισόδου

    def __post_init__(self):
        if self.highest_price <= 0:
            self.highest_price = self.entry_price

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.entry_price) * self.size_token

    def unrealized_pnl_pct(self, price: float) -> float:
        return (price / self.entry_price - 1.0) * 100.0

    def update_peak(self, price: float) -> None:
        self.highest_price = max(self.highest_price, price)


@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    
DAILY_COUNTER_FILE = Path("data/daily_counters.json")

def load_daily_trade_counter():
    today = datetime.now().strftime("%Y-%m-%d")
    if DAILY_COUNTER_FILE.exists():
        try:
            with open(DAILY_COUNTER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") == today:
                    return data.get("count", 0)
        except (json.JSONDecodeError, IOError):
            pass
    return 0

def save_daily_trade_counter(count: int):
    today = datetime.now().strftime("%Y-%m-%d")
    DAILY_COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DAILY_COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": today, "count": count}, f)



class RiskManager:
    def __init__(self, cfg: RiskCfg):
        self.cfg = cfg
        self._daily_count_date: date | None = None
        self._daily_count = 0

    # ---------------------------------------------------- ΕΙΣΟΔΟΣ
    def check_entry(self, price: float, position: Position | None, cash_usd: float) -> RiskDecision:
        """Έλεγχοι πριν από άνοιγμα θέσης."""
        if position is not None:
            return RiskDecision(False, "υπάρχει ήδη ανοιχτή θέση")

        self._rollover_day()
        if self._daily_count >= self.cfg.max_daily_trades:
            return RiskDecision(False, f"συμπληρώθηκε το ημερήσιο όριο ({self.cfg.max_daily_trades} trades)")

        if self.cfg.trade_amount_usd > self.cfg.max_position_usd:
            return RiskDecision(False, "το trade_amount_usd υπερβαίνει το max_position_usd")

        if self.cfg.trade_amount_usd > cash_usd:
            return RiskDecision(False, f"ανεπαρκές υπόλοιπο ({cash_usd:.2f} < {self.cfg.trade_amount_usd:.2f})")

        return RiskDecision(True, "OK")

    def position_size_token(self, price: float, fee_pct: float, slippage_pct: float) -> float:
        """Πόσα token αγοράζουμε με trade_amount_usd, αφαιρώντας fee+slippage."""
        effective_cost_pct = 1.0 + (fee_pct + slippage_pct) / 100.0
        # Το effective price που πληρώνουμε είναι λίγο χειρότερο από το market
        eff_price = price * effective_cost_pct
        return self.cfg.trade_amount_usd / eff_price

    def register_trade(self) -> None:
        self._rollover_day()
        count = load_daily_trade_counter()
count += 1
save_daily_trade_counter(count)


    @property
    def daily_trades(self) -> int:
        self._rollover_day()
        return self._daily_count

    # ---------------------------------------------------- ΕΞΟΔΟΣ
    def check_exit(self, position: Position, price: float) -> RiskDecision:
        """Stop-loss / take-profit / trailing stop. Ελέγχεται πριν από τα σήματα."""
        position.update_peak(price)
        pnl_pct = position.unrealized_pnl_pct(price)

        if pnl_pct <= -abs(self.cfg.stop_loss_pct):
            return RiskDecision(True, f"STOP-LOSS {pnl_pct:+.2f}%")
        if pnl_pct >= abs(self.cfg.take_profit_pct):
            return RiskDecision(True, f"TAKE-PROFIT {pnl_pct:+.2f}%")

        drawdown_from_peak = (price / position.highest_price - 1.0) * 100.0
        peak_gain = (position.highest_price / position.entry_price - 1.0) * 100.0
        if peak_gain > 0 and drawdown_from_peak <= -abs(self.cfg.trailing_stop_pct):
            return RiskDecision(
                True,
                f"TRAILING-STOP κορυφή {position.highest_price:.4f}, τώρα {price:.4f} ({drawdown_from_peak:+.2f}%)",
            )
        return RiskDecision(False, "κανένα κριτήριο εξόδου")

    # ---------------------------------------------------- ΒΟΗΘΗΤΙΚΑ
    def _rollover_day(self) -> None:
        today = date.today()
        if self._daily_count_date != today:
            self._daily_count_date = today
            self._daily_count = 0
