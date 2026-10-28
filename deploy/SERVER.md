# Always-on hosting for the direct OANDA feed

The OANDA adapter removes the desktop-terminal requirement. An always-on Linux host
is still required to keep ingesting prices and evaluating signals while your Mac is
off. This package is **not deployed yet**. No host/domain has been purchased or changed.

## Prepare a host you control

Use a Linux server with Docker Engine and the Compose plugin, and a domain pointed
to that host. Transfer the source archive and extract it. Do not transfer a local
.env or database in the source archive. Set up provider secrets directly on the server.

From the extracted Aurum root:

```sh
cp backend/.env.example backend/.env
cp .env.server.example .env.server
chmod 600 backend/.env .env.server
```

Privately edit `backend/.env`: set DATA_MODE=oanda, your matching OANDA environment,
API token and v20 account ID, and XAU_USD. See `oanda/SETUP.md` for eligibility and
instrument-access requirements. MT5 keys are unused. Telegram stays off unless you
explicitly configure it.

Set your actual hostname and a username in `.env.server`. Generate a password hash
interactively, so a plaintext password is not recorded in shell arguments/history:

```sh
docker run --rm -it caddy:2-alpine caddy hash-password
```

Copy the resulting hash to AURUM_PASSWORD_HASH inside **single quotes** in `.env.server`.
Replace the placeholder; do not use a published example password/hash. Caddy provides
HTTP basic authentication for both the dashboard and API, and automatic HTTPS for
a correctly configured public hostname.

Start:

```sh
docker compose --env-file .env.server -f compose.server.yaml up -d --build
```

Visit your HTTPS domain and sign in using that username/password. Confirm the OANDA
source, environment, quote freshness and bid/ask. Only then turn off your desktop.
If no credentials or eligible gold instrument are available, the server stays in a
waiting/error state and never substitutes generated data.

## Persistence and operations

One backend worker owns the feed. The default server deployment uses SQLite in a
named Docker volume, which is sufficient for this single-user MVP; PostgreSQL is
also supported by setting DATABASE_URL and adding a managed/private database. Keep
backend port 8000 private; the package publishes only HTTP/HTTPS through Caddy.

- Back up the `aurum_data` volume, provider configuration and Caddy volumes.
- Use the HTTPS dashboard to verify feed health; container liveness alone does not
  mean credentials are valid or the market is open.
- Keep host firewall, patches and Docker updates maintained.
- Do not run multiple independent backend instances against the same journal.
- Avoid `docker compose down -v`: removing volumes removes the recorded history.
- Stop with `docker compose --env-file .env.server -f compose.server.yaml down`;
  named volumes remain unless explicitly removed.

These Docker/Caddy definitions have been inspected and YAML-parsed, but a container
build and real server deployment could not be exercised here because Docker is not
installed. Live OANDA access is likewise unverified without your credentials.
