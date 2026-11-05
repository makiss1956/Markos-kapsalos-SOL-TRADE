"""Φόρτωση ρυθμίσεων από config.yaml + μεταβλητές περιβάλλοντος (.env)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class TokenCfg:
    mint: str
    symbol: str
    decimals: int


@dataclass
class StrategyCfg:
    ema_fast: int = 12
    ema_slow: int = 26
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0


@dataclass
class RiskCfg:
    trade_amount_usd: float = 50.0
    max_position_usd: float = 100.0
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 5.0
    trailing_stop_pct: float = 2.0
    max_daily_trades: int = 10


@dataclass
class TradingCfg:
    poll_interval_sec: int = 30
    history_size: int = 300
    fee_pct: float = 0.10
    slippage_pct: float = 0.05


@dataclass
class Config:
    token: TokenCfg
    quote: TokenCfg
    trading: TradingCfg
    strategy: StrategyCfg
    risk: RiskCfg
    mode: str = "paper"
    rpc_url: str = "https://api.mainnet-beta.solana.com"
    jupiter_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    private_key: str = ""
    data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data")


def load_config(config_path: str | None = None, overrides: dict | None = None) -> Config:
    """Φορτώνει το config.yaml και το .env. Το overrides υπερισχύει των αρχείων."""
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    path = Path(config_path) if config_path else PROJECT_ROOT / "config.yaml"
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    if overrides:
        for key, value in overrides.items():
            if value is None:
                continue
            section, _, sub = key.partition(".")
            if sub:
                raw.setdefault(section, {})[sub] = value
            else:
                raw[section] = value

    if not isinstance(raw, dict) or "token" not in raw or "quote" not in raw:
        raise ValueError(
            "Το config.yaml λείπει ή δεν έχει ενότητες «token» και «quote» — "
            "βεβαιωθείτε ότι τρέχετε από τον φάκελο του έργου."
        )

    cfg = Config(
        token=TokenCfg(**raw["token"]),
        quote=TokenCfg(**raw["quote"]),
        trading=TradingCfg(**raw.get("trading", {})),
        strategy=StrategyCfg(**raw.get("strategy", {})),
        risk=RiskCfg(**raw.get("risk", {})),
        mode=os.getenv("SOL_TRADE_MODE", "paper"),
        rpc_url=os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"),
        jupiter_api_key=os.getenv("JUPITER_API_KEY", ""),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        private_key=os.getenv("SOL_PRIVATE_KEY", ""),
    )

    if overrides and overrides.get("mode"):
        cfg.mode = overrides["mode"]

    if cfg.mode not in ("paper", "live"):
        raise ValueError(f"Άκυρη λειτουργία: {cfg.mode!r} (επιτρέπονται: paper, live)")
    if cfg.trading.poll_interval_sec < 5:
        raise ValueError("Το poll_interval_sec πρέπει να είναι >= 5 δευτερόλεπτα")
    return cfg
