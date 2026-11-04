# sol_trade

Trading bot για Solana που διαπραγματεύεται SOL/USDC μέσω του **Jupiter API** — του μεγαλύτερου swap aggregator του Solana. Δουλεύει σε δύο λειτουργίες:

| Λειτουργία | Τι κάνει | Χρήση |
|---|---|---|
| **paper** (προεπιλογή) | Προσομοίωση συναλλαγών με εικονικά 1.000 USD, σε **πραγματικές τιμές** από το Jupiter Price API | Εξάσκηση, δοκιμή ρυθμίσεων, zero risk |
| **live** | Πραγματικές συναλλαγές μέσω Jupiter Swap API v2 με το πορτοφόλι σας | Μόνο με ποσά που μπορείτε να χάσετε |

> **ΠΡΟΕΙΔΟΠΟΙΗΣΗ:** Το trading κρυπτονομισμάτων ενέχει σημαντικό ρίσκο. Αυτό το λογισμικό παρέχεται για εκπαιδευτικούς σκοπούς και δεν συνιστά οικονομική συμβουλή. Στο live mode χρησιμοποιήστε **νέο πορτοφόλι μόνο για το bot** με μικρό ποσό.

---

## 1. Χαρακτηριστικά

- **Στρατηγική:** EMA crossover (12/26) + φίλτρο RSI (14) — αγορά σε cross-up χωρίς υπεραγορά, πώληση σε cross-down ή υπεραγορά
- **Διαχείριση ρίσκου:** Stop-loss, take-profit, trailing stop, όριο μεγέθους θέσης, ημερήσιο όριο συναλλαγών
- **Paper mode:** πλήρης προσομοίωση με fee (0,10%) και slippage (0,05%), κατάσταση που επιβιώνει από επανεκκινήσεις (`data/paper_state.json`)
- **Live mode:** real swaps μέσω Jupiter Swap API v2, υπογραφή με solders, επιβεβαίωση στο blockchain
- **Backtesting:** δοκιμή της στρατηγικής σε συνθετικά ή δικά σας CSV δεδομένα με πλήρη στατιστικά (win rate, profit factor, max drawdown, σύγκριση με buy & hold)
- **Telegram ειδοποιήσεις:** προαιρετικά, για κάθε συναλλαγή στο κινητό σας
- **Ανθεκτικότητα:** αυτόματο fallback σε συνθετικές τιμές αν πέσει το API, retry με exponential backoff, ατομική εγγραφή state

## 2. Απαιτήσεις

- Python 3.10+ (δοκιμασμένο σε 3.11/3.12)
- Internet για τις τιμές (ή `--offline` για συνθετικές)

## 3. Εγκατάσταση

```bash
# 1) Αποσυμπίεση
unzip sol_trade.zip && cd sol_trade

# 2) Εικονικό περιβάλλον (προτεινόμενο)
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# 3) Εξαρτήσεις
pip install -r requirements.txt
```

Για **paper mode** αρκούν οι βασικές εξαρτήσεις (requests, PyYAML, python-dotenv).
Το solders/solana/base58 χρειάζονται μόνο για το live mode (περιλαμβάνονται στο requirements.txt).

## 4. Ρύθμιση

```bash
cp .env.example .env
```

Ανοίξτε το `.env` και συμπληρώστε ό,τι χρειάζεστε:

