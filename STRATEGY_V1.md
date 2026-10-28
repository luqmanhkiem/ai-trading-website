# Structure + Supply / Demand v1

Current strategy ID: `structure-supply-demand-v1`.

Adapted from [The Only Trading Strategy You'll Ever Need](https://www.youtube.com/watch?v=_LLXjCdLSPE).
The English auto-generated transcript was reviewed. Core segments: validated market
structure 0:25–3:26; full-wick zones, entry, stop and recent-extreme target 5:41–6:44;
minimum 2.5:1 reward/risk 9:10–9:48. This implementation does not verify or adopt the
presenter's win-rate, profit-factor, or income claims.

## What the video specifies

Trade in the direction of the validated trend. A new external high validates a
pullback low; the reverse applies to bearish structure. A break of an internal,
unvalidated pivot alone does not reverse the trend. Enter a demand-zone retest in
an uptrend or a supply-zone retest in a downtrend. Mark the complete wick-to-wick
range of the consolidation candle immediately before the departure. Put the stop
beyond the zone and the target at the recent high/low. Require reward/risk >= 2.5.

## Mechanical definitions and explicit adaptations

The video uses discretionary chart reading and does not fully specify parameters.
Its live example uses M1; Aurum retains the existing M5/M15 profiles and M5 broker feed.
Aurum's following definitions are engineering choices, not an exact replication of
all discretionary entries in the video:

| Item | Aurum rule |
|---|---|
| Profiles | Scalping uses M5, Intraday uses M15; each uses its own structure and zones |
| Closed candles | At least 30 contiguous completed setup candles; no partial-bar signals |
| Swings | Strict swing high/low with two candles on either side; known only after both right-hand candles close |
| Initial bias | Close beyond a confirmed swing, with a confirmed opposite pullback after that swing |
| Bullish continuation | Close beyond the external high validates a confirmed higher pullback low; wick-only breaks do not validate it |
| Bearish continuation | Mirror rule below the external low |
| Direction change | Close beyond the protected low/high (CHoCH); the opposite extreme since that protected pivot becomes the new protective level |
| Consolidation | Three candles before departure; each body <= 0.6 times median range of the 14 pre-departure candles; combined range <= 2 times that median |
| Displacement | Body >= 1.5 times that median; close beyond the consolidation and in the outer 25% of the departure candle in the direction of the move |
| Zone | Last consolidation candle's full low-to-high wick range, rounded to two decimals |
| Freshness | No subsequent completed candle touches or gaps beyond the near edge; no intervening direction change; departure no older than 12 bars |
| Stop | 10% of zone width beyond the far edge, minimum $0.01 buffer |
| Reference entry | Zone midpoint; actual fills use the first later executable quote inside the zone |
| TP3 | Highest completed high since bullish departure, or lowest completed low since bearish departure, known at creation and then frozen |
| TP1 / TP2 | One-third / two-thirds of the reference-entry-to-TP3 distance; milestones only, not fixed 1R/2R |
| Reward/risk | At least 2.5:1 at the least favorable edge of the entire entry zone; checked again against actual fill price |
| Limits | One active setup per timeframe; one recorded setup per zone, including after expiry or restart |
| Expiry | Three setup bars after creation: 15 minutes Scalping, 45 minutes Intraday |
| Pending invalidation | Closed structure changes, or exit-side executable price reaches stop/TP3 before entry (bid for BUY, ask for SELL) |
| Filled exits | Full position at TP3 or original stop; no partial exits, trailing stop, or time/end-of-day cutoff |

Unlike some repeated entries demonstrated in the video, Aurum uses only fresh,
unused zones. It does not require liquidity sweeps, fair value gaps, session windows,
or an extra lower-timeframe entry confirmation. These would be different strategy
versions. There is no EMA or ATR filter in the current engine. Range statistics
only make consolidation and departure strength deterministic.

Signals represent **zones awaiting a future retest**, not instructions that an entry
has already filled. A broker spread can prevent an executable entry even when the
bid candle appears to touch the zone. BUY fills use ask and SELL fills use bid;
exits use the opposite side. A quote cannot both fill and close a position.

## Data, migration and performance

The existing MT5/OANDA adapters and private Telegram settings are retained. No EA
change is required. New alerts include strategy ID, profile, entry zone, stop and
TP1–TP3. No orders are placed. Startup uses history to warm up structure but never
creates backfilled trades; live evaluation begins on a newly completed candle.

Existing breakout records retain their original entry, stop, targets and outcomes.
They remain in Signal history and CSV labeled Legacy breakout. Current dashboard
metrics use only this strategy and the selected profile. An existing active legacy
setup continues under its original rules and blocks overlapping setups on that
timeframe. Restart/feed interruption still marks active records DATA_GAP rather
than guessing their outcome. No database rows are erased or relabeled.

REST `/api/metrics` and the snapshot's top-level `metrics` retain their historical,
all-strategy aggregation for compatibility. The browser explicitly filters by
strategy ID and profile before computing its displayed summary. CSV includes
strategy, profile, zone type, and planned worst-edge reward/risk for inspection.

Historical bars initialize detection; they are not a backtest. Structure is replayed
from the available rolling history, so insufficient history can leave bias unknown.
Missing sessions require a new contiguous warm-up. TP1/TP2 hits are recorded only
from observed quotes, never inferred from OHLC bars. Commission, financing and real
execution latency are not modeled; paper results do not establish profitability.
The strategy has not been validated on XAUUSD out of sample.

## Validation

Tests cover bullish/bearish zones, wick boundaries, protected vs internal swings,
continuation validation, delayed pivot confirmation, incomplete candles, future-data
exclusion, insufficient reward/risk, previously touched zones, pre-entry invalidation,
actual-fill reward/risk, structural cancellation, legacy preservation, session gaps,
persistent consumed-zone deduplication, provider ingestion and strategy metric isolation.
