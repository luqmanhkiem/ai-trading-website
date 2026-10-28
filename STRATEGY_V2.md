# Current strategy: SMC zones with 30–40 pip targets

Version `supply-demand-fixed-pips-v2`. This replaces the minimum-2.5:1 strategy at
the user's request. [Earlier video adaptation](STRATEGY_V1.md) remains documented
for legacy records only.

## Targets and entries

The user confirmed **1 gold pip = $0.10**, so TP1/TP2/TP3 are 30/35/40 pips,
respectively $3/$3.50/$4 in price movement. Before entry, displayed target prices
use the zone midpoint as a reference. On an observed paper fill, all three target
prices rebase to that actual fill. BUY adds the distances; SELL subtracts them.
Targets do not trail after fill. TP1 and TP2 remain milestones; the full paper
position exits at TP3 or the original stop.

Full-wick zones come from the last of three small-body consolidation candles
before a directional displacement. Bodies are <=0.6 times median range of the
preceding 14 candles; consolidation span <=2 times that median; departure body
>=1.5 times that median, closing beyond the base in its outer quarter. Structure
is based on confirmed two-left/two-right swings and protected levels, as in v1,
but is now a risk-label input rather than a required alignment filter.

Weaker one-candle bases are also included: base body <=1.2 times median range,
departure body >=1 times median range, closing beyond the base in its outer 35%.
Any candidate that fails the strict three-candle consolidation/departure pattern
is explicitly graded High regardless of reward/risk.

## Inclusive risk labels

No minimum reward/risk filter is used. Untouched, retested, unconfirmed-structure
and counter-structure zones are eligible. These relative labels are engineering
heuristics, not win probabilities, evidence of profitability or an account-risk
recommendation:

| Grade | Definition |
|---|---|
| Low | Structure-aligned, untouched, $4 target/reference-entry-to-stop ratio >=1.5 |
| Mid | Structure-aligned, at most one completed-candle retest episode, ratio >=0.75; not Low |
| High | Any other intact zone: weaker base/departure, unconfirmed/counter structure, >=2 retests, or ratio <0.75 |

Risk reasons and gross ratio appear beside each zone and in details/Telegram.
A consecutive run of candles touching the zone is one retest episode. Grades on
pending zones refresh with completed candles; grades on filled positions stay as
recorded. Position size still determines actual money at risk. A fixed pip target
can be smaller than the zone stop distance, and costs are not included in the ratio.

## Visibility and lifecycle

- M5 and M15 each scan up to six newest intact zones and can track up to six active
  current-version paper setups. No daily quota or one-active-per-timeframe gate.
- The dashboard displays all active zones for the selected profile, nearest price
  first. Its chart overlays the nearest zone; each card provides entry, stop,
  targets, grade, reasons and calculator/details buttons.
- Zones remain eligible through retests and changes of structure; their risk grade
  can rise. A previously broken stop boundary makes a zone ineligible.
- Zones expire 49 setup bars after departure. At most one paper attempt per zone;
  expiry/closed outcomes are not recreated as new trades.
- Historical candles may identify an intact zone at startup, but it is recorded
  **now** as PENDING. Only subsequent observed quotes can fill it; no historical
  entries, exits or profits are inferred.
- BUY entry uses ask and SELL entry uses bid. Zone-stop invalidation uses the exit
  side (BUY bid, SELL ask). A pending projected-TP touch does **not** invalidate it.
- TP distances rebase on actual fill. Quotes cannot fill and exit on the same tick.
- Multiple zone outcomes are independent paper observations; summed R is not a
  portfolio return. No end-of-day exit, partial exits or automatic order execution.
- Stale/restarted quote coverage still marks active records DATA_GAP without
  guessing their outcome. Prior strategies keep their original levels and rules.

Current dashboard metrics filter to this version and selected profile. The full
journal/CSV includes older versions with accurate labels. REST `/api/metrics`
remains an all-strategy aggregate for compatibility. Telegram messages state risk
and fixed-pip distances, with reference target prices clearly labeled before fill.
