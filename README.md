# Aurum — XAUUSD paper signal terminal

A working local, single-user research MVP: React + TypeScript + Tailwind, FastAPI,
SQLAlchemy, PostgreSQL or zero-setup SQLite, and same-origin WebSockets. Inspired by
the supplied dark gold-signal dashboard references, with purple accents and an
explicit separation between simulated data and live integration work.

## Run locally

Requires Node 20.19+ (or 22.12+) and Python 3.9+.

From this project directory, the quick-start commands are:

```sh
make setup
make dev
```

`make setup` installs dependencies into a project-local Python environment and uses
the frontend lockfile. `make dev` starts both services, checks readiness, and stops
both with Ctrl+C. It copies the example backend environment only if `.env` is absent,
and refuses to start if either port is occupied. Existing credentials are preserved.
For an existing Python environment, set `AURUM_PYTHON` to its Python executable.

Alternatively, use two terminals:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. API docs: http://127.0.0.1:8000/docs.
Use **one Uvicorn worker, without reload** for an uninterrupted simulator. Reload
restarts the process. SQLite stores state in `backend/aurum.db`; no database service
or account is needed. The app has no trading execution endpoints.

## Optional PostgreSQL

From the project root, run `docker compose up -d postgres`, then set the backend
`DATABASE_URL=postgresql+psycopg://aurum:local_dev_only@127.0.0.1:5432/aurum` and restart.
Set `POSTGRES_PASSWORD` and use the same value in the URL if changing the local default.
Tables are created on startup; SQLite data is **not** automatically migrated.
Changing the database creates a separate journal. PostgreSQL uses the same SQLAlchemy
models and JSON payloads. For production schema changes, add migrations first.

## Direct OANDA feed (preferred)

No MT5 terminal or desktop exporter is needed. Follow [OANDA account/token setup](oanda/SETUP.md).
Configure DATA_MODE=oanda, OANDA_ENVIRONMENT=practice, OANDA_API_TOKEN and
OANDA_ACCOUNT_ID privately in backend/.env. The account must offer XAU_USD. The local
workspace is already in OANDA mode and shows missing credentials until supplied.
The distribution's environment example keeps the original simulated default.

The direct adapter checks instrument availability, polls bid/ask and confirmed M5
candles using OANDA v20 GET endpoints, and pushes browser updates over WebSockets.
Signals remain paper only; OANDA practice and live journals are isolated from each
other, from MT5 and from simulation. TradingView access is not OANDA API access.

For operation while your Mac is off, use [the always-on server package](deploy/SERVER.md).
It supplies container definitions, persistent storage and a password-protected HTTPS
frontend. Hosting is not yet provisioned/deployed. OANDA credentials and XAU_USD access
are also unverified without your eligible account.

The earlier optional MT5 exporter remains in `mt5/` for reference, but is not used by
OANDA mode. You do not need MetaEditor or an open desktop terminal for this integration.

## What works

- Reconnecting WebSocket snapshots, feed freshness warning, M5/M15 chart, UTC timestamps.
- Closed-bar market-structure and supply/demand retest signals with explainable levels and paper lifecycle tracking.
- Persistent signal journal, direction/status filters, details and CSV export.
- Closed-trade win rate, wins/losses/break-even, expired count, net and average R.
- Server-validated USD risk calculator, adjustable oz/lot, step, min/max lots.
- Forex Factory weekly economic calendar with USD/impact/period filters, MYT/UTC times, source attribution, cache and stale state.
- Private Telegram setup helper, source-labeled new-signal alerts, and a protected, rate-limited connection-test button.
- Responsive dark UI, CSV export, no fabricated confidence or seeded performance.

## Simulation and strategy contract

`DATA_MODE=simulated` is the distribution default. `oanda` enables direct OANDA polling;
`mt5` retains the optional earlier terminal bridge;
unknown modes fail startup. There is no silent simulated fallback. Synthetic prices start at an arbitrary $2,680
and follow a seeded random walk, **not** current gold prices. The initial 240 M5
candles only warm up indicators. A setup may be created from the most recently
completed warm-up candle at startup, but no warm-up outcomes are backfilled.

Each second of wall time advances the simulation by 15 seconds by default (15×).
Both clock and acceleration are visible. Change `SIMULATION_STEP_SECONDS` and
`TICK_SECONDS`; use step 1/tick 1 for wall-clock pace. Stored candles, quote, simulated
time and signals resume across restarts. The random generator restarts from its
seed, so the future path after restart is not a deterministic continuation/replay.
Wall-time freshness is separate from simulation time.

Current rules, version `supply-demand-rr-v4`, are documented in
[Strategy and analysis tools](STRATEGY.md). New setups use TP1=1R, TP2=2R and TP3=3R,
where 1R is actual fill-to-stop distance. Before entry the target preview uses the
zone midpoint; all targets rebase once on fill, then remain fixed. TP1/TP2 remain
progress milestones; full exit is TP3 or stop. Stops remain beyond the zone. All relative-risk grades stay visible,
without a minimum reward/risk gate or daily quota.

Open **Market analysis** for multi-timeframe context, confirmed structure, FVG and
swing-sweep ledgers, and switchable overlays. M1 is unavailable with the current
M5 feed; higher timeframes require enough real completed history. No confidence
percentages, institutional identities or order-flow data are manufactured.

Legacy strategy records keep their original levels. Current metrics filter by
version/profile. Only observed quotes can fill/close paper trades; no historical
profits are backfilled. Six active current-version zones per timeframe are allowed.

