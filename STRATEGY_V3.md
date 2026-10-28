# Aurum structure desk v3

Current strategy ID: `supply-demand-structure-v3`. Fixed 30–40 pip targets are
retired for new setups at the user's request. Earlier [v1](STRATEGY_V1.md) and
[v2](STRATEGY_V2.md) records retain their original rules and levels in the journal.

## Structure-derived targets

TP3 is the nearest opposing confirmed swing **beyond the entire entry zone**:
a swing high above demand for BUY, or a swing low below supply for SELL. Swings
require two candles on each side and are considered only once both right-hand
candles close. Search uses the latest 96 available completed setup candles.
If none exists, use the completed departure-leg high/low since the zone formed,
explicitly labeled as a fallback. No target is invented when neither level exists.
Targets require sufficient separation to display three distinct cent-denominated
levels, rather than overlapping rounded targets.

Before fill, TP1/TP2 mark one-third/two-thirds of the reference midpoint-to-TP3
distance. On actual observed fill, those two milestones are measured from that
fill so they remain ahead of entry. TP3 never moves. The full paper position still
exits at TP3 or the original stop; TP1/TP2 are not partial executions. Actual
reward/risk uses actual fill-to-stop and fill-to-TP3 distances, not a fixed pip count.
No minimum reward/risk requirement has been reintroduced.

## Zones and relative risk

The inclusive v2 zone detector is retained: strict consolidation/departure zones
and weaker single-candle bases. Retested, counter-structure and unconfirmed-
structure zones remain visible. A broken stop boundary or age limit still excludes
a zone. Maximum six active current-version setups per timeframe; no daily quota.

Risk labels now use **structure-target distance / reference stop distance**, not
a fixed $4 numerator. Low requires a strict fresh base, confirmed alignment and
ratio >=1.5. Mid requires a strict aligned base, <=1 retest and ratio >=0.75. Other
intact zones are High. Weaker bases always remain High. Labels are relative
heuristics, not win probabilities or account-risk recommendations.

## Analysis desk

The original Aurum dashboard is expanded around the publicly described tool
categories at [Best Trade Logic](https://besttradelogic.com/): multi-timeframe
context, chart overlays and inspectable analysis ledgers. Its live tools redirect
to login; proprietary engines/model weights and performance could not be inspected.
This is an independent implementation, not a replica of those private algorithms.

- **Structure:** confirmed two-left/two-right swings, protected levels, continuation
  breaks and CHoCH; actual events, not made-up confidence scores.
- **Fair value gaps:** three-candle wick imbalances. Bullish gap when third low is
  above first high; bearish is the reverse. Later full wick coverage mitigates the
  gap; partial coverage is labeled. Display limited to 12 recent surviving gaps.
- **Swing sweeps:** wick beyond the latest previously confirmed swing and close
  back inside. Only already-known pivots are eligible. These are candle markers,
  not proof of stop orders, exchange liquidity or institutional positioning.
- **Timeframes:** M5, M15, M30, H1, H4 and D1 aggregate real M5 history. Each requires
  30 contiguous completed candles for a structure bias. Insufficient history is
  labeled unavailable; available candles may still be inspected as limited context.
  M1 is explicitly unsupported by the M5 bridge and never synthesized.
- **Agreement counts:** descriptive bullish/bearish/neutral/unavailable counts,
  not probabilities or mandatory entry gates. Counts do not impose a WAIT filter.
- **Chart controls:** zone, FVG, structure, sweep and pivot overlays can be toggled.
  Structure event labels and a detailed ledger allow inspection of the evidence.
- **REST/WebSocket:** `/api/analysis` and snapshot `analysis` share the same cached
  analysis. Calculations refresh when closed bars/time buckets change or OHLC is
  revised; browser connections do not initiate external provider requests.

Prices, spread, source status, economic calendar, lot calculator, Telegram and
paper journal continue using existing local services. No order-book/true order-
flow data, whale identities, trained ML, probability gauges or news forecasts are
fabricated. No automatic trading is added. Performance uses recorded paper
outcomes, before costs, and filters to current version/profile in the dashboard.
History-dependent detections are initialized from available rolling history;
no historical fills/results are inferred. Quote gaps/restarts still mark active
tracking DATA_GAP without assigning an outcome.
