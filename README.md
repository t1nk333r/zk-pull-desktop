# ZK Pull

A Windows desktop app that pulls attendance from ZKTeco devices over the office network and exports
it to Excel or CSV. English and Arabic.

It is the stop-gap until the devices push to ERPNext (see
[zk_push](https://github.com/t1nk333r/zk_push)): it talks to the device directly on the LAN, the same
way ZKTeco's own software does, and needs no server.

**Nothing is ever deleted from the devices.** The app only reads: it never clears the attendance log,
never changes users and never sets the clock.

## Features

- **Pull** the attendance log from one device or all of them (TCP port 4370, read-only).
- **Pick a period**: today, yesterday, this week (from Sunday), this month, last month, or any dates.
- **Export** the period to Excel (.xlsx) or CSV, switched with one click:
  - *Punch log*: one row per punch (employee ID, name, department, date, time, punch type, verified
    by, device).
  - *Daily summary*: one row per employee per day (first punch, last punch, hours, number of punches).
  - The file opens by itself after export (a tick box next to **Export** turns this off).
- **Names**: a small list of employee ID → name and department. Fill it from the device's own user
  list, from an Excel/CSV file, or by hand. Device names are often cut short (8 characters on some
  models), so they can be corrected here.
- **No duplicates**: pulling the same period again stores nothing twice.
- **Works offline**: everything pulled is kept locally, so exports work without the device.
- **Updates itself**: checks GitHub for a new version at startup (can be turned off in Settings) and
  installs it after asking. The download is checked against the checksum GitHub publishes. This needs
  internet access; the portable zip only links to the download page.
- English and Arabic (right to left). Numbers and dates always use Western digits (0-9).

## Install

Download `ZK-Pull-Setup-<version>.exe` from the
[releases](https://github.com/t1nk333r/zk-pull-desktop/releases) page and run it. No admin rights are
needed. There is also a portable zip that runs without installing.

The installer is not code-signed, so Windows SmartScreen shows *"Windows protected your PC"*. Click
**More info**, then **Run anyway**. Updates installed from inside the app skip this.

Version 0.1.0 has no updater: install 0.2.0 over it once by hand (names and history are kept).

The PC must be on the same network as the devices.

## First launch

1. Choose English or Arabic (can be changed later in **Settings**).
2. Add a device: a name, its IP address, port (4370) and comm key (0 unless one was set on the
   device). **Test connection** shows the serial number and how many punches and users it holds.
3. Import names from the device, or skip and do it later from the **People** tab.

Every step can be skipped.

## Data

Everything is kept in `%LOCALAPPDATA%\ZK Pull`:

- `zk_pull.db`: devices, names, pulled punches and settings (SQLite).
- `zk_pull.log`: what was pulled and any errors. Send this file when reporting a problem.

Uninstalling leaves this folder in place. Back it up to keep the names and history.

## Settings

| Setting | Default | |
|---|---|---|
| Language | chosen on first launch | English or Arabic |
| Export layout | Punch log | or Daily summary |
| Export column headers | English | English headers are what payroll and ERP imports usually expect |
| Default export folder | your home folder | then the last folder used |
| Open file after export | on | the tick box next to **Export** |
| Check for updates at startup | on | **Check for updates** checks now |

CSV files opened in Excel lose leading zeros in employee IDs (`007` becomes `7`); use Excel (.xlsx)
when IDs have them.

## Linux

The Windows build is not tested under Wine. On Linux, run the app from source instead (see
Development); it is the same app.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run zk-pull             # run the app
uv run pytest              # tests (set QT_QPA_PLATFORM=offscreen without a display)
uv run ruff check . && uv run ruff format --check .
```

| Module | |
|---|---|
| `device.py` | Reads punches and users from a device (pyzk). Read-only. |
| `store.py` | SQLite: devices, people, punches, settings. |
| `export.py` | CSV / XLSX writers, punch log and daily summary. |
| `i18n.py` | English and Arabic texts. |
| `periods.py` | Quick date ranges. |
| `worker.py` | Runs device I/O off the UI thread. |
| `updater.py` | Checks GitHub Releases, downloads and checks the installer. |
| `app.py`, `*_tab.py`, `dialogs.py` | The Qt (PySide6) interface. |

## Release

Set `__version__` in `src/zk_pull_desktop/__init__.py`, commit, then tag `v<version>` and push the
tag. GitHub Actions (Windows) runs the tests, builds the app with PyInstaller, wraps it with Inno
Setup and attaches the installer and portable zip to the release.

## License

MIT. The app icon is "Fingerprint" by [Icons8](https://icons8.com), used under their free licence,
which requires this link.