Paper fills use a single synthetic price, not broker bid/ask, fees or latency. R is
not cash P&L. Separate M5/M15 setups can overlap; aggregate R is not a portfolio return.
The lot calculator assumes a USD account and dollars per ounce; confirm actual
broker contract size. Sizes round down; below-minimum risk returns zero lots. Stop
risk excludes commission, spread and slippage. Synthetic outcomes do not validate
strategy profitability.

## Integration boundaries

**Live prices:** `backend/app/oanda.py` implements direct OANDA account-instrument,
pricing and candle GET requests. Environment hosts are fixed to OANDA practice/live.
Credentials never enter the browser. Closed-candle flags, symbol, timestamps, finite
prices and sufficient history are validated. Requests time out, retry with backoff,
and display redacted errors. No simulated fallback or order requests exist.
See [OANDA setup](oanda/SETUP.md) for eligibility, data basis and sampling limitations.
The shared quote engine preserves paper entry/exit rules and DATA_GAP behavior. The
legacy MT5 receiver is disabled unless DATA_MODE=mt5.

**Calendar:** implemented with Forex Factory's official weekly export. See
[calendar behavior and configuration](CALENDAR.md). The backend refreshes hourly,
caches last valid events, labels stale/out-of-period data and normalizes source
timezones. Missing actual values remain unavailable. The UI defaults to USD/upcoming
releases in MYT with UTC and filter controls. Calendar data does not alter signal rules.

**Telegram:** see [private Telegram setup](telegram/SETUP.md). Double-click
`setup-telegram.command` on this Mac, or run `scripts/setup_telegram.py` using the
backend Python environment. It verifies a bot, discovers destinations only if asked,
preserves existing settings, and stores secrets with owner-only file permissions.
Restart Aurum and explicitly click **Connections → Send test message** to confirm.
The browser never receives token/chat ID. New paper signals include source, entry,
stop and targets. Calendar reminders remain off. No live Telegram delivery has been
verified until the user provides a bot privately and chooses the destination.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Feed/processing health and mode |
| `GET /api/snapshot` | Full dashboard state |
| `WS /api/ws` | Full snapshot each tick; browser origin allowlist |
| `GET /api/signals` | Persistent journal, newest first |
| `GET /api/metrics` | Recorded outcome metrics |
| `POST /api/calculate-lot` | Validated position sizing |
| `GET /api/news` | Cached attributed weekly calendar and freshness |
| `POST /api/news/refresh` | Origin-restricted, throttled calendar refresh |
| `POST /api/telegram/test` | Explicit, origin-restricted connection test |
| `GET /api/config` | Redacted integration status |
| `POST /api/mt5/ingest` | Authenticated read-only terminal packets in MT5 mode |

## Checks

```sh
cd backend
source .venv/bin/activate
python -m pytest -q
pip check
cd ../frontend
npm test
npm run build
```

`package-lock.json` pins frontend installs. Python requirements constrain compatible
major versions; `requirements-lock.txt` records the environment used for verification.

## Deployment limits

This MVP is intended for localhost and has no user accounts or authorization. The
included `deploy/nginx.conf` illustrates a same-origin static/API/WebSocket proxy,
not a complete hosted deployment. Add HTTPS, access control, managed secrets, backups,
migrations, pagination and a separate durable feed worker before a shared deployment.
The in-process feed must run in exactly one backend worker; multiple workers would
create competing simulations. Credentials are environment-only; never put them in
Vite variables or source control. No real OANDA/MT5 feed, calendar or Telegram delivery has
been exercised without credentials. PostgreSQL runtime verification requires Docker
or a reachable PostgreSQL instance.

Framework references: [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/),
[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/),
[Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite).

### Scalping and Intraday profiles

Use Scalping (M5) or Intraday (M15) for zone setups and current-version metrics.
Both run continuously; changing the view does not turn generation/alerts off.
The new Market analysis desk adds context without adding entry gates. Telegram
identifies target method, strategy, profile and relative-risk grade. No orders
are placed. Intraday remains the M15 profile without an automatic day-end exit.

## Aurum Edge refresh (21 October 2026)

The existing app now has a purple/black card dashboard and an independent MTF confirmation strategy inspired by XAU Katana's disclosed concepts. See [REFERENCE_RULES.md](REFERENCE_RULES.md) for observed rules, implementation assumptions, 2R targets, version isolation and limitations. This is not the reference site's proprietary AI. Personal P&L entries are saved only in this browser and remain separate from paper performance. Restart the backend after updating to activate the rules; the existing provider configuration and database are retained.

### Pip results and history reset (21 October 2026)

Signal history was cleared at the user’s request (5 simulated + 45 MT5 records); candle/feed state and credentials were preserved. Results, net/average performance and CSV exports now use signed observed fill-to-exit movement with $0.10 per pip (BUY 4200→4204 = +40 pips). Missing exit data stays unavailable. Risk multiples remain internal for target placement and compatibility, not headline performance. Existing backups are separate from active history.

### Chart controls

Charts now support Expand/Restore (Escape restores), drag/touch panning, candle zoom (+/− or mouse wheel), earlier/later candles, vertical price movement and Y-axis zoom. Scroll over the right price axis to shift the visible price range; Ctrl/Cmd+wheel there scales it. Shift+wheel pans through available history. Reset restores 64 latest candles and automatic price range. Keyboard on the chart: arrows pan, +/− zoom candles, Home resets. Navigation is limited to the observed candles already loaded; it does not fetch older broker history. Chart navigation does not change strategy rules, signal prices or results.

Price-axis drag now matches the requested chart interaction: hold the right price scale and drag up to stretch candles, or down to compress them. This changes the price span around its current centre without panning candle history. Double-click the right axis to restore auto price scaling. Dragging inside the plot still pans. Solid red supply/SELL and blue demand/BUY boundaries show Aurum’s possible zones with price-axis tags; these are not Katana’s proprietary zones.
