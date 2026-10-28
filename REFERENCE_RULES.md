# Aurum confirmation strategy v5

On 21 October 2026 MYT, the user requested XAU Katana's disclosed rules be applied to the existing Aurum app. This is an independent rule-based implementation, not the site's private engine, AI or trained model. The access code is not stored in source.

## Observed on the reference

The dashboard monitors M15/M30/H1 and explains higher-timeframe structure/BOS, a liquidity sweep, supply/demand or mitigation zones, a pin-bar/engulfing reversal at a zone, and a stop beyond structure. Its summary displays 1:2 R:R. It does not disclose precise thresholds, grading or the full proprietary strategy. A sampled BUY record (#804) displayed a stop at the top of its entry zone; that inconsistent geometry is not copied.

## Explicit Aurum assumptions

- Existing entry profiles remain scalping M5 and intraday M15. These are Aurum choices; the sampled Katana scalping record used M15.
- 30 completed candles required per context timeframe. Entry timeframe requires a contiguous tail. Higher contexts may cross session gaps using observed complete bars only, not fabricated candles. Each latest context close must be no more than one timeframe old. Missing constituent M5 bars prevent an aggregate bar from forming.
- M15, M30 and H1 must all agree using Aurum's existing causal swing/BOS/CHoCH logic (two right bars confirm a pivot). RSI is informational on the reference; no undisclosed RSI threshold is invented here.
- Use existing intact base/displacement zones. Their exact geometry is Aurum's existing implementation, not inferred institutional orders.
- Entry timeframe sweep of a previously confirmed swing within the last 12 closed candles, after the zone was formed. Sweep direction must match the signal.
- Most recent closed candle must touch the intact zone and show directional body engulfing, or a pin bar with rejection wick >=2 body lengths and close in outer 35% of its range. Dojis do not qualify.
- Confirmation must occur after displacement. Publish a PENDING future-retest plan; never retrospectively fill its confirmation candle. A subsequent executable quote inside the zone is required.
- Stop beyond zone stop, reversal extreme and protected entry-timeframe structure, plus 10% zone-width buffer (minimum $0.01). Targets 1R/1.5R/2R rebase once at actual paper fill. TP1/2 are milestones; all out at TP3 or stop. These TP milestones are an Aurum choice based on displayed 1:2, not an exact reverse-engineering.
- Only one candidate per scan, with existing six pending/open cap per entry timeframe. A zone can be published once, not once per repeated confirmation. Pending plans cancel if higher structure alignment disappears. Filled plans retain original stop/targets.
- No AI confidence, A/A+ grading, verified accuracy or calibrated risk grade is claimed. Rule thresholds are centralized in `backend/app/reference_rules.py` Rules.
- New strategy ID `aurum-mtf-confirmation-v5`; legacy records are retained and excluded from current strategy metrics. No real order execution. Feed interruption still marks affected paper trades DATA_GAP.

## Interface

Purple/black cards, market brief, chart, multi-timeframe context, setups, history, news, lot calculator and performance. Personal P&L is a manual browser-local journal, not broker account data or Aurum paper results; clearing browser storage removes it. No access-code gate or shared reference credentials are added.

No profitability or out-of-sample validation has been performed for v5. Automated tests verify causal confirmation/blocking, stop/target arithmetic and legacy bookkeeping, not trading edge.

## Pressure evidence panel (21 October 2026)

OHLC-only descriptive proxy on M15/M30/H1. No AI zone prediction, institutional identity, accumulation confirmation or resting-order visibility is claimed. Current bridge has no tick-volume or order-book fields; these are explicitly unavailable. The panel does not change entry rules.

Central `PressureRules` assumptions: minimum 30 closed bars; 12-bar evidence window; large latest-bar displacement at least 1.5x prior 20-bar median range with body >=65% of its range; sweeps beyond previously known swings; >=2 rejections at the same previously confirmed swing, with wick >=50% of candle range; recent unfilled FVGs; existing structure bias. Counts are unweighted evidence types, not independent signals, calibrated scores or probabilities. Directional label requires >=2 same-side types and zero opposing types; otherwise inconclusive. Range compression <=70% of previous 12-bar range is descriptive only and does not establish accumulation or distribution. Disconnected/stale feeds suppress all readings. Future/open bars are excluded.

## Possible supply/demand chart areas

Chart overlays now show up to two nearest intact supply and two nearest intact demand bases from the existing displacement detector, independently of confirmed entry signals. Dashed red/green rectangles show full wick ranges with prices and retest status. Only completed candles create zones; a subsequent wick beyond the distal edge removes a zone. Lookback is 48 completed candles after displacement. These are possible reaction areas, not predictions of institutional orders or automatic entries. The Supply / demand toggle hides/shows them; active confirmed setups keep separate SL/TP overlays.
