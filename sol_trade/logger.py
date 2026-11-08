"""Ρύθμιση logging σε κονσόλα και αρχείο data/bot.log."""

import logging
import sys
from pathlib import Path


def setup_logger(name: str = "sol_trade", log_dir: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:  # ήδη ρυθμισμένος
        return logger
    logger.setLevel(level)
    logger.propagate = False  # όχι διπλές γραμμές από τον γονικό logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "bot.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger
