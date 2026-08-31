# Vindictive Harvest (VIHA)

Local desktop OSINT workbench. Seed a persona with a name, phone, email, and/or known usernames. VIHA harvests **public** databases and public profile URLs and builds a sourced case file.

It does not log into accounts, bypass CAPTCHAs, or pull non-public records.

## Requirements

- Windows, macOS, or Linux
- Python 3.11+

## Install

```powershell
cd VindictiveHarvest
python -m pip install -e ".[dev]"
```

## Run

Desktop shortcut **VIHA** (created on install) or:

```powershell
python -m viha
```

`pythonw -m viha` launches the GUI without a console window.

### CLI harvest

Seeds are passed on the command line and are **not** stored in the repo.

```powershell
python -m viha reap --name "Full Name" --phone "5551234567" --email "you@example.com" --username "handle1, handle2" --out harvest-out.json --md dossier.md --graphml graph.graphml
python -m viha reap --list-collectors
```

Optional free keys (GitHub PAT, FEC `DEMO_KEY`) live in `%USERPROFILE%\.viha\settings.json` via **SETTINGS** in the GUI.

## Layout

```
VindictiveHarvest/
  viha/           application package
  tests/          pytest
  scripts/        launchers
  pyproject.toml
  LICENSE
```

Case files are written to `cases/` (gitignored).

## Legal

Use only for lawful research on public information. Verify every hit. Do not target minors.
