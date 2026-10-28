# Telegram setup for Aurum

The bot sends new **paper-signal** alerts containing direction, timeframe, entry zone,
stop and TP1–TP3. The source is always identified (simulated, Valetax MT5 or OANDA).
No trading orders are sent. Calendar-event reminders are not enabled in this version.

## Create your bot in Telegram

1. Open the official [@BotFather](https://t.me/BotFather) account in Telegram.
2. Send `/newbot` and follow its prompts for a display name and unique bot username.
3. BotFather returns a bot token. Treat it like a password; do not paste it into this
   chat or include it in screenshots, browser URLs or source code.
4. Open your new bot's chat and press **Start**, or send `/start`.

## Enter the token privately on this Mac

In Finder, open the Aurum project folder and double-click `setup-telegram.command`.
Terminal will prompt for the token with input hidden: paste it and press Return.
Nothing appearing while you type/paste is normal.

The helper verifies the bot with Telegram. Leave the chat ID blank to discover recent
bot chats, then choose **your intended destination** by its displayed number. It shows
chat labels/IDs but never displays incoming message contents. Alternatively, enter
an existing chat ID or a channel username. For channels, add the bot with permission
to post first. Do not choose a chat you do not intend to notify.

The helper saves the token/chat ID privately to `backend/.env` (owner-readable only),
enables notifications, and preserves your MT5 symbol, feed settings and other secrets.
**It does not send a message.** It also never changes an existing Telegram webhook;
use a separate bot if discovery conflicts with an existing integration.

If opening the helper is blocked by macOS, use your already-created Python environment
in Terminal from the Aurum project folder:

```sh
backend/.venv/bin/python scripts/setup_telegram.py
```

For this existing Codex workspace, dependencies currently live in `../../work/venv`;
the double-click helper detects that location automatically. In a new checkout run
`make setup` first to create `backend/.venv`.

## Verify delivery

Restart Aurum after the helper saves settings. In **Connections → Telegram alerts**,
click **Send test message**. This explicitly sends one connection-test message to the
saved destination. The dashboard shows success or a redacted failure. It limits test
attempts to one every 15 seconds. No token or chat ID is returned to the browser.

New runtime setups then notify automatically. Startup synchronization does not replay
old signals. TP1/TP2 are milestones; the test is not a trade or an outcome. Runtime
notification delivery is best-effort, with status visible in Connections, not a durable
retry queue. Delivery failures do not create performance records.

## Troubleshooting

- **No chats found:** open your bot and send `/start`, then rerun the helper.
- **Invalid/revoked token:** generate a replacement through BotFather and rerun setup.
- **Forbidden/access denied:** you may have blocked the bot, omitted `/start`, or not
  granted posting permission for the destination channel.
- **Existing webhook:** enter a known destination or use a separate bot; this helper
  will not delete another integration's webhook.
- **Configured but no signals:** use the test button first; real alerts require a new
  signal meeting the strategy rules. An empty signal journal is not a bot failure.
- **Disable alerts:** set `TELEGRAM_ENABLED=false` in `backend/.env` and restart.

Reference: [Telegram Bot API](https://core.telegram.org/bots/api),
[official bot creation tutorial](https://core.telegram.org/bots/tutorial#obtain-your-bot-token).
