#!/usr/bin/env python3
"""Integration test: πλήρης βρόχος bot με συνθετικό feed (χωρίς internet)."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sol_trade.config import Config, load_config
from sol_trade.data_feed import SyntheticFeed
from sol_trade.paper_engine import PaperEngine
from sol_trade.bot import TradingBot
from sol_trade.notifier import Notifier


def main() -> int:
    cfg = load_config()
    # Επιταχυνόμενο σενάριο: μικρά βήματα ώστε να εμφανιστούν σήματα γρήγορα
    with tempfile.TemporaryDirectory() as tmp:
        cfg.data_dir = Path(tmp)
        paper = PaperEngine(cfg, state_path=Path(tmp) / "paper_state.json")
        feed = SyntheticFeed(start_price=100.0, seed=11)
        bot = TradingBot(cfg, feed, paper, Notifier(cfg), live_engine=None)

        trades_before = 0
        for i in range(3000):
            bot.tick()
            if len(paper.trades) > trades_before:
                trades_before = len(paper.trades)
            if i > 60 and len(paper.trades) >= 3:
                break

        print(f"\n=== Integration test: {len(paper.trades)} trades σε {i + 1} ticks ===")
        for t in paper.trades:
            print(f"  {t['side']} @ {t.get('entry_price', t.get('exit_price'))} | "
                  f"{t['pnl_usd']:+.2f} USD | {t['reason']}")
        print(f"Μετρητά: {paper.cash_usd:.2f} USD | equity: {paper.equity(feed.next_price()):.2f} USD")

        # Έλεγχος persist/reload
        reloaded = PaperEngine(cfg, state_path=Path(tmp) / "paper_state.json")
        assert len(reloaded.trades) == len(paper.trades), "το state δεν επαναφορτώθηκε σωστά"
        assert len(paper.trades) >= 1, "δεν έγινε κανένα trade σε 3000 ticks"
        print("PASS: state persist/reload OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
