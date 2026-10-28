# Economic calendar

Aurum reads the **official Forex Factory weekly JSON export**, linked from
[Forex Factory's calendar](https://www.forexfactory.com/calendar). No API account or
calendar credential is required. This is a cached weekly schedule, not a real-time
release-news service or an inferred prediction of gold direction.

`CALENDAR_PROVIDER=forex_factory` is enabled in this workspace. It refreshes hourly
(`CALENDAR_REFRESH_SECONDS=3600`, minimum 900 seconds). The source is contacted by
one backend task, not by every browser. **Check refresh** honors the same throttle;
it does not repeatedly hammer the source. Disable with `CALENDAR_PROVIDER=none`.

The view defaults to USD/upcoming events in **Malaysia time (MYT)**. Currency, impact,
period and UTC/MYT filters are available. The Overview card shows the next USD events.
Change Period to **This week** to include earlier events. The source export covers
this week only; no future-week data is invented.

Event timestamps include the provider's explicit timezone offset and are normalized
to UTC internally. Holiday events show an all-day date. Impact, forecast and previous
values come from the export. Actual release values are **not** inferred: this export
may omit them, so unavailable actual values remain “—”. Event times can change.

The last valid calendar is cached in the database. Fetch failures retain that data
with a clear stale/error message. Old-week data is flagged, never labeled a current
complete schedule. Currency/impact/time parsing rejects malformed documents rather
than silently dropping individual risks. The provider and source link are shown in
both the API and UI. This integration does not block, suppress or alter signal rules.
Calendar reminders over Telegram are not enabled.

API: `GET /api/news` and the `news` section of the dashboard WebSocket snapshot.
`POST /api/news/refresh` is restricted to the configured dashboard origins and uses
the shared refresh throttle. No generated economic events or news sentiment are used.
