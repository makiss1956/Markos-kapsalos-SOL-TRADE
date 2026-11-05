"""Backtester — δοκιμή της στρατηγικής σε ιστορικά ή συνθετικά δεδομένα.

Χρήση μέσω run.py:
  python run.py backtest --days 30           # συνθετικά δεδομένα 30 ημερών
  python run.py backtest --csv data/prices.csv  # δικά σας δεδομένα (στήλες: timestamp,price)
"""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .indicators import ema, rsi
from .risk import Position, RiskManager
from .strategy import StrategyCfg


@dataclass
class BacktestTrade:
    opened_at: int
    closed_at: int
    entry_price: float
    exit_price: float
    pnl_usd: float
    pnl_pct: float
    reason: str


@dataclass
class BacktestResult:
    start_price: float
    end_price: float
    initial_cash: float
    final_equity: float
    trades: list[BacktestTrade] = field(default_factory=list)

    @property
    def num_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return 100.0 * sum(1 for t in self.trades if t.pnl_usd > 0) / len(self.trades)

    @property
    def total_pnl(self) -> float:
        return self.final_equity - self.initial_cash

    @property
    def return_pct(self) -> float:
        return (self.final_equity / self.initial_cash - 1.0) * 100.0

    @property
    def buy_hold_return_pct(self) -> float:
        return (self.end_price / self.start_price - 1.0) * 100.0

    @property
    def profit_factor(self) -> float:
        gains = sum(t.pnl_usd for t in self.trades if t.pnl_usd > 0)
        losses = sum(-t.pnl_usd for t in self.trades if t.pnl_usd < 0)
        return gains / losses if losses > 0 else math.inf if gains > 0 else 0.0

    @property
    def max_drawdown_pct(self) -> float:
        return self._max_dd

    _max_dd: float = 0.0

    def summary_text(self) -> str:
        lines = [
            f"Τελικό υπόλοιπο:      {self.final_equity:,.2f} USD (αρχικό {self.initial_cash:,.2f})",
            f"Συνολικό PnL:         {self.total_pnl:+,.2f} USD ({self.return_pct:+.2f}%)",
            f"Συναλλαγές:           {self.num_trades} | Win rate: {self.win_rate:.1f}% | Profit factor: {self.profit_factor:.2f}",
            f"Μέγιστη απώλεια κορυφής (max drawdown): {self.max_drawdown_pct:.2f}%",
            f"Buy & hold για σύγκριση: {self.buy_hold_return_pct:+.2f}%",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------- ΔΕΔΟΜΕΝΑ
def synthetic_prices(days: int, points_per_day: int = 288, start: float = 100.0,
                     seed: int = 42) -> list[float]:
    """Συνθετική τιμή (5-λεπτά κεριά: 288/ημέρα) με τάσεις και σοκ.

    Χρησιμοποιείται όταν δεν υπάρχουν πραγματικά ιστορικά δεδομένα.
    """
    rng = random.Random(seed)
    n = days * points_per_day
    prices = [start]
    trend = 0.0
    for _ in range(n - 1):
        if rng.random() < 0.02:
            trend = rng.uniform(-0.08, 0.08)
        shock = rng.gauss(0, 0.15) + trend
        prices.append(max(0.01, prices[-1] * (1 + shock / 100.0)))
    return prices


def load_csv_prices(path: Path) -> list[float]:
    """Διαβάζει CSV με στήλες timestamp,price (ή απλά μία στήλη τιμών)."""
    prices: list[float] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        price_col = 0
        if header:
            lowered = [h.strip().lower() for h in header]
            if "price" in lowered:
                price_col = lowered.index("price")
            elif len(lowered) >= 2:
                price_col = 1
        for row in reader:
            if not row:
                continue
            try:
                prices.append(float(row[price_col]))
            except (ValueError, IndexError):
                continue
    if len(prices) < 50:
        raise ValueError(f"Το CSV {path} έχει λιγότερες από 50 έγκυρες τιμές")
    return prices


# ---------------------------------------------------------------- ΕΚΤΕΛΕΣΗ
def run_backtest(cfg: Config, prices: list[float], verbose: bool = True) -> BacktestResult:
    """Τρέχει τη στρατηγική πάνω στη σειρά τιμών (paper-style fills).

    Βελτιστοποίηση: οι δείκτες υπολογίζονται ΜΙΑ φορά σε όλη τη σειρά
    και το βήμα-προς-βήμα γράφει μόνο συγκρίσεις scalars (O(n) αντί O(n²)).
    Η λογική αντιστοιχεί 1:1 στη strategy.evaluate().
    """
    strat: StrategyCfg = cfg.strategy
    risk = RiskManager(cfg.risk)
    fee_slip = cfg.trading.fee_pct + cfg.trading.slippage_pct

    ema_f = ema(prices, strat.ema_fast)
    ema_s = ema(prices, strat.ema_slow)
    rsi_s = rsi(prices, strat.rsi_period)

    position: Position | None = None
    cash = 1000.0
    result = BacktestResult(
        start_price=prices[0], end_price=prices[-1],
        initial_cash=cash, final_equity=cash,
    )

    equity_curve: list[float] = []
    for i in range(len(prices)):
        price = prices[i]

        # 1) Έλεγχος εξόδου (stop/TP/trailing) έχει προτεραιότητα
        if position is not None:
            decision = risk.check_exit(position, price)
            if decision.allowed:
                exit_price = price * (1 - fee_slip / 100.0)
                proceeds = exit_price * position.size_token
                pnl = proceeds - position.size_usd
                result.trades.append(BacktestTrade(
                    opened_at=0, closed_at=i,
                    entry_price=position.entry_price, exit_price=exit_price,
                    pnl_usd=pnl,
                    pnl_pct=(exit_price / position.entry_price - 1) * 100,
                    reason=decision.reason,
                ))
                cash += proceeds
                position = None

        # 2) Σήμα στρατηγικής (ίδια λογική με strategy.evaluate)
        signal_kind = "HOLD"
        signal_reason = "κανένα σήμα"
        f_prev, f_cur = (ema_f[i - 1], ema_f[i]) if i >= 1 else (None, None)
        s_prev, s_cur = (ema_s[i - 1], ema_s[i]) if i >= 1 else (None, None)
        r_cur = rsi_s[i]
        min_len = max(strat.ema_slow, strat.rsi_period + 2) + 2
        if i + 1 < min_len or None in (f_prev, f_cur, s_prev, s_cur, r_cur):
            signal_kind = "HOLD"
        else:
            cross_up = f_prev <= s_prev and f_cur > s_cur
            cross_down = f_prev >= s_prev and f_cur < s_cur
            if not position and cross_up and r_cur < strat.rsi_overbought:
                signal_kind = "BUY"
                signal_reason = f"EMA cross up, RSI={r_cur:.1f}"
            elif position and (cross_down or r_cur > strat.rsi_overbought):
                signal_kind = "SELL"
                signal_reason = ("EMA cross down" if cross_down
                                 else f"RSI υπεραγορά ({r_cur:.1f})")

        if signal_kind == "BUY" and position is None:
            decision = risk.check_entry(price, position, cash)
            if decision.allowed:
                size_token = risk.position_size_token(price, cfg.trading.fee_pct, cfg.trading.slippage_pct)
                eff_price = price * (1 + fee_slip / 100.0)
                cost = size_token * eff_price
                cash -= cost
                position = Position(
                    entry_price=eff_price, size_token=size_token,
                    size_usd=cost, opened_at=str(i),
                )
        elif signal_kind == "SELL" and position is not None:
            exit_price = price * (1 - fee_slip / 100.0)
            proceeds = exit_price * position.size_token
            pnl = proceeds - position.size_usd
            result.trades.append(BacktestTrade(
                opened_at=0, closed_at=i,
                entry_price=position.entry_price, exit_price=exit_price,
                pnl_usd=pnl,
                pnl_pct=(exit_price / position.entry_price - 1) * 100,
                reason=signal_reason,
            ))
            cash += proceeds
            position = None

        pos_value = position.size_token * price if position else 0.0
        equity_curve.append(cash + pos_value)

    # Κλείσιμο ανοιχτής θέσης στην τελευταία τιμή (mark-to-market)
    if position is not None:
        exit_price = prices[-1] * (1 - fee_slip / 100.0)
        proceeds = exit_price * position.size_token
        pnl = proceeds - position.size_usd
        result.trades.append(BacktestTrade(
            opened_at=0, closed_at=len(prices) - 1,
            entry_price=position.entry_price, exit_price=exit_price,
            pnl_usd=pnl,
            pnl_pct=(exit_price / position.entry_price - 1) * 100,
            reason="τέλος backtest",
        ))
        cash += proceeds
        position = None

    result.final_equity = cash

    # Max drawdown στην καμπύλη equity
    peak = equity_curve[0] if equity_curve else cash
    max_dd = 0.0
    for eq in equity_curve:
        peak = max(peak, eq)
        dd = (eq / peak - 1) * 100
        max_dd = min(max_dd, dd)
    result._max_dd = abs(max_dd)

    if verbose:
        print(result.summary_text())
        if result.trades:
            print("\nΤελευταίες 5 συναλλαγές:")
            for t in result.trades[-5:]:
                print(f"  είσοδος {t.entry_price:.4f} -> έξοδος {t.exit_price:.4f} "
                      f"| {t.pnl_usd:+.2f} USD ({t.pnl_pct:+.2f}%) | {t.reason}")
    return result


def export_trades_csv(result: BacktestResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["closed_at_step", "entry_price", "exit_price", "pnl_usd", "pnl_pct", "reason"])
        for t in result.trades:
            w.writerow([t.closed_at, t.entry_price, t.exit_price,
                        round(t.pnl_usd, 4), round(t.pnl_pct, 4), t.reason])
    return path
