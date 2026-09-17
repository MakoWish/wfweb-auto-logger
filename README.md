![WFWEB Auto-Logger](docs/wfweb-auto-logger-banner.png)

---

## About

**_NOTE_**: This is just a test and should not be relied upon. Please use at your own risk, knowing that this might go away. The suggested changes to WFWEB's server-side logging are still being discussed. 

`wfweb-auto-logger` watches WFWEB's JSON-lines QSO log and automatically uploads each new contact to every enabled online logbook. Integrations are available for QRZ.com, eQSL.cc, HamQTH, and World Radio League.

## Integration status

| Service | Status | Notes |
| --- | --- | --- |
| QRZ.com | **Verified** | Confirmed working |
| eQSL.cc | **Verified** | Confirmed working |
| World Radio League | **Verified** | Confirmed working |
| HamQTH | **Verified** | Confirmed working |

## Requirements

- Python 3 (no third-party packages are required)
- WFWEB server-side QSO logging (pending [adecarolis/wfweb/issues/109](https://github.com/adecarolis/wfweb/issues/109))
- Credentials/API Keys for each logbook you enable

## Usage

At least one destination and the station callsign must be configured. Multiple `--enable-*` options may be supplied; each QSO is sent to all enabled destinations.

```console
./wfweb-auto-logger \
  --station-callsign KF0ZJT \
  --enable-qrz --qrz-api-key 'your-qrz-key' \
  --enable-eqsl --eqsl-username 'KF0ZJT' --eqsl-password 'your-eqsl-password' \
  --enable-hamqth --hamqth-username 'KF0ZJT' --hamqth-password 'your-hamqth-password'
```

Credentials can instead be supplied through environment variables, which keeps secrets out of the process list:

```console
export STATION_CALLSIGN='KF0ZJT'
export QRZ_API_KEY='your-qrz-key'
export EQSL_USERNAME='KF0ZJT'
export EQSL_PASSWORD='your-eqsl-password'
export HAMQTH_USERNAME='KF0ZJT'
export HAMQTH_PASSWORD='your-hamqth-password'
./wfweb-auto-logger --enable-qrz --enable-eqsl --enable-hamqth
```

### QRZ.com

Enable QRZ with `--enable-qrz`. Supply its Logbook API key with `--qrz-api-key` or `QRZ_API_KEY`.

### eQSL.cc

Enable eQSL with `--enable-eqsl`. Unlike QRZ, eQSL's ADIF upload interface authenticates with the account username and password rather than an API key:

- `--eqsl-username` or `EQSL_USERNAME`
- `--eqsl-password` or `EQSL_PASSWORD`
- Optional: `--eqsl-qth-nickname` or `EQSL_QTH_NICKNAME` to select an eQSL station profile

If the password contains shell metacharacters, quote it when passing it on the command line. Environment variables are preferable.

The logger encodes these credentials as the `eQSL_User` and `eQSL_Pswd`
fields required by eQSL's real-time ADIF interface. If eQSL reports
`Missing eQSL_User`, verify that the installed logger contains eQSL support and
that `--eqsl-username` (or `EQSL_USERNAME`) is set.

### HamQTH

Enable HamQTH with `--enable-hamqth`. Supply the account username and password with `--hamqth-username` and `--hamqth-password`, or `HAMQTH_USERNAME` and `HAMQTH_PASSWORD`.

The logger uses HamQTH's documented real-time QSO endpoint and sends one `insert` request per new contact. HamQTH requires both sent and received signal reports. HTTP 400 and 403 responses are recorded as rejections; server-side HTTP 500 responses remain pending for retry. This integration has been checked against the published API documentation and is ready for live-account testing.

### World Radio League

Enable World Radio League with `--enable-wrl`. Generate an API key under **Integrations → Developer API**, then supply it with `--wrl-api-key` or `WRL_API_KEY`. By default, contacts go to the account's default logbook. To select one explicitly, use `--wrl-logbook-id` or `WRL_LOGBOOK_ID`. See the [World Radio League API documentation](https://worldradioleague.com/developer/#description/introduction) for account and logbook setup.

If the account has multiple logbooks and no default, a destination is required. Either choose a default under **Integrations → Developer API** or obtain the desired UUID from `GET /v1/logbooks` and configure it explicitly:

```console
export WRL_API_KEY='wrl_live_...'
export WRL_LOGBOOK_ID='00000000-0000-0000-0000-000000000000'
./wfweb-auto-logger --enable-wrl --station-callsign KF0ZJT
```

With `--verbose`, the logger prints the contact JSON sent to World Radio League. WRL server and rate-limit errors remain pending for retry; when its response includes a request ID, the logger prints it so it can be supplied to WRL support.

## Options

| Option | Environment variable | Description |
| --- | --- | --- |
| `--station-callsign CALL` | `STATION_CALLSIGN` | Callsign written to `STATION_CALLSIGN` in uploaded ADIF |
| `--enable-qrz` | — | Upload to QRZ.com |
| `--qrz-api-key KEY` | `QRZ_API_KEY` | QRZ Logbook API key |
| `--enable-eqsl` | — | Upload to eQSL.cc |
| `--eqsl-username NAME` | `EQSL_USERNAME` | eQSL account username/callsign |
| `--eqsl-password PASSWORD` | `EQSL_PASSWORD` | eQSL account password |
| `--eqsl-qth-nickname NAME` | `EQSL_QTH_NICKNAME` | Optional eQSL QTH nickname |
| `--enable-hamqth` | — | Upload to HamQTH |
| `--hamqth-username NAME` | `HAMQTH_USERNAME` | HamQTH account username |
| `--hamqth-password PASSWORD` | `HAMQTH_PASSWORD` | HamQTH account password |
| `--enable-wrl` | — | Upload to World Radio League |
| `--wrl-api-key KEY` | `WRL_API_KEY` | World Radio League API key |
| `--wrl-logbook-id UUID` | `WRL_LOGBOOK_ID` | Optional World Radio League destination logbook |
| `--log-file PATH` | — | WFWEB JSONL log path |
| `--state-file PATH` | — | Upload progress state path |
| `--failed-file PATH` | — | Rejected or invalid record output path |
| `--from-start` | — | Upload existing records on the first run instead of starting at EOF |
| `--dry-run` | — | Print records and ADIF without uploading or updating state |
| `-v`, `--verbose` | — | Print ADIF and service responses |

Run `./wfweb-auto-logger --help` for the current defaults.

## Run at system startup with systemd

The repository includes a ready-to-install unit at
[`systemd/wfweb-auto-logger.service`](systemd/wfweb-auto-logger.service). Keep
the unit with the application source (rather than in `docs/`), then install it
under `/etc/systemd/system`, where locally managed system units belong.

Install the logger and unit:

```console
sudo install -m 0755 wfweb-auto-logger /usr/local/bin/wfweb-auto-logger
sudo install -m 0644 systemd/wfweb-auto-logger.service \
  /etc/systemd/system/wfweb-auto-logger.service
```

Create the configuration directory and `/etc/wfweb-auto-logger/config.env`:

```console
sudo install -d -m 0755 -o root -g root /etc/wfweb-auto-logger
sudo touch /etc/wfweb-auto-logger/config.env
sudo chown root:root /etc/wfweb-auto-logger/config.env
sudo chmod 0600 /etc/wfweb-auto-logger/config.env
sudoedit /etc/wfweb-auto-logger/config.env
```

Credentials alone do not enable a destination. The `--enable-*` options do not
have direct environment-variable equivalents, so list every desired destination
in `LOGGER_ARGS`. For example, this configuration enables all four services:

```ini
LOGGER_ARGS="--enable-qrz --enable-wrl --enable-eqsl --enable-hamqth"

STATION_CALLSIGN="KF0ZJT"

QRZ_API_KEY="your-qrz-key"

WRL_API_KEY="wrl_live_your-key"
# Optional when the WRL account has a default logbook:
WRL_LOGBOOK_ID="00000000-0000-0000-0000-000000000000"

EQSL_USERNAME="KF0ZJT"
EQSL_PASSWORD="your-eqsl-password"
# Optional:
EQSL_QTH_NICKNAME="Home"

HAMQTH_USERNAME="KF0ZJT"
HAMQTH_PASSWORD="your-hamqth-password"
```

Remove an `--enable-*` option and its service-specific settings if that
destination is not wanted. Keep the quotes around `LOGGER_ARGS` when it
contains multiple options. After changing only `config.env`, restart the
service with `sudo systemctl restart wfweb-auto-logger.service`; a
`daemon-reload` is needed only after changing the unit itself.

Load the unit and start it now and on future boots:

```console
sudo systemctl daemon-reload
sudo systemctl enable --now wfweb-auto-logger.service
```

The root-owned `0600` configuration file is intentional. The systemd service
manager reads `EnvironmentFile` before starting the process as `wfweb`, so the
service account does not need permission to read the file directly. A `Failed
to load environment files: No such file or directory` error means the file is
not present at the path used by the installed unit, rather than that `wfweb`
cannot read it. Confirm both the file and the installed unit with:

```console
sudo test -f /etc/wfweb-auto-logger/config.env && echo "config exists"
sudo systemctl cat wfweb-auto-logger.service
```

If `systemctl cat` shows a different environment-file path, reinstall the unit
using the commands above and run `sudo systemctl daemon-reload` before starting
it again.

The supplied unit runs as the existing `wfweb` user because the default QSO
log and logger state live below `/var/lib/wfweb`. If WFWEB runs under a
different account or the script is installed elsewhere, update `User`, `Group`,
`HOME`, `ReadWritePaths`, or `ExecStart` in the installed unit as appropriate.
Inspect startup and upload messages with:

```console
sudo systemctl status wfweb-auto-logger.service
sudo journalctl -u wfweb-auto-logger.service -f
```

## Delivery, retries, and failures

Progress is tracked independently for each enabled service in the state file. A successful QRZ upload is therefore not repeated merely because the same eQSL upload encountered a temporary network error. Services with transient network errors retry after 30 seconds while successful services continue from their own saved position.

A response-level rejection (for example, invalid credentials or an unacceptable QSO) is recorded in the failed-record JSONL file with a `logger` field identifying the service. It is treated as handled so one bad record cannot permanently block later contacts. Use `--verbose` when diagnosing a rejection.

The default paths are:

```text
Log:     /var/lib/wfweb/.local/share/wfweb/wfweb/qso-log.jsonl
State:   /var/lib/wfweb/.local/share/wfweb/wfweb/qrz-logger.state
Failures:/var/lib/wfweb/.local/share/wfweb/wfweb/qrz-logger-failed.jsonl
```

The original QRZ-only state format is recognized. Its QRZ offset is migrated automatically; a newly enabled service starts at the end of the current log unless `--from-start` is supplied.

## Dry run

A dry run is a safe way to inspect generated ADIF:

```console
./wfweb-auto-logger --enable-qrz --qrz-api-key unused \
  --station-callsign KF0ZJT --dry-run --from-start --verbose
```

Dry runs never contact a service and never update the state or failure files.

## Suggestions, Issues, or Contributions

If you have suggestions for this logger, or would like to make a contribution, please first open an issue to get the conversation started.
