# Vindictive Harvest (VIHA)

Local desktop OSINT workbench. Seed a persona with a name, phone, email, and/or known usernames. VIHA harvests **public** databases and public profile URLs and builds a sourced case file.

It does not log into accounts, bypass CAPTCHAs, or pull non-public records.

## Requirements

- Windows, macOS, or Linux
- Python 3.10 or newer

## Install

**Windows:** double-click `install.bat`. That creates a local `.venv`, installs every dependency, and adds a desktop shortcut.

If you already have Python 3.10+:

```powershell
cd VindictiveHarvest
python -m pip install -e .
python -m viha
```

`python -m viha` also installs missing packages (`httpx`, `PySide6`) the first time it runs.

The GitHub zip unpacks as `VindictiveHarvest-main`. Run `install.bat` from that folder (the one that contains `pyproject.toml`).

## Run

Desktop shortcut **VIHA** (amber sickle / constellation icon). Recreate it with:

```powershell
powershell -File scripts\install-shortcut.ps1
```

Or:

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

## Age, address, and people indexes

DuckDuckGo HTML no longer returns people-search titles like `Owner …, Age 25 in …`. Bing still does. VIHA now:

- Queries **Bing HTML** for quoted names, age/born, phone forms, and `site:` dorks (FastPeopleSearch, TruePeopleSearch, Intelius, ThatsThem). DuckDuckGo still runs the broader query set. **Google.com is not used** — it captchas bots; Bing `site:` is the dork engine.
- Parses indexed titles/snippets for aka, age, `Born Month Year`, city, and streets.
- **GETs viable result URLs** from those hits (people-index and a few official hosts). If the live page 403s or shows a challenge, it tries the Wayback Machine copy, then the same HTML parser as IMPORT PEOPLE HTML.
- Direct collector GETs of FastPeopleSearch often **403**. The harvest follows reverse-phone listings into the `_id_G` profile page (JSON-LD: job, relatives, emails, addresses). If blocked, the persona sheet lists those URLs — save the **profile** HTML and **IMPORT PEOPLE HTML**. CLI: `python -m viha ingest-html saved.html --name "Full Name" --phone "5551234567"`.
- Hits stay **candidates**. Two data-broker pages agreeing is not confirmation.
- Does not fuzzy-match first names (`Brendon` ≠ `Brendan`). Phone digits in the title raise confidence.
- Adds **Guadalupe CAD** portals for 210 / Cibolo / Schertz / Seguin, not only Bexar. Official owner and mortgage note are CAD/clerk records, not skip-trace pages.

Spotify user URLs are probed as vanity paths. Instagram, Facebook, LinkedIn, and Discord stay login-walled; VIHA does not sign in.

## Legal

Use only for lawful research on public information. Verify every hit. Do not target minors.
