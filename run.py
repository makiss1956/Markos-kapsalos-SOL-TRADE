#!/usr/bin/env python3
"""sol_trade — Trading bot για Solana (Jupiter API).

Εντολές:
  python run.py trade                 # τρέχει το bot (paper mode προεπιλογή)
  python run.py trade --live          # ΠΡΑΓΜΑΤΙΚΕΣ συναλλαγές (προσοχή!)
  python run.py trade --once          # ένα μόνο βήμα και έξοδος
  python run.py trade --offline       # συνθετικές τιμές, χωρίς internet
  python run.py backtest --days 30    # backtest σε συνθετικά δεδομένα
  python run.py backtest --csv data/prices.csv
  python run.py status                # κατάσταση paper λογαριασμού
  python run.py reset                 # μηδενισμός paper λογαριασμού
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sol_trade.backtest import export_trades_csv, load_csv_prices, run_backtest, synthetic_prices
from sol_trade.bot import TradingBot
from sol_trade.config import load_config
from sol_trade.data_feed import make_feed
from sol_trade.jupiter_client import JupiterClient
from sol_trade.live_engine import LiveEngine
from sol_trade.logger import setup_logger
from sol_trade.notifier import Notifier
from sol_trade.paper_engine import PaperEngine
from sol_trade.utils import load_json

log = setup_logger("sol_trade")


def cmd_trade(args: argparse.Namespace) -> int:
    overrides = {"mode": "live" if args.live else None}
    cfg = load_config(overrides=overrides)

    if cfg.mode == "live":
        print("=" * 60)
        print("ΠΡΟΣΟΧΗ: LIVE MODE — ΠΡΑΓΜΑΤΙΚΕΣ ΣΥΝΑΛΛΑΓΕΣ ΜΕ ΠΡΑΓΜΑΤΙΚΑ ΚΕΦΑΛΑΙΑ")
        print("Βεβαιωθείτε ότι το πορτοφόλι έχει USDC (για αγορές) και SOL (για fees).")
        print("=" * 60)
        if args.yes is False:
            reply = input("Συνέχεια; (γράψτε YES για επιβεβαίωση): ").strip()
            if reply != "YES":
                print("Ακυρώθηκε.")
                return 1

    feed = make_feed(cfg, offline=args.offline, seed=args.seed)
    paper = PaperEngine(cfg)
    notifier = Notifier(cfg)
    live_engine = None
    if cfg.mode == "live":
        live_engine = LiveEngine(cfg)  # κάνει validation keys και ρίχνει λάθος αν λείπουν

    bot = TradingBot(cfg, feed, paper, notifier, live_engine=live_engine)
    bot.run(once=args.once)
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    cfg = load_config()
    if args.csv:
        prices = load_csv_prices(Path(args.csv))
        source = f"CSV: {args.csv}"
    else:
        prices = synthetic_prices(days=args.days, seed=args.seed)
        source = f"συνθετικά δεδομένα {args.days} ημερών (seed={args.seed})"

    print(f"=== Backtest | {source} | {len(prices)} σημεία ===")
    print(f"Στρατηγική: EMA {cfg.strategy.ema_fast}/{cfg.strategy.ema_slow} + RSI {cfg.strategy.rsi_period}")
    print(f"Risk: amount={cfg.risk.trade_amount_usd} USD, SL={cfg.risk.stop_loss_pct}%, "
          f"TP={cfg.risk.take_profit_pct}%, trailing={cfg.risk.trailing_stop_pct}%\n")

    result = run_backtest(cfg, prices)

    if args.export:
        out = Path(args.export)
        export_trades_csv(result, out)
        print(f"\nΟι συναλλαγές αποθηκεύτηκαν: {out}")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    cfg = load_config()
    state_path = cfg.data_dir / "paper_state.json"
    state = load_json(state_path, {})
    if not state:
        print("Δεν υπάρχει αποθηκευμένη κατάσταση — τρέξτε πρώτα «python run.py trade».")
        return 0

    print("=== sol_trade — κατάσταση paper λογαριασμού ===")
    print(f"Ξεκίνησε:  {state.get('started_at', '?')}")
    print(f"Μετρητά:   {state.get('cash_usd', 0):,.2f} USD")
    pos = state.get("position")
    if pos:
        print(f"Θέση:      {pos['size_token']:.6f} {cfg.token.symbol} @ {pos['entry_price']:.4f} "
              f"(ανοίχτηκε {pos['opened_at']})")
    else:
        print("Θέση:      καμία")
    trades = state.get("trades", [])
    wins = [t for t in trades if t.get("pnl_usd", 0) > 0]
    total_pnl = sum(t.get("pnl_usd", 0) for t in trades)
    print(f"Trades:    {len(trades)} συνολικά ({len(wins)} κερδοφόρα) | realized PnL: {total_pnl:+,.2f} USD")
    if trades:
        print("\nΤελευταίες συναλλαγές:")
        for t in trades[-5:]:
            print(f"  {t.get('closed_at', '?')} | {t.get('entry_price')} -> {t.get('exit_price')} "
                  f"| {t.get('pnl_usd', 0):+,.2f} USD | {t.get('reason', '')}")
    return 0


def cmd_reset(_args: argparse.Namespace) -> int:
    cfg = load_config()
    PaperEngine(cfg).reset()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sol_trade",
        description="Trading bot για Solana μέσω Jupiter API (paper & live mode)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Εντολές:")[1] if "Εντολές:" in __doc__ else None,
    )
    sub = parser.add_subparsers(dest="command")

    p_trade = sub.add_parser("trade", help="τρέχει το trading bot")
    p_trade.add_argument("--live", action="store_true", help="πραγματικές συναλλαγές (ΠΡΟΣΟΧΗ)")
    p_trade.add_argument("--once", action="store_true", help="ένα μόνο βήμα και έξοδος")
    p_trade.add_argument("--offline", action="store_true", help="συνθετικές τιμές χωρίς internet")
    p_trade.add_argument("--seed", type=int, default=None, help="seed για συνθετικά δεδομένα")
    p_trade.add_argument("--yes", action="store_true", help="παράλειψη επιβεβαίωσης στο live mode")

    p_bt = sub.add_parser("backtest", help="δοκιμή στρατηγικής σε ιστορικά δεδομένα")
    p_bt.add_argument("--csv", type=str, default=None, help="CSV αρχείο (timestamp,price)")
    p_bt.add_argument("--days", type=int, default=30, help="ημέρες συνθετικών δεδομένων (default 30)")
    p_bt.add_argument("--seed", type=int, default=42, help="seed για συνθετικά δεδομένα")
    p_bt.add_argument("--export", type=str, default=None, help="αποθήκευση trades σε CSV αρχείο")

    sub.add_parser("status", help="κατάσταση paper λογαριασμού")
    sub.add_parser("reset", help="μηδενισμός paper λογαριασμού")

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
