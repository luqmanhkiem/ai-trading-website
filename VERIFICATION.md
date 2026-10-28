# Verification — 15 October 2026

- Backend: **22 tests passed** (Python 3.9.6).
- Frontend: **3 tests passed** (Vitest 4.1.12, Node 25.9.0).
- TypeScript and Vite production build: passed.
- Python dependency consistency (`pip check`): passed.
- npm audit after patched test-runner upgrade: zero vulnerabilities reported.
- Local frontend HTTP request and API health request: successful.
- Browser checks: mobile and desktop layout, live WebSocket updates, M15 switch,
  lot calculator (10,000 USD / 1% / entry 2,680 / stop 2,675 = 0.20 lots), journal
  direction filter, signal detail modal, redacted Connections page.
- Backend tests cover completed M15 buckets, buy/sell rule symmetry, flat markets,
  entry expiry, unfilled target gaps, TP milestones and TP3 exit, adverse stop gaps,
  closed-only metrics including break-even, lot rounding and invalid inputs,
  REST/WebSocket contract, SQLite persistence, origin rejection, secret redaction,
  duplicate suppression, live-mode refusal, tick persistence, storage failure rollback,
  disabled Telegram behavior and mocked Telegram payload delivery.

Not exercised: real broker quotes, external calendar data, actual Telegram delivery,
or PostgreSQL runtime. No credentials were supplied and Docker/PostgreSQL are not
installed locally. Telegram was tested with a mocked transport, not a real recipient.

The preview journal contains only outcomes produced while the simulator ran during
verification. The source archive excludes the runtime database so a fresh checkout
starts with no backfilled performance. No live trade execution is present.

## Valetax MT5 bridge update

Added the read-only MQL5 exporter, authenticated receiver, separate MT5 persistence,
source-aware UI, broker lot-spec import and private local configuration helper.
Tests cover MT5 cold start without generated prices, source/symbol checks, invalid
OHLC, freshness/future rejection, duplicate handling, closed-candle generation,
ask-side BUY entry, reconnect DATA_GAP invalidation, mode isolation, authorization,
secret redaction, required credentials, and configuration-helper behavior.

Actual Valetax connectivity and MQL5 compilation remain unverified. Native MT5 UI
automation timed out. The source file and Mac installation guide are provided;
only the user’s exact Market Watch symbol and local terminal setup can complete
that connection. Local environment is now configured for DATA_MODE=mt5 and XAUUSD.vx, with a locally generated token. The live receiver is running and correctly reports waiting for the bridge. No live quotes have been received.

Latest checks: 38 backend tests and 3 frontend tests pass; TypeScript/Vite production build passes. Browser verification confirms MT5 waiting state, exact symbol, empty quote/candle display, and separate empty MT5 performance journal.

## Direct OANDA update — 16 October 2026

The selected source is now OANDA practice, XAU_USD. Direct API polling replaces the
MT5 desktop requirement; the earlier exporter is inactive. Missing credentials leave
an empty, clearly labeled waiting state. Real OANDA access and XAU_USD eligibility are
not verified because the user does not yet have an API account/token.

52 backend tests pass, including direct-client GET-only requests, closed-candle flag
mapping, auth/rate-limit/server-error redaction, instrument availability, market closure,
invalid/fractional timestamps, fresh signal generation without backfill, bid/ask mapping,
provider/environment storage isolation and secret redaction. Frontend tests/build are
checked separately. Server Docker/Caddy definitions are provided, but not built or
deployed: Docker is not installed and no host/domain was supplied. An always-on host
is required for operation while the user's Mac is off.

Final OANDA validation: 52 backend and 3 frontend tests pass; TypeScript/Vite build succeeds. Browser confirms OANDA practice, XAU_USD, explicit missing-credentials message, empty prices and an isolated empty paper journal.

## Calendar and Telegram update — 16 October 2026

68 backend tests pass. New coverage checks calendar timezone offsets, missing actual
values, deduplication, holiday dates, strict malformed-document rejection, persistent
cache, refresh throttle and stale fallback; Telegram disabled behavior, chosen test
destination, test cooldown, error/secret redaction, dashboard-origin restrictions and
private setup persistence preserving the MT5 feed. The official live weekly calendar
export was fetched and all 111 provider events parsed successfully. No Telegram bot
credentials were supplied in chat; real Telegram delivery remains unverified. The
setup helper does not send messages. The explicit browser test button and runtime
new-signal alerts use only the privately configured destination.

Final integration checks: 68 backend tests and 3 frontend tests pass; production build succeeds. The running app loads 111 source events with stale=false, and browser verification confirms impact filtering and the MYT/UTC 8-hour conversion. Valetax XAUUSD.vxx candles continue arriving. Telegram controls correctly remain disabled until a private bot/destination is configured; no Telegram test was sent.


