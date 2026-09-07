# Glow Diary by Deea

Jurnal personal de recenzii makeup — produsele cumpărate și testate de Deea, cu poza, nota și părerea ei. Vizitatoarele pot lăsa opțional o părere rapidă la fiecare produs, fără cont.

**Slogan:** Real products. My honest take.

## Stack

Django 5 + SQLite (dev). Fără cont/login pentru vizitatoare — doar Deea are acces de administrare, prin Django admin.

## Structură

- `reviews/` — app-ul principal: modele (`Product`, `Comment`, `ContactMessage`), views, forms, admin, template-uri
- `glow_diary/` — configurare proiect (settings, urls)
- `templates/base.html` — layout comun (header, navigare, footer)
- `static/css/style.css` — stilul girly/makeup din mock (culori, Unbounded + DM Sans)

## Setup local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Apoi:
- site: http://127.0.0.1:8000/
- admin (adaugă produse noi): http://127.0.0.1:8000/admin/

## Adăugare produs nou

Din Django admin → Products → Add product: nume, brand, categorie, nuanță (opțional), sursă (de unde a fost cumpărat), poză, nota ta (1-5) și părerea ta. Slug-ul se generează automat din brand + nume.

## Comentarii vizitatoare

Fiecare produs are o secțiune de comentarii publice (fără cont). Protecție anti-spam minimă:
- **honeypot** — câmp ascuns (`website`) pe care boții îl completează, oamenii nu; dacă e completat, comentariul e respins silențios
- **rate limiting** — un vizitator (după IP) poate comenta o dată la 60s pe același produs

Fiecare comentariu are un flag `aprobat` (implicit `True`) — poate fi debifat din admin pentru a ascunde un comentariu din public fără să fie șters (moderare manuală opțională).

## Note

Conținutul (produse, note, păreri) este real — al lui Deea, nu placeholder. Baza de date pornește goală; conținutul se adaugă din admin.
