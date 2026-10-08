# CustodyChain - Evidence Chain of Custody (Django)

Evidence ko log karo, haath-badal (transfer) record karo, aur **SHA-256 hash chain** se verify karo ki koi record badla to nahi gaya.

## Run karne ke steps

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac / Linux
pip install -r requirements.txt

python manage.py makemigrations custody
python manage.py migrate
python manage.py seed_demo      # demo users + cases + evidence (optional)
python manage.py runserver
```

Browser me kholo: http://127.0.0.1:8000/

| User | Password | Role |
|---|---|---|
| admin | admin12345 | Administrator (+ /admin/ panel) |
| investigator | demo12345 | Investigator |
| analyst | demo12345 | Lab analyst |
| viewer | demo12345 | Read only |

Apna superuser banana ho to: `python manage.py createsuperuser`

## Features
- Login + roles (Admin / Investigator / Lab analyst / Viewer read-only)
- Cases aur Evidence (auto IDs: CS-2026-001, EV-2026-0001), search + filters + pagination
- File upload: file ka SHA-256 save hota hai aur chain ke pehle record me jata hai
- Append-only custody ledger: har record me pichle record ka hash hota hai
- "Verify chain" button: server pe poori chain dobara hash hoti hai, tampering pe red link dikhta hai
- Integrity check page (saare evidence ek saath)
- Printable custody report (PDF save kar sakte ho) + QR code evidence label ke liye
- Dashboard: counters, chain health strip, charts
- Fully responsive (mobile me sidebar menu ban jata hai)

## Hash chain kaise kaam karti hai
Har `CustodyLog` ka hash = SHA-256( evidence ID | action | from | to | location | notes | recorded by | time | **pichla hash** ).
Koi bhi purana record DB me chupke se badla jaye to uska hash match nahi karega aur chain "broken" dikhegi.

Limitation: sabse aakhri record chupke se hata diya jaye to wo hash se pakda nahi jata. Production me hash ko
alag jagah (external log / blockchain / signed timestamp) anchor karna chahiye.

## Folder structure
```
config/      settings, urls
custody/     models (Case, Evidence, CustodyLog, Profile), views, forms, admin, seed command
templates/   base, login, dashboard, cases, evidence, report, integrity
static/      css/app.css, js/app.js
```

Note: UI ke liye Bootstrap, icons, fonts, Chart.js aur QR library CDN se load hoti hain, isliye internet chahiye.
Deploy karne se pehle `SECRET_KEY` badlo aur `DEBUG = False` karo.