| Μεταβλητή | Απαραίτητη για | Περιγραφή |
|---|---|---|
| `SOL_TRADE_MODE` | — | `paper` ή `live` |
| `SOLANA_RPC_URL` | live | RPC endpoint (δωρεάν: `https://api.mainnet-beta.solana.com`) |
| `SOL_PRIVATE_KEY` | live | Ιδιωτικό κλειδί σε Base58 ή πίνακα 64 byte |
| `JUPITER_API_KEY` | live | Δωρεάν από [developers.jup.ag/portal](https://developers.jup.ag/portal) |
| `TELEGRAM_BOT_TOKEN` | ειδοποιήσεις | Από τον @BotFather |
| `TELEGRAM_CHAT_ID` | ειδοποιήσεις | Το chat id σας (μέσω @userinfobot) |

Η στρατηγική και το ρίσκο ρυθμίζονται στο **`config.yaml`** (ποσά, stop-loss, take-profit, περίοδοι δεικτών κ.λπ.) — δείτε τα σχόλια μέσα στο αρχείο.

## 5. Χρήση

```bash
# Paper trading σε πραγματικές τιμές (default)
python run.py trade

# Ένα μόνο βήμα (χρήσιμο για τεστ)
python run.py trade --once

# Χωρίς internet — συνθετικές τιμές (SIMULATED)
python run.py trade --offline --seed 42

# ΠΡΑΓΜΑΤΙΚΕΣ ΣΥΝΑΛΛΑΓΕΣ (ζητάει πληκτρολόγηση YES)
python run.py trade --live

# Backtest 60 ημερών σε συνθετικά δεδομένα
python run.py backtest --days 60
python run.py backtest --days 60 --export data/backtest_trades.csv

# Backtest με δικά σας δεδομένα (CSV με στήλες timestamp,price)
python run.py backtest --csv data/prices.csv

# Κατάσταση / μηδενισμός paper λογαριασμού
python run.py status
python run.py reset
```

### Τι βλέπετε στη κονσόλα

```
2026-11-03 14:30:00 | INFO | Τιμή SOL: 92.9583 USD | equity $1,000.00 | trades σήμερα: 0 | EMA12=92.71 EMA26=92.84 RSI=54.3
2026-11-03 14:30:30 | INFO | PAPER BUY 0.538231 SOL @ 92.9211 | κόστος 50.00 USD | μετρητά 950.00
```

Όλα τα logs γράφονται και στο `data/bot.log`.

## 6. Πώς λειτουργεί η στρατηγική

1. Κάθε `poll_interval_sec` δευτερόλεπτα το bot τραβάει την τρέχουσα τιμή του token από το Jupiter Price API v3.
2. Κρατάει κυλιόμενη ιστορία (`history_size`) τιμών και υπολογίζει EMA12, EMA26 και RSI14.
3. **BUY** όταν η EMA12 διασχίζει πάνω από την EMA26 (φρέσκο crossover) και το RSI < 70.
4. **SELL** όταν η EMA12 διασχίζει κάτω από την EMA26, ή το RSI > 70, ή ενεργοποιηθεί stop-loss / take-profit / trailing stop.
5. Κάθε συναλλαγή καταγράφεται σε `data/paper_state.json` (paper) ή αποστέλλεται στο blockchain (live) και αποστέλλεται στο Telegram (αν ρυθμιστεί).

Παράμετροι του ρίσκου στο `config.yaml` → `risk:` — π.χ. `stop_loss_pct: 3.0` σημαίνει έξοδος με ζημιά 3%.

## 7. Δομή του έργου

```
sol_trade/
├── run.py                    # Είσοδος CLI (trade / backtest / status / reset)
├── integration_test.py       # End-to-end test με συνθετικό feed
├── config.yaml               # Ρυθμίσεις στρατηγικής & ρίσκου
├── .env.example              # Πρότυπο για κλειδιά (αντιγράψτε σε .env)
├── requirements.txt
├── sol_trade/                # Ο κώδικας του bot (Python πακέτο)
│   ├── bot.py                # Κύριος βρόχος
│   ├── config.py             # Φόρτωμα config.yaml + .env
│   ├── jupiter_client.py     # Price API v3 + Swap API v2
│   ├── data_feed.py          # Jupiter feed + συνθετικό fallback
│   ├── indicators.py         # SMA, EMA, RSI, μεταβλητότητα
│   ├── strategy.py           # Σήματα BUY/SELL/HOLD
│   ├── risk.py               # Stop-loss / TP / trailing / όρια
│   ├── paper_engine.py       # Προσομοίωση + persist state
│   ├── live_engine.py        # Πραγματικά swaps (solders)
│   ├── wallet.py             # Keypair, υπογραφή, επιβεβαίωση
│   ├── notifier.py           # Telegram
│   └── backtest.py           # Backtester + στατιστικά
├── tests/                    # 23 unit tests (pytest)
├── .github/workflows/
│   └── paper-trading.yml     # ΠΡΟΑΙΡΕΤΙΚΟ: paper tick κάθε ώρα στο GitHub Actions
├── archive/                  # Παλιά δεδομένα (από το πρώτο protoype bot)
├── docs/                     # Αναλυτικός οδηγός (PDF)
└── data/                     # bot.log, paper_state.json, price_history.json (δημιουργούνται)
```

## 8. Paper trading χωρίς ανοιχτό υπολογιστή (GitHub Actions — προαιρετικό)

Στο repo υπάρχει το `.github/workflows/paper-trading.yml`: τρέχει **ένα βήμα του bot κάθε ώρα** σε paper mode με πραγματικές τιμές, και αποθηκεύει το state πίσω στο repo, ώστε η προσομοίωση να συνεχίζεται από εκεί που έμεινε.

- **Ενεργοποίηση:** GitHub → tab **Actions** → «Paper Trading (sol_trade)» → **Enable**.
- **Telegram ειδοποιήσεις:** Settings → Secrets → προσθέστε `TELEGRAM_BOT_TOKEN` και `TELEGRAM_CHAT_ID`.
- Η κατάσταση φαίνεται πάντα στο `data/paper_state.json` και με `python run.py status` τοπικά.

> Σημείωση: η προεπιλεγμένη στρατηγική θέλει ~30 τιμές ιστορικού για να «ζεσταθούν» οι δείκτες — με ένα tick/ώρα, τα πρώτα σήματα εμφανίζονται από τη 2η ημέρα. Για πιο γρήγορα αποτελέσματα τρέχετε το bot τοπικά με `poll_interval_sec: 30`.

## 9. Tests

```bash
python -m pytest tests/ -q       # 23 tests
python integration_test.py       # πλήρης βρόχος με συνθετικές τιμές
```

## 10. Συχνές ερωτήσεις

**Δεν μου στέλνει Telegram.** Ελέγξτε ότι βάλατε και τα δύο env vars και ότι έχετε στείλει τουλάχιστον ένα μήνυμα στο bot σας πριν το τρέξετε.

**Το bot δεν ανοίγει θέσεις.** Κανονικό — περιμένει φρέσκο EMA crossover. Σε επίπεδη αγορά μπορεί να περάσουν ώρες. Δοκιμάστε `--offline` για να δείτε τη ροή με γρήγορες διακυμάνσεις, ή χαμηλώστε τα `ema_fast/ema_slow` στο config.

**Αλλάζω token.** Στο `config.yaml` αλλάξτε `token.mint`, `token.symbol`, `token.decimals` (τα mints θα βρείτε στο jup.ag αναζητώντας το token).

**Πόσο κοστίζει το live trading;** Priority fees ~0,0001–0,001 SOL ανά swap + fee/aggregator χρέωση. Βάλτε 0,05+ SOL στο πορτοφόλι για fees.

**Πώς μεταφέρω το bot σε VPS;** Αντιγράψτε το φάκελο, δημιουργήστε venv, βάλτε το `.env` και τρέξτε με `nohup python run.py trade &` ή με systemd unit (βλ. PDF οδηγίες, ενότητα 7).

## 11. Αποποίηση ευθύνης

Το λογισμικό παρέχεται «ως έχει», χωρίς εγγυήσεις. Οι κρυπταγορές είναι εξαιρετικά μεταβλητές· οι προηγούμενες αποδόσεις δεν εγγυώνται μελλοντικές. Χρησιμοποιήστε το με δική σας ευθύνη.
