#!/usr/bin/env python3
"""sol_trade — Multi-token CLI (με patch για tokens.yaml).

Εντολές:
  python run.py trade --token SOL         # τρέχει το bot για SOL
  python run.py trade --once --token BONK # ένα βήμα μόνο, BONK
  python run.py trade --live --token JUP   # ΠΡΑΓΜΑΤΙΚΕΣ συναλλαγές JUP
  python run.py trade --offline           # συνθετικές τιμές χωρίς internet
  python run.py status --all              # σύνοψη όλων των tokens
  python run.py status --token WBTC       # σύνοψη μόνο WBTC
  python run.py reset --token BONK        # μηδενισμός paper state BONK
  python run.py backtest --token SOL --days 90  # backtest για SOL
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sol_trade.backtest import (
    export_trades_csv, load_csv_prices, run_backtest, synthetic_prices,
)
from sol_trade.bot import TradingBot
from sol_trade.config import (
    load_config, load_tokens, token_state_path, token_history_path,
)
from sol_trade.data_feed import make_feed
from sol_trade.live_engine import LiveEngine
from sol_trade.logger import setup_logger
from sol_trade.notifier import Notifier
from sol_trade.paper_engine import PaperEngine
from sol_trade.utils import load_json

log = setup_logger("sol_trade")


def apply_token_override(cfg, token_sym: str):
    """Αντικαθιστά token/quote/backfill_coin_id/risk με βάση tokens.yaml."""
    tokens = load_tokens()
    if token_sym.upper() not in tokens:
        raise SystemExit(
            f"Token {token_sym} δεν υπάρχει στο tokens.yaml. "
            f"Διαθέσιμα: {list(tokens.keys())}"
        )
    t = tokens[token_sym.upper()]
    cfg.token.mint = t["mint"]
    cfg.token.symbol = t["symbol"]
    cfg.token.decimals = t["decimals"]
    cfg.trading.backfill_coin_id = t.get("coingecko_id", "solana")
    if "risk" in t:  # override specific risk values
        for k, v in t["risk"].items():
            setattr(cfg.risk, k, v)
    return cfg


def cmd_trade(args: argparse.Namespace) -> int:
    overrides = {"mode": "live" if args.live else None}
    cfg = load_config(overrides=overrides)
    if args.token:
        cfg = apply_token_override(cfg, args.token)

    if cfg.mode == "live":
        print("=" * 60)
        print("ΠΡΟΣΟΧΗ: LIVE MODE — ΠΡΑΓΜΑΤΙΚΕΣ ΣΥΝΑΛΛΑΓΕΣ ΜΕ ΠΡΑΓΜΑΤΙΚΑ ΚΕΦΑΛΑΙΑ")
        print(f"Token: {cfg.token.symbol} | Ποσό ανά trade: {cfg.risk.trade_amount_usd} USD")
        print("=" * 60)
        if not args.yes:
            reply = input("Συνέχεια; (γράψτε YES για επιβεβαίωση): ").strip()
            if reply != "YES":
                print("Ακυρώθηκε.")
                return 1

    feed = make_feed(cfg, offline=args.offline, seed=args.seed)
    state_path = token_state_path(cfg.token.symbol, cfg.data_dir)
    paper = PaperEngine(cfg, state_path=state_path)
    notifier = Notifier(cfg)
    live_engine = None
    if cfg.mode == "live":
        live_engine = LiveEngine(cfg)

    bot = TradingBot(cfg, feed, paper, notifier, live_engine=live_engine)
    bot.run(once=args.once)
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    cfg = load_config()
    if args.token:
        cfg = apply_token_override(cfg, args.token)
    if args.csv:
        prices = load_csv_prices(Path(args.csv))
        source = f"CSV: {args.csv}"
    else:
        prices = synthetic_prices(days=args.days, seed=args.seed)
        source = f"συνθετικά {args.days} ημερών (seed={args.seed})"

    print(f"=== Backtest | {source} | {len(prices)} σημεία | token={cfg.token.symbol} ===")
    print(f"Στρατηγική: EMA {cfg.strategy.ema_fast}/{cfg.strategy.ema_slow} + RSI {cfg.strategy.rsi_period}")
    print(f"Risk: amount={cfg.risk.trade_amount_usd} USD, SL={cfg.risk.stop_loss_pct}%, "
          f"TP={cfg.risk.take_profit_pct}%, trailing={cfg.risk.trailing_stop_pct}%\n")

    result = run_backtest(cfg, prices)

    if args.export:
        out = Path(args.export)
        export_trades_csv(result, out)
        print(f"\nΟι συναλλαγές αποθηκεύτηκαν: {out}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    cfg = load_config()
    tokens = load_tokens()
    if not args.all and not args.token:
        args.token = "SOL"  # default behavior

    targets = [args.token] if args.token else list(tokens.keys())
    print("=== sol_trade — κατάσταση paper λογαριασμού ===")
    for sym in targets:
        if sym.upper() not in tokens:
            print(f"\n[{sym}] ΔΕΝ υπάρχει στο tokens.yaml")
            continue
        state_path = token_state_path(sym, cfg.data_dir)
        state = load_json(state_path, {})
        if not state:
            print(f"\n[{sym}]  Δεν υπάρχει paper state ακόμα "
                  f"(κανένα trade δεν έχει εκτελεστεί)")
            continue
        trades = state.get("trades", [])
        wins = [t for t in trades if t.get("pnl_usd", 0) > 0]
        pnl = sum(t.get("pnl_usd", 0) for t in trades)
        print(f"\n[{sym}]  cash: {state.get('cash_usd', 0):.2f} | "
              f"trades: {len(trades)} ({len(wins)} win) | "
              f"PnL: {pnl:+.2f} USD")
        pos = state.get("position")
        if pos:
            print(f"  θέση: {pos['size_token']:.4f} {sym} @ "
                  f"{pos['entry_price']:.4f}")
        if trades:
            print("  τελευταία trades:")
            for t in trades[-3:]:
                print(f"    {t.get('closed_at', '?')[:16]} | "
                      f"{t.get('pnl_usd', 0):+.2f} USD | {t.get('reason', '')}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    cfg = load_config()
    if args.token:
        cfg = apply_token_override(cfg, args.token)
    state_path = token_state_path(cfg.token.symbol, cfg.data_dir)
    PaperEngine(cfg, state_path=state_path).reset()
    print(f"Reset paper state για {cfg.token.symbol}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sol_trade",
        description="Trading bot για Solana μέσω Jupiter API (paper & live mode, multi-token)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Εντολές:")[1] if "Εντολές:" in __doc__ else None,
    )
    sub = parser.add_subparsers(dest="command")

    p_trade = sub.add_parser("trade", help="τρέχει το trading bot")
    p_trade.add_argument("--token", type=str, default=None,
                         help="Token symbol από tokens.yaml (π.χ. SOL, BONK, JUP)")
    p_trade.add_argument("--live", action="store_true", help="πραγματικές συναλλαγές (ΠΡΟΣΟΧΗ)")
    p_trade.add_argument("--once", action="store_true", help="ένα μόνο βήμα και έξοδος")
    p_trade.add_argument("--offline", action="store_true", help="συνθετικές τιμές χωρίς internet")
    p_trade.add_argument("--seed", type=int, default=None, help="seed για συνθετικά δεδομένα")
    p_trade.add_argument("--yes", action="store_true", help="παράλειψη επιβεβαίωσης στο live mode")

    p_bt = sub.add_parser("backtest", help="δοκιμή στρατηγικής σε ιστορικά δεδομένα")
    p_bt.add_argument("--token", type=str, default=None, help="Token symbol από tokens.yaml")
    p_bt.add_argument("--csv", type=str, default=None, help="CSV αρχείο (timestamp,price)")
    p_bt.add_argument("--days", type=int, default=30, help="ημέρες συνθετικών δεδομένων (default 30)")
    p_bt.add_argument("--seed", type=int, default=42, help="seed για συνθετικά δεδομένα")
    p_bt.add_argument("--export", type=str, default=None, help="αποθήκευση trades σε CSV αρχείο")

    p_status = sub.add_parser("status", help="κατάσταση paper λογαριασμού")
    p_status.add_argument("--all", action="store_true", help="δείξε όλα τα tokens")
    p_status.add_argument("--token", type=str, default=None, help="συγκεκριμένο token")

    p_reset = sub.add_parser("reset", help="μηδενισμός paper λογαριασμού")
    p_reset.add_argument("--token", type=str, default=None, help="συγκεκριμένο token")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "trade":
        return cmd_trade(args)
    if args.command == "backtest":
        return cmd_backtest(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "reset":
        return cmd_reset(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
