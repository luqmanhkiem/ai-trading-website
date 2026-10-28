# Connect Valetax MT5 on this Mac (read-only)

Your desktop terminal supplies the feed. TradingView OANDA gold is a separate feed;
its prices, spreads and candle shapes need not match Valetax. The bridge never logs
into a broker, requests account balances, or places/manages orders. Your MT5 login
stays in MT5. Mobile can still be used for manual trading, but cannot run this exporter.

## 1. Match your account's actual symbol

Open desktop MT5, log in to your Valetax account yourself if necessary, and find the
exact gold symbol in Market Watch. Valetax lists suffixes such as `XAUUSD.vx`,
`XAUUSD.vxc`, `XAUUSD.vcn`, `XAUUSD.vxx`, `XAUUSD.vxb`, and `XAUUSD.vxp`.
Do not assume your account's symbol or contract size from this list.

From the Aurum project directory run (replace the example symbol):

```sh
python3 scripts/configure_mt5.py --symbol XAUUSD.vx
```

This creates a random local bridge token if absent, preserves unrelated environment
settings, and selects `DATA_MODE=mt5`. It does not send or print the token. Open
`backend/.env` privately to copy `MT5_BRIDGE_TOKEN` into the exporter input later.
Do not paste the token or broker passwords into chat.

Restart the app using `make dev` (stop any previous launcher with Ctrl+C first).
The dashboard should say **Valetax MT5 · paper signals** and **waiting for bridge**.
It will show no generated prices. Simulation and MT5 use separate database tables.

## 2. Install and compile the exporter

1. In desktop MT5 choose **File → Open Data Folder**.
2. Copy `mt5/AurumReadOnlyBridge.mq5` into that terminal's `MQL5/Experts` directory.
3. Open **MetaEditor** from MT5, open the copied file and click **Compile**.
4. Check the compile result. A compiled `.ex5` should appear beside the source.
5. Return to MT5 and refresh **Navigator → Expert Advisors** if needed.

The native MT5 app could not be controlled in this session (its UI automation timed
out), so compilation in your terminal and an actual broker-feed check remain required.
The Python receiver is tested; that does not prove terminal compilation or connectivity.

## 3. Permit only the local destination and attach

In **Tools → Options → Expert Advisors**, enable **Allow WebRequest for listed URL**
and add `http://127.0.0.1:8000`. On some Mac MT5 builds these options are under the
application's Settings menu. WebRequest requires this allowlist; it cannot run in
MT5 Strategy Tester. Use a normal chart, preferably a demo account for initial checks.

Attach **AurumReadOnlyBridge** to your exact Valetax gold chart. Inputs:

| Input | Value |
| --- | --- |
| `Endpoint` | `http://127.0.0.1:8000/api/mt5/ingest` |
| `BridgeToken` | Your locally generated `MT5_BRIDGE_TOKEN` |
| `PollSeconds` | `1` |
| `BrokerUtcOffsetMinutes` | `9999` for automatic detection; override only if confirmed incorrect |

The exporter reads M5 candles regardless of the chart timeframe. Its trade permissions
can remain disabled: this EA has no trading calls. No DLL permission is needed.
Keep the terminal and Aurum running. Do not publish this endpoint to the internet.

## 4. Verify before trusting the display

- MT5 chart comment should report successful read-only export.
- Aurum should show **Valetax MT5**, exact symbol, bid-based candles and a fresh timestamp.
- Compare bid/ask to MT5 Market Watch, not the separate TradingView OANDA chart.
- Compare the UTC candle times and OHLC to the terminal after accounting for broker
  server offset. Automatic offset detection uses `TimeTradeServer − TimeGMT`, rounded
  to 15 minutes, and depends on the Mac's correct clock/timezone. Historical DST
  offsets are not reconstructed; the bridge only supplies a short recent window.
- Use **Use broker lot specifications** to copy contract size, step and volume limits
  into the calculator. Calculator balance/risk remain your inputs and assume a USD
  account; cent-account balances may require conversion. Confirm with the broker.
- New signals wait for the next completed candle after synchronization. No old signals
  or historical performance are inferred from the warm-up data.

## Paper accounting and interruptions

Live-data mode still produces **paper signals only**. BUY entry uses observed ask,
SELL entry observed bid; exits use the opposite side. TP1/TP2 remain milestones and
TP3/stop close the full paper position. These are sampled quotes, not executable fills,
and commissions/latency remain excluded.

Quotes older than 15 seconds, future quotes, wrong symbols, non-Valetax sources,
duplicate/out-of-order timestamps and malformed candles are rejected. No simulated
fallback is generated. A feed interruption invalidates pending/open paper setups as
`DATA_GAP` on reconnection; they are excluded from win rate and R rather than assigned
invented outcomes. Restarting the backend also requires re-synchronization. After a
market-session gap, signals wait for 90 contiguous completed M5 candles (and enough
complete M15 candles), a deliberately conservative warm-up.

## Troubleshooting

- **HTTP 401:** local token differs between `.env` and EA input. Restart backend after changes.
- **HTTP 409:** backend still in simulated mode; configure MT5 and restart.
- **HTTP 422:** check exact suffix, Valetax account, quotes, UTC offset, and loaded M5 history.
- **HTTP -1 / MT5 error:** check URL allowlist, endpoint, desktop network connection,
  and that the backend is running. Some Wine/MT5 builds may require network troubleshooting.
- **Stale/market closed:** no fresh ticks means evaluation pauses. It does not mean
  a price or trade outcome should be fabricated.
- **No events:** economic calendar remains a separate unconnected stub.

References: [Valetax metals](https://valetax.com/trading-instruments/metals/),
[MQL5 WebRequest](https://www.mql5.com/en/docs/network/webrequest),
[CopyRates](https://www.mql5.com/en/docs/series/copyrates),
[SymbolInfoTick](https://www.mql5.com/en/docs/marketinformation/symbolinfotick),
[TimeGMT](https://www.mql5.com/en/docs/dateandtime/timegmt).

## Recent H1 warm-up history (bridge v1.01)

`HistoryBars` now defaults to **600 completed M5 bars plus the current candle**, within the receiver's 601-bar payload limit. The former hardcoded 240-bar window can supply only about 19–20 complete H1 aggregates and cannot satisfy the 30-H1 warm-up. 600 M5 bars normally supplies about 49–50 H1 aggregates, excluding incomplete buckets and actual gaps. History is real terminal CopyRates data; no missing bars or past signals are fabricated. The existing recent-window timezone conversion remains in use; this is not a multi-year DST reconstruction.

The source and compiled `.ex5` are included in `mt5/`. On 21 October the installed source/binary was updated and compilation verified (0 errors, 0 warnings). The already attached instance continued sending its old 240-bar window. Remove AurumReadOnlyBridge from its chart and reattach the same EA to reload v1.01. Preserve Endpoint/BridgeToken/offset settings and set HistoryBars=600. Do not remove other EAs or change any trading permissions. Verify H1 completed-bar count reaches >=30; broker history availability may limit the actual count.