Scalping / Intraday update: 71 backend tests and 3 frontend tests passed; TypeScript and Vite production build passed. Intraday selection verified in the running dashboard with M15 chart and 2× ATR rules. Backend restarted; Valetax feed reconnected. New profiles preserve legacy record levels and do not backfill outcomes.


Structure + supply/demand v1 (2026-10-16): reviewed the supplied video English auto-generated transcript; implemented validated structure, full-wick zones, retests, structural stops and minimum 2.5:1 recent-extreme targets. Exact adaptations are in STRATEGY.md. 89 backend tests and 4 frontend tests pass; TypeScript and Vite production build pass. Verified both setup profiles and methodology dialog in the running mobile dashboard. Confirmed /api/config strategy ID and real MT5 ingestion HTTP 200 after restart. Legacy history is preserved and excluded from current profile dashboard metrics. No orders or Telegram test messages were sent during verification. No historical-profitability validation was performed.


Pending-cancellation fix: BUY pre-entry stop/target boundaries now use bid, SELL uses ask; fill eligibility still uses entry-side quotes. Future invalidations record distinct codes, quote, level and explicit reason. Historical records remain untouched. Regular quotes preserve the last rule-evaluation reason rather than overwriting it with synchronization text. 94 backend tests passed; TypeScript/Vite build passed.


Fixed pip zone board v2: user confirmed 1 pip=$0.10, so targets are 30/35/40 pips ($3/$3.50/$4). No minimum RR or structure-alignment gate; retested and weaker bases are included with descriptive Low/Mid/High labels (weaker bases always High). Up to six concurrent zones per timeframe; projected TP touches before entry do not invalidate; targets rebase at observed fill. 109 backend tests and 4 frontend tests passed, production TypeScript/Vite build passed. Restarted on MT5 feed; verified four real-current M5 zones in the browser with risk reasons and fixed-pip targets. No fabricated historical fills/results. Screenshot saved as aurum-fixed-pip-zones.png.


Analysis desk / structure targets v3 (2026-10-16): inspected Best Trade Logic public feature descriptions; live tool pages redirect to authentication. Implemented original multi-timeframe desk, confirmed structure, FVG mitigation, swing sweeps, overlay toggles and evidence ledgers with no proprietary ML/flow claims. New targets use opposing confirmed swings or labeled departure-leg fallback; TP3 fixed and TP1/TP2 measured from actual fill. Fixed pip generation retired; v2 regression coverage retained. 121 backend tests plus 4 frontend tests pass; TypeScript/Vite production build passes. Verified mobile navigation, M1 unavailable state, FVG ledger, overlay toggles and desktop 1440px layout on actual MT5 feed. Screenshot aurum-analysis-desk.png saved; viewport reset. Backend restarted and MT5 ingestion HTTP200 confirmed. No historical-profitability claim or automatic trading added.


Risk-multiple targets v4: TP1/2/3 use 1/2/3 times actual fill-to-original-stop distance, with reference-midpoint previews before fill. New strategy version separates metrics and preserves earlier rules. 129 backend tests plus 4 frontend tests passed; TypeScript/Vite build passed. BUY/SELL fills away from midpoint, fixed targets after fill, exact 3R exits, pre-entry stop invalidation and legacy target preservation verified. Backend restarted and live v4 setups confirmed via API.

## Aurum Edge / reference rules v5 — 21 October 2026

- Backend: 143 pytest tests pass, including explicit missing-confluence blocking, BUY/SELL reversal patterns, future-only paper fill, 2R arithmetic, consumed-zone identity and pending invalidation. Legacy bookkeeping tests explicitly inject their original scanner rather than implying old fixtures satisfy v5.
- Frontend: production TypeScript/Vite build and 4 formatting/version-isolation tests pass.
- Browser: refreshed dashboard, rule explanation, manual P&L controls and existing provider state inspected locally.
- Runtime: original SQLite database backed up to `backend/backups/before-reference-v5.db` before API restart. No provider secrets changed; no GMC files restored. Current MT5 connection is waiting for fresh bridge data; cached candles are historical and not live verification.
- Strategy edge, live v5 alerts and actual broker feed continuity have not been validated. Reference hidden rules are unavailable; see REFERENCE_RULES.md.

## Chart controls — 21 October 2026

Frontend production build and nine tests passed. In-browser checks verified Expand/Restore, candle zoom, earlier-candle navigation, price movement, reset, native wheel zoom and pointer-drag pan. Mobile expanded chart uses measured SVG dimensions to fill the viewport, and Escape restores the embedded chart. Backend code and strategy rules were unchanged by this UI update.

Price-axis interaction refinement: native browser drag verified the numeric range expanding from 4115.31–4157.35 to 4106.17–4166.49 with centre 4136.33 unchanged and 64 latest candles unchanged. Upward drag contracted the range; double-click restored automatic scale. Eleven frontend tests and the production build passed. Zone boundary styling changed, not strategy geometry or backend behavior.
