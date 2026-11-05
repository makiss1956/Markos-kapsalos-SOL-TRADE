"""Paper trading engine — προσομοίωση συναλλαγών χωρίς πραγματικά κεφάλαια.

Κρατάει κατάσταση σε data/paper_state.json:
  cash_usd      — διαθέσιμα μετρητά σε USD
  position      — ανοιχτή θέση ή None
  trades        — ιστορικό ολοκληρωμένων συναλλαγών
  started_at    — πότε ξεκίνησε η προσομοίωση
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .logger import setup_logger
from .risk import Position
from .strategy import Signal
from .utils import load_json, save_json, utc_now_iso

log = setup_logger("sol_trade.paper")


class PaperEngine:
    def __init__(self, cfg: Config, state_path: Path | None = None):
        self.cfg = cfg
        self.state_path = state_path or (cfg.data_dir / "paper_state.json")
        if not self.state_path.exists():
            # Πρώτη εκκίνηση — αποθηκεύουμε αμέσως την αρχική κατάσταση
            save_json(self.state_path, self._default_state())
        state = load_json(self.state_path, self._default_state())
        self.cash_usd: float = float(state["cash_usd"])
        self.position: Position | None = self._load_position(state.get("position"))
        self.trades: list[dict] = state["trades"]
        self.started_at: str = state["started_at"]

    @staticmethod
    def _default_state() -> dict:
        return {
            "cash_usd": 1000.0,
            "position": None,
            "trades": [],
            "started_at": utc_now_iso(),
        }

    @staticmethod
    def _load_position(raw: dict | None) -> Position | None:
        if not raw:
            return None
        return Position(
            entry_price=float(raw["entry_price"]),
            size_token=float(raw["size_token"]),
            size_usd=float(raw["size_usd"]),
            opened_at=raw["opened_at"],
            highest_price=float(raw.get("highest_price") or raw["entry_price"]),
        )

    def to_state(self) -> dict:
        return {
            "cash_usd": self.cash_usd,
            "position": (
                {
                    "entry_price": self.position.entry_price,
                    "size_token": self.position.size_token,
                    "size_usd": self.position.size_usd,
                    "opened_at": self.position.opened_at,
                    "highest_price": self.position.highest_price,
                }
                if self.position
                else None
            ),
            "trades": self.trades,
            "started_at": self.started_at,
        }

    def persist(self) -> None:
        save_json(self.state_path, self.to_state())

    def reset(self) -> None:
        fresh = self._default_state()
        self.cash_usd = fresh["cash_usd"]
        self.position = None
        self.trades = []
        self.started_at = fresh["started_at"]
        self.persist()
        log.info("Το paper state μηδενίστηκε (1000.00 USD μετρητά)")

    # ---------------------------------------------------- ΕΚΤΕΛΕΣΗ
    def buy(self, signal: Signal, risk_manager) -> bool:
        """Ανοίγει θέση αγοράς. Επιστρέφει True αν εκτελέστηκε."""
        fee = self.cfg.trading.fee_pct
        slip = self.cfg.trading.slippage_pct
        size_token = risk_manager.position_size_token(signal.price, fee, slip)
        eff_price = signal.price * (1 + (fee + slip) / 100.0)
        cost_usd = size_token * eff_price  # == trade_amount_usd

        self.cash_usd -= cost_usd
        self.position = Position(
            entry_price=eff_price,
            size_token=size_token,
            size_usd=cost_usd,
            opened_at=utc_now_iso(),
        )
        risk_manager.register_trade()
        log.info(
            "PAPER BUY  %.6f %s @ %.4f | κόστος %.2f USD | μετρητά %.2f",
            size_token, self.cfg.token.symbol, eff_price, cost_usd, self.cash_usd,
        )
        self.persist()
        return True

    def sell(self, signal_price: float, reason: str, risk_manager) -> dict | None:
        """Κλείνει την ανοιχτή θέση. Επιστρέφει το trade record ή None."""
        if self.position is None:
            return None
        fee = self.cfg.trading.fee_pct
        slip = self.cfg.trading.slippage_pct
        exit_price = signal_price * (1 - (fee + slip) / 100.0)

        proceeds = exit_price * self.position.size_token
        pnl = proceeds - self.position.size_usd
        pnl_pct = (exit_price / self.position.entry_price - 1.0) * 100.0

        trade = {
            "opened_at": self.position.opened_at,
            "closed_at": utc_now_iso(),
            "side": "SELL",
            "reason": reason,
            "entry_price": round(self.position.entry_price, 6),
            "exit_price": round(exit_price, 6),
            "size_token": round(self.position.size_token, 6),
            "size_usd": round(self.position.size_usd, 2),
            "proceeds_usd": round(proceeds, 2),
            "pnl_usd": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        }
        self.trades.append(trade)
        self.cash_usd += proceeds
        self.position = None
        risk_manager.register_trade()
        log.info(
            "PAPER SELL %.6f %s @ %.4f | λόγος: %s | PnL %.2f USD (%+.2f%%) | μετρητά %.2f",
            trade["size_token"], self.cfg.token.symbol, exit_price, reason,
            pnl, pnl_pct, self.cash_usd,
        )
        self.persist()
        return trade

    # ---------------------------------------------------- ΣΤΑΤΙΣΤΙΚΑ
    def equity(self, price: float) -> float:
        pos_value = self.position.size_token * price if self.position else 0.0
        return self.cash_usd + pos_value

    def summary(self, price: float | None = None) -> str:
        closed = [t for t in self.trades]
        wins = [t for t in closed if t["pnl_usd"] > 0]
        total_pnl = sum(t["pnl_usd"] for t in closed)
        lines = [
            f"Μετρητά: {self.cash_usd:,.2f} USD | Ολοκληρωμένα trades: {len(closed)} "
            f"(κερδοφόρα: {len(wins)}) | Συνολικό realized PnL: {total_pnl:+,.2f} USD",
        ]
        if self.position:
            p = self.position
            if price:
                lines.append(
                    f"Ανοιχτή θέση: {p.size_token:.6f} {self.cfg.token.symbol} @ είσοδος {p.entry_price:.4f} "
                    f"| unrealized {p.unrealized_pnl_pct(price):+.2f}% ({p.unrealized_pnl(price):+,.2f} USD)"
                )
            else:
                lines.append(f"Ανοιχτή θέση: {p.size_token:.6f} {self.cfg.token.symbol} @ είσοδος {p.entry_price:.4f}")
        else:
            lines.append("Καμία ανοιχτή θέση")
        return "\n".join(lines)
