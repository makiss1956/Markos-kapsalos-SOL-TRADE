"""Κύριος βρόχος trading — ενώνει feed, στρατηγική, risk, engines, ειδοποιήσεις."""

from __future__ import annotations

import time

from .config import Config
from .data_feed import PriceFeed
from .logger import setup_logger
from .notifier import Notifier
from .paper_engine import PaperEngine
from .risk import Position, RiskManager
from .strategy import evaluate
from .utils import fmt_usd, load_json, save_json, utc_now_iso

log = setup_logger("sol_trade.bot")


class TradingBot:
    def __init__(self, cfg: Config, feed: PriceFeed, paper: PaperEngine,
                 notifier: Notifier, live_engine=None):
        self.cfg = cfg
        self.feed = feed
        self.paper = paper
        self.notifier = notifier
        self.live = live_engine
        self.risk = RiskManager(cfg.risk)
        # Φόρτωση αποθηκευμένου ιστορικού τιμών (επιβιώνει από επανεκκινήσεις)
        self._history_path = cfg.data_dir / "price_history.json"
        saved = load_json(self._history_path, {"prices": []})
        self.prices: list[float] = [float(p) for p in saved.get("prices", [])]
        self.prices = self.prices[-cfg.trading.history_size:]
        self._backfill_history()

    def _backfill_history(self) -> None:
        """Αν το ιστορικό δεν φτάνει για τους δείκτες, το γεμίζουμε από CoinGecko.

        Η στρατηγική θέλει max(ema_slow, rsi_period+2)+2 τιμές (για EMA26/RSI14
        = 28). Με ωριαίο tick αυτό σημαίνει μια ολόκληρη μέρα αναμονή — το
        δωρεάν CoinGecko δίνει τις ωριαίες τιμές των τελευταίων ημερών και το
        bot γίνεται «ζεστό» από την πρώτη κιόλας εκτέλεση.
        """
        s = self.cfg.strategy
        min_needed = max(s.ema_slow, s.rsi_period + 2) + 2
        if len(self.prices) >= min_needed:
            return
        try:
            from .backfill import fetch_hourly_prices

            hours = int(getattr(self.cfg.trading, "backfill_hours", 72))
            coin = str(getattr(self.cfg.trading, "backfill_coin_id", "solana"))
            filled = fetch_hourly_prices(hours=hours, coin_id=coin, symbol=self.cfg.token.symbol)
            if not filled:
                log.warning("Backfill: το CoinGecko δεν επέστρεψε τιμές.")
                return
            # βάζουμε τις ωριαίες τιμές ΠΡΙΝ από τις υπάρχουσες (νεότερες στο τέλος)
            self.prices = filled[:-1] + self.prices
            self.prices = self.prices[-self.cfg.trading.history_size:]
            self._persist_prices()
            log.info("Backfill: +%d ωριαίες τιμές → ιστορικό τώρα %d σημεία (=%s)",
                     len(filled) - 1, len(self.prices), coin)
        except Exception as e:  # noqa: BLE001 — το backfill είναι προαιρετικό
            log.warning("Backfill απέτυχε (συνεχίζουμε κανονικά): %s", e)

    def _persist_prices(self) -> None:
        save_json(self._history_path, {"prices": self.prices})

    # ---------------------------------------------------- ΒΡΟΧΟΣ
    def run(self, once: bool = False) -> None:
        mode = self.cfg.mode
        log.info("=== sol_trade ξεκίνησε | mode=%s | token=%s | feed=%s ===",
                 mode.upper(), self.cfg.token.symbol, self.feed.label)
        self.notifier.send(
            f"<b>sol_trade ξεκίνησε</b>\nΛειτουργία: {mode.upper()} | Token: {self.cfg.token.symbol} | Feed: {self.feed.label}"
        )

        try:
            while True:
                try:
                    self.tick()
                except KeyboardInterrupt:
                    raise
                except Exception as e:  # noqa: BLE001
                    # Προσωρινά σφάλματα δικτύου/API δεν σταματούν το bot
                    log.error("Σφάλμα στο tick (συνέχεια σε %ds): %s",
                              self.cfg.trading.poll_interval_sec, e)
                if once:
                    break
                time.sleep(self.cfg.trading.poll_interval_sec)
        except KeyboardInterrupt:
            log.info("Διακοπή από τον χρήστη (Ctrl+C)")
        finally:
            price = self.prices[-1] if self.prices else 0.0
            log.info("=== Σύνοψη ===\n%s", self.paper.summary(price or None))
            self.notifier.send(f"sol_trade σταμάτησε.\n{self.paper.summary(price or None)}")

    # ---------------------------------------------------- ΕΝΑ ΒΗΜΑ
    def tick(self) -> None:
        cfg = self.cfg
        price = self.feed.next_price()
        self.prices.append(price)
        if len(self.prices) > cfg.trading.history_size:
            self.prices = self.prices[-cfg.trading.history_size:]
        self._persist_prices()

        signal = evaluate(self.prices, cfg.strategy, self.paper.position is not None)

        ind = signal.indicators
        ind_str = ""
        if ind.get("rsi") is not None:
            ind_str = (f" | EMA{cfg.strategy.ema_fast}={ind['ema_fast']:.4f} "
                       f"EMA{cfg.strategy.ema_slow}={ind['ema_slow']:.4f} RSI={ind['rsi']}")
        log.info("Τιμή %s: %.4f USD | equity %s | trades σήμερα: %d%s",
                 cfg.token.symbol, price, fmt_usd(self.paper.equity(price)),
                 self.risk.daily_trades, ind_str)

        if self.paper.position is not None:
            exit_decision = self.risk.check_exit(self.paper.position, price)
            if exit_decision.allowed:
                self._close_position(price, exit_decision.reason)
                return

        if signal.kind == "BUY":
            decision = self.risk.check_entry(price, self.paper.position, self.paper.cash_usd)
            if decision.allowed:
                self._open_position(signal)
            else:
                log.info("BUY απορρίφθηκε: %s", decision.reason)
        elif signal.kind == "SELL" and self.paper.position is not None:
            self._close_position(price, signal.reason)

    # ---------------------------------------------------- ΕΚΤΕΛΕΣΕΙΣ
    def _open_position(self, signal) -> None:
        if self.cfg.mode == "live" and self.live is not None:
            # LIVE: το USDC σε USD είναι πρακτικά 1.00 (stablecoin)
            quote_price = 1.0
            try:
                record = self.live.buy(signal, quote_price, self.risk)
                # Καταγραφή θέσης για παρακολούθηση stop-loss/TP (χωρίς κινήσεις μετρητών)
                self.paper.position = Position(
                    entry_price=record["entry_price"],
                    size_token=record["size_token"],
                    size_usd=record["size_usd"],
                    opened_at=utc_now_iso(),
                )
                self.paper.persist()
                self.notifier.notify_trade(
                    "BUY", f"{self.cfg.token.symbol} @ {signal.price:.4f}\nΑιτία: {signal.reason}\nΣυναλλαγή: {record['signature'][:16]}...",
                    "live",
                )
            except Exception as e:  # noqa: BLE001
                log.error("LIVE BUY απέτυχε: %s", e)
                self.notifier.send(f"LIVE BUY απέτυχε: {e}")
            return

        if self.paper.buy(signal, self.risk):
            self.notifier.notify_trade(
                "BUY",
                f"{self.cfg.token.symbol} @ {signal.price:.4f} USD\nΑιτία: {signal.reason}\n"
                f"Ποσό: {self.cfg.risk.trade_amount_usd:.2f} USD",
                "paper",
            )

    def _close_position(self, price: float, reason: str) -> None:
        if self.cfg.mode == "live" and self.live is not None and self.paper.position is not None:
            try:
                record = self.live.sell(self.paper.position, reason, self.risk)
                self.notifier.notify_trade(
                    "SELL", f"{self.cfg.token.symbol} @ {price:.4f}\nΑιτία: {reason}\nΣυναλλαγή: {record['signature'][:16]}...",
                    "live",
                )
            except Exception as e:  # noqa: BLE001
                log.error("LIVE SELL απέτυχε: %s", e)
                self.notifier.send(f"LIVE SELL απέτυχε: {e}")
            self.paper.position = None
            self.paper.persist()
            return

        trade = self.paper.sell(price, reason, self.risk)
        if trade:
            self.notifier.notify_trade(
                "SELL",
                f"{self.cfg.token.symbol} έξοδος @ {trade['exit_price']:.4f}\nΑιτία: {reason}\n"
                f"PnL: {trade['pnl_usd']:+.2f} USD ({trade['pnl_pct']:+.2f}%)",
                "paper",
            )
