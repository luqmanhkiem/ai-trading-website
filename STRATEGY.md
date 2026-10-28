# Current strategy: Aurum confirmation v5

The active rules are documented in [REFERENCE_RULES.md](REFERENCE_RULES.md). The previous strategy description below is retained as historical documentation; it is not used for new signals.

---

# Aurum zone desk v4 — targets from risk

Current strategy ID: `supply-demand-rr-v4`.

New setups use **TP1=1R, TP2=2R, TP3=3R**. R is the absolute distance between
actual observed entry and the original zone stop. BUY adds these multiples to
entry; SELL subtracts them. Stop placement remains beyond the supply/demand zone.

Before entry, displayed targets use the zone midpoint as a reference. On the first
subsequent eligible executable quote inside the zone, all three target prices
recalculate using that actual fill and the unchanged stop. They then remain fixed.
For BUY at 4200 with stop 4195: targets 4205 / 4210 / 4215. For SELL at 4200 with
stop 4205: targets 4195 / 4190 / 4185. Prices round to two decimals.

There is no minimum reward/risk entry filter: the target formula itself is 1/2/3R.
Opposing structure is now context only; it does not cap targets. Relative risk labels
still consider strict/weak base quality, retests, structure alignment and available
room to opposing structure relative to reference stop distance. They do not treat
the planned 3R target as proof of a safe trade or a probability of winning. Unknown
structure room is explicitly labeled and graded High.

BUY fills use ask and SELL fills use bid; exits use the opposite side. A pre-entry
stop boundary break invalidates the setup; touching a projected target before entry
does not. TP1/TP2 remain milestones, not partial executions. The whole paper
position exits at TP3 or the original stop. Adverse quote gaps can realize worse
than -1R; cent rounding and costs mean executable results may differ from nominal R.
Same-quote entry and exit is not allowed. No automatic broker orders are placed.

The inclusive zone detector, six-zone-per-timeframe limit, absence of a daily quota,
49-bar expiry, analysis desk, data-source behavior, economic calendar and private
Telegram configuration remain in place. [Analysis desk / prior structure-target
rules](STRATEGY_V3.md) documents the tools and preserved v3 behavior.

Old records keep their version-specific rules and levels. Legacy structure/fixed-pip
setups are not converted to R targets. Current dashboard metrics filter to v4 and
selected profile; the full journal/CSV retains all versions. Restart/feed gaps still
mark active tracking DATA_GAP without guessing an outcome.
