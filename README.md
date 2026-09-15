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

**Notă:** după 5 încercări greșite de parolă de pe aceeași adresă IP, login-ul se blochează automat 1 oră (django-axes — protecție împotriva ghicitului repetat de parolă). Dacă te blochezi singură din greșeală, așteaptă ora sau, local, rulează `python manage.py axes_reset`.

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
| `INSTAGRAM_URL` | link afișat ca iconiță în footer; are deja o valoare implicită |
| `TIKTOK_URL` | link afișat ca iconiță în footer; necompletat, iconița nu apare |

## Checklist înainte de lansare live

1. `.env` (sau variabilele de mediu de pe server) completat: `SECRET_KEY` nou generat, `DEBUG=False`, `ALLOWED_HOSTS` cu domeniul real, `CSRF_TRUSTED_ORIGINS` cu `https://domeniultau.ro`.
2. `REDIS_URL` setat dacă rulezi mai mult de un worker (gunicorn/uwsgi) — altfel rate limiting-ul devine inconsistent între procese.
3. `python manage.py check --deploy` — trebuie să iasă curat.
4. `python manage.py collectstatic --noinput` — copiază fișierele statice în `STATIC_ROOT` (`staticfiles/`), servite apoi de webserver/CDN.
5. `python manage.py migrate`.
6. `ADMIN_EMAIL` setat, ca să afli când pică ceva (email automat la eroare 500).
7. `python manage.py test reviews` — toate testele trec.

## Adăugare produs nou

Din Django admin → Products → Add product: nume, brand, categorie, nuanță (opțional), sursă (de unde a fost cumpărat), poză, nota ta (1-5) și părerea ta. Slug-ul se generează automat din brand + nume. Poți adăuga și poze suplimentare de galerie direct din aceeași pagină (secțiunea „Imagine galerie" de sub formular). Pozele mari (poze de telefon) sunt redimensionate automat la salvare, nu e nevoie să le micșorezi manual înainte.

Pentru mai multe produse deodată: butonul „Adaugă mai multe produse" de lângă „Add product" deschide un formular cu mai multe rânduri (fără poză — aceea rămâne de adăugat individual, per produs, după).

### Verdict (secțiunea din formular)

Pe lângă notă și părere, un produs poate avea: **preț** (lei — opțional, dar exact ce vine să afle cineva care se întreabă dacă merită banii), **îl recumpăr** (Da/Nu, lăsat necompletat cât timp nu te-ai hotărât — completat, arată sigiliu auriu pe card), **cât ține** (text liber, ex. „8 ore") și **recomandat pentru** (text liber, ex. „ten gras"). Toate opționale.

### Categorii (grupuri + subcategorii)

Categoriile sunt pe 2 niveluri: un **grup** (ex. „Machiaj", „Îngrijire ten") și **subcategoriile** lui (ex. „Buze", „Ochi"). Un produs se leagă mereu de o subcategorie, sau de un grup fără subcategorii (ex. „Parfumuri", „Altele"). Complet editabile din admin → Categorii — la fel ca Tag-urile, poți adăuga/redenumi/reordona oricând, fără cod. În feed, o categorie apare în filtru doar dacă are cel puțin un produs activ.

### Tag-uri și filtrare după preț

**Tag-uri** — atribute libere de filtrare (tip de ten, ingrediente etc.), gestionate din admin → Tags: se pot adăuga/șterge oricând, fără cod. Un produs poate avea mai multe tag-uri (secțiunea „Filtrare" din formularul de produs). Feed-ul are un filtru dedicat pe tag, plus un filtru de **preț maxim** — ambele combinabile cu restul filtrelor existente (categorie, notă minimă, sursă, sortare).

## Colecții curate

Din admin → Collections poți grupa produse existente într-o colecție tematică (nume, descriere, copertă opțională + produsele incluse). Colecțiile fără produse nu apar public.

## Wishlist vizitatoare

Butonul cu inimioară de pe orice postare salvează produsul într-o listă locală, în browserul vizitatoarei (`localStorage`, fără cont, fără server). Pagina „Favorite" citește acea listă și afișează produsele salvate.

## Moment de celebrare

Când numărul de produse postate atinge un prag (10, 25, 50, 100, 200, 500), feed-ul arată o dată un banner + confetti de celebrare (per vizitator, ținut minte tot în `localStorage`).

## Căutare live și paginare

Căutarea din feed filtrează pe măsură ce tastezi (debounced, fără reload), prin `/api/search/`. Paginarea folosește pastile numerotate, nu doar „înapoi/înainte".

## Produse similare

Pagina de produs arată automat 2-3 produse din aceeași categorie sub secțiunea de comentarii ("S-ar putea să-ți placă și").

## Card de distribuire pentru Instagram Story

Fiecare produs are un buton „Descarcă pentru Story" (`/produs/<slug>/story.png`) care generează pe loc o imagine 1080x1920 cu poza produsului, brand, notă și sigiliul TESTED BY DEEA — gata de postat direct la story.

## PWA — instalabil pe telefon

Site-ul are `site.webmanifest` + service worker minim (`/sw.js`) — pe telefon poate fi adăugat pe ecranul principal ca o mini-aplicație (fără bară de adresă). Service worker-ul cache-uiește doar fișierele statice; paginile HTML merg mereu în rețea întâi, ca conținutul să rămână mereu actual.

## Comentarii vizitatoare

Fiecare produs are o secțiune de comentarii publice (fără cont). Protecție anti-spam minimă:
- **honeypot** — câmp ascuns (`website`) pe care boții îl completează, oamenii nu; dacă e completat, comentariul e respins silențios
- **rate limiting** — un vizitator (după IP) poate comenta o dată la 60s pe același produs

Fiecare comentariu are un flag `aprobat` (implicit `True`) — poate fi debifat din admin pentru a ascunde un comentariu din public fără să fie șters (moderare manuală opțională).

O vizitatoare poate atașa opțional și o poză cu produsul la comentariu (validată la upload: max. 5MB, rezoluție rezonabilă — vezi `CommentForm.clean_imagine`).

## Recap anual

`/recap/<an>/` generează automat un „best of anul" din datele existente (nu conținut scris separat): media notelor, total cheltuit, produse recumpărate, top 3 produse după notă, cele mai comentate, brandul și categoria preferată, cel mai scump produs. Sub un prag minim de produse postate în anul respectiv, arată un mesaj prietenos în loc de statistici goale.

## Dark mode

Automat, după preferința sistemului de operare al vizitatoarei (`prefers-color-scheme`, fără toggle manual în interfață). Acoperă tot CSS-ul site-ului; imaginile de Story rămân neschimbate (sunt PNG-uri generate server-side cu Pillow, nu randate din CSS).

## Note

Conținutul (produse, note, păreri) este real — al lui Deea, nu placeholder. Baza de date pornește goală; conținutul se adaugă din admin.
