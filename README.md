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

cp .env.example .env
# completează SECRET_KEY în .env (vezi comentariul din fișier pentru comanda de generat)

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Apoi:
- site: http://127.0.0.1:8000/
- admin (adaugă produse noi): http://127.0.0.1:8000/admin/ (sau ruta din `ADMIN_URL`)

## Variabile de mediu

Toate valorile sensibile/specifice mediului vin din `.env` (local) sau din variabilele de mediu setate direct pe server (producție) — vezi `.env.example` pentru lista completă cu explicații. Cele mai importante:

| Variabilă | Rol |
|---|---|
| `SECRET_KEY` | obligatorie, fără fallback — aplicația refuză să pornească fără ea |
| `DEBUG` | `False` implicit; `True` doar local |
| `ALLOWED_HOSTS` | domeniile permise, separate prin virgulă |
| `CSRF_TRUSTED_ORIGINS` | originile `https://...` de încredere, în producție |
| `REDIS_URL` | cache partajat pentru rate limiting — necesar dacă rulezi mai mult de un worker |
| `TRUST_X_FORWARDED_FOR` | `True` doar dacă hostingul suprascrie sigur acest header |
| `ADMIN_URL` | schimbă ruta panoului de admin din `admin/` implicit |
| `ADMIN_EMAIL` | primește email automat la fiecare eroare 500 |

## Checklist înainte de lansare live

1. `.env` (sau variabilele de mediu de pe server) completat: `SECRET_KEY` nou generat, `DEBUG=False`, `ALLOWED_HOSTS` cu domeniul real, `CSRF_TRUSTED_ORIGINS` cu `https://domeniultau.ro`.
2. `REDIS_URL` setat dacă rulezi mai mult de un worker (gunicorn/uwsgi) — altfel rate limiting-ul devine inconsistent între procese.
3. `python manage.py check --deploy` — trebuie să iasă curat.
4. `python manage.py collectstatic --noinput` — copiază fișierele statice în `STATIC_ROOT` (`staticfiles/`), servite apoi de webserver/CDN.
5. `python manage.py migrate`.
6. `ADMIN_EMAIL` setat, ca să afli când pică ceva (email automat la eroare 500).
7. `python manage.py test reviews` — toate testele trec.

## Adăugare produs nou

Din Django admin → Products → Add product: nume, brand, categorie, nuanță (opțional), sursă (de unde a fost cumpărat), poză, nota ta (1-5) și părerea ta. Slug-ul se generează automat din brand + nume. Poți adăuga și poze suplimentare de galerie direct din aceeași pagină (secțiunea „Imagine galerie" de sub formular).

## Colecții curate

Din admin → Collections poți grupa produse existente într-o colecție tematică (nume, descriere, copertă opțională + produsele incluse). Colecțiile fără produse nu apar public.

## Wishlist vizitatoare

Butonul cu inimioară de pe orice postare salvează produsul într-o listă locală, în browserul vizitatoarei (`localStorage`, fără cont, fără server). Pagina „Favorite" citește acea listă și afișează produsele salvate.

## Moment de celebrare

Când numărul de produse postate atinge un prag (10, 25, 50, 100, 200, 500), feed-ul arată o dată un banner + confetti de celebrare (per vizitator, ținut minte tot în `localStorage`).

## Comentarii vizitatoare

Fiecare produs are o secțiune de comentarii publice (fără cont). Protecție anti-spam minimă:
- **honeypot** — câmp ascuns (`website`) pe care boții îl completează, oamenii nu; dacă e completat, comentariul e respins silențios
- **rate limiting** — un vizitator (după IP) poate comenta o dată la 60s pe același produs

Fiecare comentariu are un flag `aprobat` (implicit `True`) — poate fi debifat din admin pentru a ascunde un comentariu din public fără să fie șters (moderare manuală opțională).

## Note

Conținutul (produse, note, păreri) este real — al lui Deea, nu placeholder. Baza de date pornește goală; conținutul se adaugă din admin.
