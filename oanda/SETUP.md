# Direct OANDA XAUUSD data — no MT5 required

Aurum now connects directly to OANDA's v20 REST API. You can close MT5. The backend
must run on an always-on server if you want prices/signals while your Mac is off.
The included server package is ready to configure; no hosting has been purchased or
deployed. A local preview does not continue running when the Mac sleeps or turns off.

## Get API access

1. Visit OANDA's official [v20 introduction](https://developer.oanda.com/rest-live-v20/introduction/)
   and [authentication instructions](https://developer.oanda.com/rest-live-v20/authentication/).
2. Obtain an eligible **v20 fxTrade Practice** account to test the feed. Use the OANDA
   entity available to your jurisdiction; not every account/entity offers the same API
   or gold instruments. TradingView OANDA chart access alone is not API access.
3. In the eligible OANDA account portal, use **Manage API Access** to generate a personal
   access token. Record the v20 account ID from your OANDA account.
4. Confirm that the account offers **XAU_USD**. Aurum also checks this through the
   account-instruments endpoint and refuses to substitute another instrument/feed.

If the portal does not offer v20 tokens or XAU_USD, ask OANDA support about availability
for that account/entity. Do not create or fund an account on the assumption that the
TradingView chart guarantees access. No paid account or trading is required by this
app's code; provider eligibility and access conditions are OANDA's.

## Add credentials privately

The local app is already set to `DATA_MODE=oanda`, environment `practice`. Edit
`backend/.env` locally (never send its contents or the token in chat):

```dotenv
DATA_MODE=oanda
OANDA_ENVIRONMENT=practice
OANDA_API_TOKEN=your-private-token
OANDA_ACCOUNT_ID=your-v20-account-id
OANDA_INSTRUMENT=XAU_USD
OANDA_POLL_SECONDS=2
OANDA_STALE_SECONDS=15
```

Stop and restart `make dev`. Open http://127.0.0.1:5173. Until credentials are supplied,
the UI explicitly says **OANDA credentials missing** and shows no generated prices.
To use a live-account data environment later, change `OANDA_ENVIRONMENT=live` and
supply matching credentials; this does **not** enable trading. Practice and live
journals are stored separately. The API token may itself have broad account powers:
keep it server-side and revoke it in OANDA if exposed. Aurum sends only GET requests.

## What the connection does

- Checks account access to XAU_USD.
- Polls OANDA account pricing every two seconds by default, using bid/ask.
- Fetches 241 recent M5 bid candles about every 10 seconds. Closed candles require
  OANDA's `complete=true`; candle closure is never guessed from elapsed wall time.
- Builds M15 candles from completed M5 candles, and evaluates the existing rules.
- Uses WebSockets from the backend to your browser. This is REST polling upstream,
  not an every-tick OANDA streaming capture.
- Rejects stale/future/malformed quotes and duplicate/out-of-order timestamps, retries
  failures with capped exponential backoff, and never falls back to simulation.
- Keeps OANDA practice/live results separate from MT5 and simulated results.
- Uses bid/ask for paper entry and exit, not actual broker fills. Missed quotes between
  polling intervals can miss touches; paper results are not execution evidence.
- Marks active setups affected by a stale feed/restart as DATA_GAP on reconnection,
  excluding their unknown outcomes from win rate and R.

The chart uses **OANDA bid candles**. Do not assume exact equivalence with TradingView
OANDA candles; the provider's chart basis and account environment may differ. Your
manual Valetax entry/fill and spread may also differ. The lot calculator remains for
USD-account broker lots: keep **Valetax** contract size/lot constraints rather than
importing OANDA units. No automatic order execution exists.

## Run without your desktop

Use [the server deployment guide](../deploy/SERVER.md). It provides containers for
one backend worker, persistent storage and an HTTPS frontend with password protection.
You still need to choose/provision a host and domain and add your OANDA secrets there.
Nothing in the app requires a logged-in terminal or a running Mac once hosted.

## Troubleshooting

- **Credentials missing:** configure both token and v20 account ID, then restart.
- **401/403:** mismatched practice/live credentials, wrong account ID, revoked token,
  or account access restrictions. API responses are redacted from the browser.
- **XAU_USD unavailable:** your account/entity does not expose gold to this integration.
- **Market not tradeable/stale:** evaluation pauses; no synthetic prices are substituted.
- **Waiting for closed M5 candle:** the quote crossed a candle boundary before the
  candle endpoint confirmed closure. It retries rather than evaluating an incomplete bar.
- **Warm-up/session gap:** signals require enough completed contiguous candles. No
  historical signal outcomes are backfilled after downtime.

References: [OANDA environments](https://developer.oanda.com/rest-live-v20/development-guide/),
[pricing/candle endpoints](https://developer.oanda.com/rest-live-v20/pricing-ep/),
[account instruments](https://developer.oanda.com/rest-live-v20/account-ep/).
