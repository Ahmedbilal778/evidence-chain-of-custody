# CustodyChain - Evidence Chain of Custody (Django)

Log evidence, record every hand-over, and verify with a **SHA-256 hash chain** that no record was changed.

## Getting started

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

python manage.py makemigrations custody
python manage.py migrate
python manage.py seed_demo      # demo users + cases + evidence (optional)
python manage.py runserver
```

Open in your browser: http://127.0.0.1:8000/

| User | Password | Role |
|---|---|---|
| admin | admin12345 | Administrator (+ /admin/ panel) |
| investigator | demo12345 | Investigator |
| analyst | demo12345 | Lab analyst |
| viewer | demo12345 | Read only |

To create your own superuser: `python manage.py createsuperuser`

## Features
- Login + roles (Admin / Investigator / Lab analyst / Viewer read-only)
- Cases and evidence (auto IDs: CS-2026-001, EV-2026-0001), search, filters and pagination
- File upload: the file's SHA-256 is saved and written into the first record of the chain
- Append-only custody ledger: every record stores the hash of the previous record
- "Verify chain" button: the server re-hashes the whole chain and shows a red link where tampering is found
- Integrity check page (all evidence at once)
- Printable custody report (save as PDF) + QR code for evidence labels
- Dashboard: counters, chain health strip, charts
- Fully responsive (the sidebar becomes a menu on mobile), with light and dark themes

## How the hash chain works
Each `CustodyLog` hash = SHA-256( evidence ID | action | from | to | location | notes | recorded by | time | **previous hash** ).
If an old record is quietly changed in the database, its hash will no longer match and the chain will show as "broken".

Limitation: if the most recent record is deleted directly in the database, the hash check cannot catch it.
In production, anchor the latest hash somewhere else (external log / blockchain / signed timestamp).

## Project structure
```
config/      settings, urls
custody/     models (Case, Evidence, CustodyLog, Profile), views, forms, admin, seed command
templates/   base, login, dashboard, cases, evidence, report, integrity
static/      css/app.css, js/app.js
```

Note: Bootstrap, icons, fonts, Chart.js and the QR library load from CDNs, so the UI needs an internet connection.
Before deploying, change `SECRET_KEY` and set `DEBUG = False`.