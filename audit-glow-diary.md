# Audit Glow Diary by Deea — 5 prompturi

*Notă de context: Prompt 1 e pe codul din repo (stare curentă la 13.09.2026, inclusiv commit-urile locale — Tag-uri, verdict, poze în comentarii, recap, dark mode). Prompturile 2-5 sunt bazate pe navigarea site-ului **live** (glowdiary.pythonanywhere.com), care nu reflectă încă aceste commit-uri, deoarece n-au fost push-uite/deployate.*

> **Stare Prompt 1 (13.09.2026):** trecut prin el punct cu punct — fiecare are un marcaj **Status** imediat sub el. ✅ = rezolvat acum (cod + teste + migrații, 74/74 teste trec). ⏸ = amânat conștient (cere un serviciu extern nou sau o decizie de produs/infra pe care n-am luat-o eu). Nimic nu a fost șters din cod — unde auditul oferea alegerea "șterge sau documentează", am ales varianta care păstrează codul.

---

# PROMPT 1/5 — AUDIT DE COD

## 1. Securitate

- **Fișier:** `glow_diary/settings.py` (admin login) → **Risc:** Nu există rate-limiting sau 2FA pe login-ul de admin Django. Un singur cont controlează tot site-ul (produse, comentarii, mesaje) — brute-force pe parolă e limitat doar de `MinimumLengthValidator(12)`, fără blocare după N încercări eșuate. → **Recomandare:** `django-axes` sau echivalent pentru lockout după încercări repetate; opțional 2FA (`django-otp`) dat fiind că un singur cont are acces total.
  → **Status:** ✅ Rezolvat parțial — `django-axes` adăugat și configurat (lockout 1 oră după 5 încercări greșite/IP, vezi `AXES_*` în `settings.py`, migrat, testat). ⏸ 2FA amânat — e o decizie de produs (Deea ar trebui să-și instaleze o aplicație de coduri), nu doar o modificare de cod.

- **Fișier:** `reviews/forms.py` (`CommentForm.imagine`) → **Risc:** Niciun formular public (comentariu cu poză, fără autentificare) nu are o limită explicită de dimensiune fișier. Django are doar `FILE_UPLOAD_MAX_MEMORY_SIZE` implicit (2.5MB — prag de spooling pe disc, nu de refuz), deci un vizitator anonim poate încărca fișiere mari repetat, limitat doar de rate-limiting (1/60s per produs + 5/10min global) — tot înseamnă potențial multe zeci de MB pe oră către un hosting cu spațiu limitat (PythonAnywhere free tier). → **Recomandare:** validare explicită `clean_imagine` cu un plafon (ex. 5MB) + `DATA_UPLOAD_MAX_MEMORY_SIZE` setat conștient.
  → **Status:** ✅ Rezolvat — `CommentForm.clean_imagine` respinge orice poză peste 5MB (`MAX_UPLOAD_IMAGINE_BYTES`), plus `FILE_UPLOAD_MAX_MEMORY_SIZE`/`DATA_UPLOAD_MAX_MEMORY_SIZE` declarate explicit în `settings.py`. Testat (`test_poza_peste_5mb_e_respinsa_de_formular`).

- **Fișier:** `reviews/image_utils.py` (`optimizeaza_poza`) → **Risc:** `except Exception` general înghite orice eroare de procesare, inclusiv un posibil `DecompressionBombError` de la Pillow pe o imagine cu dimensiuni de pixeli exagerate — la eroare, fișierul original (netratat) tot se salvează. Endpoint public (`Comment.imagine`) fără nicio verificare suplimentară de `Image.MAX_IMAGE_PIXELS`. → **Recomandare:** verifică explicit dimensiunile decodate înainte de resize și respinge imaginile anormal de mari, în loc să te bazezi doar pe excepția implicită din Pillow.
  → **Status:** ✅ Rezolvat — verificare explicită de pixeli (`MAX_PIXELI_ACCEPTATI` = 40MP) înainte de resize, care ridică `PozaPreaMareError` (nu mai e înghițită de `except Exception`); dublată în `CommentForm.clean_imagine` pentru calea publică. Testat pe ambele căi (`test_poza_peste_pragul_de_pixeli_e_respinsa`, `test_poza_cu_rezolutie_extrema_e_respinsa`).

- **Fișier:** `reviews/views/product.py` (`ProductDetailView.post`) → **Risc:** Detectarea honeypot-ului (`if not any(form.errors.get(f) for f in (...))`) e euristică: dacă un bot completează honeypot-ul ȘI lasă `comentariu` gol, ramura de eroare normală (nu cea "silențioasă") se activează, dezvăluind indirect structura de validare unui bot. → **Recomandare:** verifică explicit `form.cleaned_data.get("website")`/eroarea de honeypot înainte de orice altă ramificație, nu prin excludere.
  → **Status:** ✅ Rezolvat — acum verifică explicit `form.errors.get("website")` primul. Am găsit exact același bug și în `ContactView.post` (`static_pages.py`, nemenționat separat în audit) și l-am reparat la fel, pentru consecvență. Testat cu ambele (`test_honeypot_cu_comentariu_gol_ramane_mesaj_generic`, `test_contact_honeypot_cu_mesaj_gol_ramane_mesaj_generic`).

- **Fișier:** `reviews/forms.py` / `reviews/models.py` (Contact, Comment) → **Risc:** Singura protecție anti-spam e honeypot + rate-limit per IP. Un spammer care rotește IP-uri trece nelimitat; nu există CAPTCHA. → **Recomandare:** dacă spam-ul devine o problemă reală, adaugă un CAPTCHA invizibil (hCaptcha/Turnstile) ca a doua linie.
  → **Status:** ⏸ Amânat — cere un cont/cheie la un serviciu extern (hCaptcha/Turnstile), decizie de-a ta. Auditul însuși spune să-l adaugi doar "dacă spam-ul devine o problemă reală" — nu e urgent acum.

- **Fișier:** `glow_diary/urls.py` (servirea `media/` prin `django.views.static.serve`) → **Risc:** Documentat deja în cod ca soluție temporară, dar `serve()` nu e recomandat de Django pentru producție (nu din motive de securitate directă — are protecție la path traversal — ci de performanță/lipsă control cache-headers). → **Recomandare:** migrare la storage extern (S3/Cloudinary) + CDN pe termen mediu, așa cum e deja notat.
  → **Status:** ⏸ Amânat — cere cont la un provider extern (S3/Cloudinary) + configurare de credențiale, decizie de infra a ta, nu o schimbare de cod pe care s-o iau singur.

- **Fișier:** `.github/workflows/tests.yml` → **Risc:** CI rulează testele cu `DEBUG=True`, deci pipeline-ul de fișiere statice de producție (`ManifestStaticFilesStorage`, care cere `collectstatic`) nu e exercitat niciodată de CI — o referință `{% static %}` la un fișier inexistent ar trece testele în CI dar ar pica 500 în producție. → **Recomandare:** un job CI separat care rulează `collectstatic` + un smoke-test cu `DEBUG=False`.
  → **Status:** ✅ Rezolvat — job nou `static-smoke` în `tests.yml`: `collectstatic` + suita de teste completă rulată cu `DEBUG=False` (testele erau deja pregătite pentru asta, via `_no_ssl_redirect`).

## 2. Concurență și integritate a datelor

- **Fișier:** `reviews/signals.py` (`invalideaza_feed_stats`) → **Risc:** Semnalul ascultă doar `post_save`/`post_delete` pe `Product`, nu și pe `Comment`. `produsul_lunii()` (în `queries.py`) depinde de numărul de comentarii din ultimele 30 de zile — un comentariu nou nu invalidează cache-ul `feed-stats` (TTL 5 minute), deci sigiliul "PRODUSUL LUNII" poate rămâne stale până la 5 minute după un comentariu care ar fi trebuit să schimbe rezultatul. → **Recomandare:** adaugă `post_save`/`post_delete` pe `Comment` la același semnal.
  → **Status:** ✅ Rezolvat — `invalideaza_feed_stats` ascultă acum și `Comment` (post_save/post_delete).

- **Fișier:** `reviews/models.py` (`Comment.imagine`) → **Risc:** Inconsistență de convenție față de restul codebase-ului: `Product.poza`, `ProductImage.imagine`, `Collection.coperta` folosesc doar `blank=True` (fără `null=True`); `Comment.imagine` folosește ambele. Două reprezentări diferite de "fără fișier" (`""` vs `NULL`) în același model de date, fără motiv funcțional. → **Recomandare:** aliniază la convenția existentă — doar `blank=True`.
  → **Status:** ✅ Rezolvat — `null=True` eliminat; migrare `0009` (data-fix NULL→'' + AlterField) scrisă manual și testată, aplicată curat pe baza existentă.

- **Fișier:** `reviews/models.py` (`Product.delete()`, CASCADE pe `ProductImage`/`Comment`) → **Risc:** Django nu șterge automat fișierul fizic de pe disc când un rând cu `ImageField` e șters din bază (gotcha cunoscut). La hard-delete (al doilea click în admin, după soft-delete), rândurile `ProductImage`/`Comment` dispar din DB prin CASCADE, dar fișierele-imagine rămân orfane pe disc la nesfârșit. Același lucru se întâmplă și la simpla ÎNLOCUIRE a unei poze existente — fișierul vechi nu e șters niciodată. → **Recomandare:** `django-cleanup` (sau semnale `pre_delete`/`pre_save` custom) pentru a șterge fișierul fizic odată cu rândul/la înlocuire.
  → **Status:** ✅ Rezolvat — `django-cleanup` adăugat și configurat. Testat direct (fișier șters la hard-delete și la înlocuirea unei poze existente), folosind `captureOnCommitCallbacks` (cleanup rulează în `transaction.on_commit`).

- **Fișier:** `reviews/views/recap.py` (`brand_top`, `categorie_top`, `cel_mai_scump`) → **Risc:** `.order_by("-total").first()` / `.order_by("-pret").first()` fără un al doilea criteriu de sortare (tiebreaker) — la egalitate, rezultatul returnat nu e garantat determinist de SQL standard. → **Recomandare:** adaugă un criteriu secundar stabil, ex. `.order_by("-total", "brand")` (deja făcut pentru `brand_top`, lipsește pentru `categorie_top` și `cel_mai_scump`).
  → **Status:** ✅ Rezolvat — `categorie_top` are acum tiebreaker `categorie`, `cel_mai_scump` are tiebreaker `-data_postarii`.

- **Fișier:** `reviews/queries.py` / README (deja documentat) → **Risc:** Fără `REDIS_URL` setat în producție cu mai mult de un worker, rate-limiting-ul (bazat pe `cache.add`/`cache.incr` din `LocMemCache`, per-proces) devine inconsistent între workeri — un spammer poate ocoli limita distribuindu-se pe workeri diferiți. E deja în checklist-ul de lansare, dar rămâne un risc real dacă pasul e omis. → **Recomandare:** verificare automată la boot (`checks.py`) care avertizează dacă `DEBUG=False` și `REDIS_URL` lipsește.
  → **Status:** ✅ Rezolvat — `reviews.W001` în `checks.py`, rulează la `manage.py check --deploy`, verificat manual că apare/dispare corect.

## 3. Performanță

- **Fișier:** `reviews/views/product.py` (`get_context_data`, secțiunea `similare`) → **Risc:** `cu_numar_pareri(...)` calculează un `Count` cu JOIN pe comentarii pentru produsele "similare", dar acestea sunt randate cu `show_details=False` în `_product_card.html`, unde `comment_count` nici măcar nu se afișează — query irosit complet. → **Recomandare:** folosește direct `.order_by("-data_postarii")` fără `cu_numar_pareri` pentru `similare`.
  → **Status:** ✅ Rezolvat — exact cum recomandă auditul.

- **Fișier:** `reviews/queries.py` (`cu_numar_pareri`) → **Risc:** Funcția bagă un `.order_by("-data_postarii")` intern, dar aproape toți apelanții (feed, recap) re-sortează imediat după (`.order_by()` chemat din nou înlocuiește complet ordinea anterioară) — ordinea bagată e moartă în majoritatea cazurilor, ceea ce face funcția înșelătoare. → **Recomandare:** scoate `.order_by()` din `cu_numar_pareri`, lasă ordonarea explicit la fiecare apelant.
  → **Status:** ✅ Rezolvat — verificat toți cei 5 apelanți (feed, recap, api, collections) înainte de a scoate ordinea: cei fără re-sortare explicită cad oricum pe `Product.Meta.ordering` ("-data_postarii"), deci comportamentul rămâne identic.

- **Fișier:** `reviews/image_utils.py` (`MAX_DIMENSIUNE_IMPLICITA=1600`) → **Risc:** Toate imaginile (produs, galerie, colecție, comentariu) sunt redimensionate la același max (1600px lățime), dar afișate în contexte de 56–240px (thumbnail-uri, avatar, carduri) — browserul descarcă o imagine de 1600px doar ca s-o arate la 190px, risipă de bandwidth, mai ales relevantă pe mobil. → **Recomandare:** generează 1-2 variante mai mici (thumbnail) la upload, sau folosește `srcset`.
  → **Status:** ⏸ Amânat — e o feature reală (generare de variante derivate + `srcset` în toate template-urile), nu un fix punctual; implic-o separat, cu timp dedicat, dacă vrei să mergem mai departe cu ea.

- **Fișier:** `static/css/style.css` + template-urile → **Risc:** Doar imaginile din comentarii au `loading="lazy"`; pozele de card din feed, hero-ul de produs, thumbnail-urile din galerie, avatarul din Despre — toate se încarcă eager, indiferent de poziția în viewport. → **Recomandare:** `loading="lazy"` pe toate `<img>`-urile din afara viewport-ului inițial.
  → **Status:** ✅ Rezolvat — `loading="lazy"` pe cardurile de produs (feed + randare JS din cards.js), cardurile de colecție și thumbnail-urile din galeria de produs. Hero-ul de produs și avatarul din Despre au rămas eager intenționat — sunt above-the-fold, deci corect să se încarce imediat (recomandarea auditului viza explicit doar ce e "în afara viewport-ului inițial").

- **Fișier:** `reviews/views/product.py` (`ProductStoryImageView._render_with_lock`) → **Risc:** La cache-miss simultan pe același produs, cererile care pierd lock-ul fac `time.sleep(0.3)` de până la 6 ori (1.8s), blocând un worker WSGI sincron per cerere. → **Recomandare:** dacă traficul crește, mută randarea PNG într-un task de fundal (Celery/RQ) în loc de blocare sincronă.
  → **Status:** ⏸ Amânat — Celery/RQ cere un broker separat (Redis/RabbitMQ) rulat ca serviciu propriu, decizie de infra. Auditul însuși spune "dacă traficul crește" — nu urgent la volumul actual.

- **Fișier:** `reviews/models.py` (indexuri lipsă) → **Risc:** `Comment.aprobat` (filtrat în aproape fiecare view care afișează comentarii) nu are `db_index=True`, spre deosebire de `Product.nota_mea`/`sursa`/`categorie`/`activ`. `Product.pret` și `Product.il_recumpar` sunt de asemenea neindexate. → **Recomandare:** `db_index=True` pe `Comment.aprobat`; evaluează index pe `pret`/`il_recumpar` când catalogul crește.
  → **Status:** ✅ Rezolvat parțial — `db_index=True` pe `Comment.aprobat` (migrat). ⏸ Index pe `pret`/`il_recumpar` amânat — auditul însuși spune "evaluează... când catalogul crește", nu acum.

- **Fișier:** `reviews/views/api.py` (`SearchDataView`, `FavoritesDataView`) → **Risc:** Căutarea live rulează `icontains` pe `nume`/`brand` la fiecare apăsare de tastă, fără index full-text/trigram. → **Recomandare:** de urmărit; index trigram (Postgres) sau full-text search dacă/când se schimbă de la SQLite.
  → **Status:** ⏸ Amânat — cere schimbarea motorului de bază de date (SQLite → Postgres); auditul spune explicit "de urmărit", nu o acțiune imediată.

## 4. Mentenabilitate

- **Fișier:** `reviews/models.py` (`Product.stele`, `Comment.stele`) → **Risc:** Proprietăți complet moarte de cod — nimic nu le mai apelează după trecerea la `stars_svg`/`GlowStars.render`. → **Recomandare:** șterge-le sau documentează explicit "păstrat doar ca API, nefolosit intern".
  → **Status:** ✅ Rezolvat — am ales varianta "documentează" (nu șterge, la cererea ta explicită din timpul sesiunii): am adăugat comentariu clar pe ambele proprietăți.

- **Fișier:** `reviews/templatetags/glow_extras.py` (`stars_svg`) și `static/js/cards.js` (`GlowStars`) → **Risc:** Logica de randare a stelei e duplicată în Python și JavaScript. → **Recomandare:** acceptabil pe termen scurt (comentat clar), de reevaluat dacă apar mai multe variante client-side.
  → **Status:** — Nicio acțiune necesară acum — auditul însuși spune că e "acceptabil pe termen scurt".

- **Fișier:** `reviews/queries.py` (`filtreaza_produse`, docstring) → **Risc:** Docstring-ul nu mai menționează `tag`/`pret_max`, adăugate recent. → **Recomandare:** actualizează docstring-ul.
  → **Status:** ✅ Rezolvat.

- **Fișier:** `README.md` → **Risc:** Documentează doar setul vechi de funcționalități — nimic despre Tag-uri/filtre de preț, câmpurile de verdict, poze în comentarii, recap anual sau dark mode. → **Recomandare:** secțiune nouă în README pentru fiecare funcție adăugată.
  → **Status:** ✅ Rezolvat — secțiuni noi pentru Verdict, Tag-uri/preț, poze în comentarii, Recap anual, Dark mode (verificat în cod înainte de a scrie despre dark mode — nu are toggle manual, doar `prefers-color-scheme`, ca să nu documentez ceva ce nu există).

- **Fișier:** `reviews/views/recap.py` (reutilizare `MIN_PRODUSE_PENTRU_CONTOR`) → **Risc:** Constanta gândită pentru pragul contorului din feed e reutilizată ca prag de "date suficiente pentru recap" — două decizii de produs diferite legate de aceeași valoare. → **Recomandare:** o constantă separată (`MIN_PRODUSE_PENTRU_RECAP`).
  → **Status:** ✅ Rezolvat — exact cum recomandă auditul (aceeași valoare numerică, 10, dar decuplate).

- **Fișier:** `reviews/models.py` (`Product.tag_uri`) → **Risc:** Singurul câmp nou fără `help_text`, spre deosebire de `pret`/`il_recumpar`/`tine_cat`/`pentru_cine`. → **Recomandare:** adaugă `help_text`.
  → **Status:** ✅ Rezolvat.

- **Fișier:** `reviews/views/api.py`, `reviews/views/recap.py` (`[:24]`, `[:50]`, `[:3]`, `[:10]`) → **Risc:** Limite numerice inline, fără constante numite — inconsecvent cu restul codebase-ului. → **Recomandare:** extrage-le ca constante numite cu un comentariu scurt.
  → **Status:** ✅ Rezolvat — toate patru: `MAX_REZULTATE_CAUTARE`, `MAX_SLUGURI_FAVORITE` (api.py), `TOP_PRODUSE_LIMITA`, `CANDIDATI_COMENTATE_LIMITA`, `CELE_MAI_COMENTATE_LIMITA` (recap.py).

- **Fișier:** `reviews/tests.py` → **Risc:** Fișier monolitic de 700+ linii/67 teste, spre deosebire de `reviews/views/`, deja despărțit pe zone. → **Recomandare:** împarte în `tests/test_feed.py`, `tests/test_product.py` etc.
  → **Status:** ⏸ Amânat — restructurare mecanică, dar cu risc de conflicte/greșeli de mutare fără beneficiu funcțional imediat; mai are sens făcută separat, cu atenție dedicată doar ei. (Fișierul a mai crescut între timp — acum 74 de teste, cu cele adăugate azi.)

- **Fișier:** `static/css/style.css` → **Risc:** Fișier CSS unic, monolitic, peste 800 de linii și în creștere. → **Recomandare:** de reevaluat separarea pe fișiere dacă proiectul continuă să crească.
  → **Status:** ⏸ Amânat — auditul însuși spune "de reevaluat dacă proiectul continuă să crească", nu o acțiune necesară acum.

- **Fișier:** `reviews/admin.py` (`ContactMessageAdmin`) → **Risc:** `citit` nu are `list_editable`, Deea nu poate bifa rapid din lista de mesaje. → **Recomandare:** `list_editable = ("citit",)`.
  → **Status:** ✅ Rezolvat.

- **Fișier:** `requirements-dev.txt` → **Risc:** Nicio unealtă de coverage configurată. → **Recomandare:** adaugă `coverage` în CI, cu un prag minim.
  → **Status:** ✅ Rezolvat — `coverage` în `requirements-dev.txt`, config în `pyproject.toml` (`fail_under = 80`; coverage reală actuală: 88%), rulat în CI (`coverage run` + `coverage report`).

---

# PROMPT 2/5 — AUDIT UX/UI

*Bazat pe navigarea site-ului live — starea curentă publicată, nu commit-urile locale.*

## 1. Ierarhia vizuală

- **Secțiune → Acasă/Feed** → **Problemă:** Titlul, tagline-ul, paragraful de intro, bara de căutare+filtre și rândul de 13 categorii (12 needitabile) preced un singur card de produs. → **Impact:** Vizitatorul parcurge mult "mobilier" de interfață înainte de conținutul real. → **Recomandare:** simplifică/ascunde temporar interfața de filtrare cât conținutul e redus.

- **Secțiune → Cardul de produs** → **Problemă:** Poza produsului are o înălțime modestă (140px) față de restul cardului. → **Impact:** Pe un site vizual prin natură, imaginea nu domină cardul cum ar trebui. → **Recomandare:** mărește proporția pozei față de text.

- **Secțiune → Pagina de produs** → **Problemă:** Cele 3 butoane de acțiune apar imediat sub poză, înaintea notei/părerii care ar convinge vizitatorul. → **Impact:** Ierarhia cere acțiune înainte de a oferi motivul acțiunii. → **Recomandare:** mută acțiunile secundare mai jos, păstrează doar "Salvează" sus.

- **Secțiune → Despre** → **Observație pozitivă:** Ierarhia poză → titlu → text → linkuri e clară și logică.

## 2. Consistența design-ului

- **Secțiune → Tot site-ul** → **Problemă:** O singură culoare de accent (roz) pentru linkuri, badge-uri, chip-uri active și titluri — nimic nu iese ca suprafață de contrast puternic. → **Impact:** Pagina se simte plată vizual. → **Recomandare:** o singură suprafață închisă la culoare ca ancoră de contrast.

- **Secțiune → Titluri (font Unbounded)** → **Problemă:** Font display geometric, tip tech/SaaS, vs. tonul foarte personal al textului. → **Impact:** Mic decalaj între „cum arată" și „cum sună" brandul.

- **Secțiune → Butoanele de acțiune (product detail)** → **Problemă:** "Salvează" (primary) și celelalte două (secundare) au aceeași greutate vizuală, diferă doar prin bordură subțire. → **Impact:** Ierarhia de importanță nu e suficient de clară dintr-o privire.

## 3. Claritatea CTA-urilor

- **Secțiune → Card de produs** → **Problemă:** Cardul e link, dar fără text explicit ("Vezi recenzia"). → **Impact:** Vizitatorul deduce din convenție, nu din indiciu explicit.

- **Secțiune → Paragraful de intro** → **Problemă:** "Vezi colecțiile mele curate →" și linkul de Instagram sunt linkuri text simple, în mijlocul unui paragraf lung. → **Impact:** Ușor de ratat de cineva care scanează.

- **Secțiune → Bara de căutare** → **Problemă:** Butonul "Caută" există deși căutarea e deja live. → **Impact:** Buton aproape inutil, ocupă atenție.

- **Secțiune → Colecții** → **Problemă:** Cardul de colecție e clickabil integral, fără text CTA. → **Impact:** Pe mobil, fără hover, niciun indiciu vizual de „apăsabil".

- **Secțiune → Formularul de comentariu** → **Problemă:** "Trimite părerea" are aceeași greutate vizuală ca orice alt buton, deși e probabil acțiunea cea mai valoroasă pentru comunitate. → **Impact:** Nu e tratată ca CTA principal.

- **Secțiune → Tot site-ul** → **Problemă:** Niciun CTA de tip "revino"/"abonează-te". → **Impact:** Fără mecanism de a aduce vizitatorul înapoi la următoarea postare.

## 4. Fricțiuni

- **Secțiune → Rândul de categorii** → **Problemă:** 12 din 13 categorii dezactivate vizibil. → **Impact:** Comunică involuntar „conținut foarte puțin".

- **Secțiune → Tot site-ul (volum de conținut)** → **Problemă:** Un singur produs, o singură colecție, zero comentarii. → **Impact:** Interacțiunea cu filtrele/căutarea/paginarea e practic inutilă acum.

- **Secțiune → Formularul de comentariu** → **Problemă:** Nu se specifică dacă părerea apare imediat sau trece prin moderare. → **Impact:** Poate descuraja trimiterea din incertitudine.

- **Secțiune → "Descarcă pentru Story"** → **Problemă:** Detaliile (dimensiune, format) sunt doar într-un tooltip invizibil pe mobil. → **Impact:** Exact pe canalul unde acțiunea contează cel mai mult, informația lipsește.

- **Secțiune → Contact** → **Problemă:** "Dacă nu-mi place, spun și asta pe site, cu numele brandului lângă" — sinceritate reală, dar formulată ca avertisment. → **Impact:** Poate descuraja branduri nesigure să trimită produse.

- **Secțiune → Butonul de distribuire** → **Problemă:** "Copiază linkul" cere un pas în plus pe mobil față de distribuire nativă. → **Impact:** Fricțiune suplimentară exact pe mobil.

## 5. Diferențe desktop/mobil

- **Secțiune → Navigare principală** → **Problemă:** Meniul ascuns după hamburger pe mobil, vizibil direct pe desktop. → **Impact:** Un click în plus pe mobil pentru orice navigare non-Acasă.

- **Secțiune → Grid de carduri** → **Observație:** 1→2→3 coloane responsive, corect arhitectural dar netestabil vizual cu un singur produs.

- **Secțiune → Despre** → **Observație pozitivă:** Layout editorial pe desktop vs. simplu pe mobil — schimbare coerentă.

- **Secțiune → Zona sticky de căutare+filtre** → **Problemă:** Topbar + rând de filtre, ambele sticky. → **Impact:** Pe telefon, ocupă un procent vizibil din înălțimea ecranului în timpul scroll-ului.

- **Secțiune → Tooltip-uri** → **Problemă:** Detaliile despre Story sunt disponibile doar prin hover pe desktop. → **Impact:** Pe mobil informația dispare complet.

---

# PROMPT 3/5 — AUDIT DE TEXTE

*Notă: site-ul nu e o afacere B2B cu formular „Start Project"/portofoliu de proiecte — e un jurnal personal de recenzii. Aplic lentila cerută la elementele reale, notând unde conceptul cerut nu are echivalent literal.*

## Acasă / Feed

- Citat: **„Ultimele încercări"** → Problemă: descrie ce e pagina, nu ce câștigă vizitatorul. → De ce nu funcționează: neutru, pur informativ, fără motivație sau beneficiu.

- Citat: **„Real products. My honest take."** (engleză, pe site 100% românesc) → Problemă: schimbare bruscă de limbă, unică pe tot site-ul. → De ce nu funcționează: sună ca slogan de branding împrumutat, desprins de vocea naturală.

- Citat: **„Ca să știi dacă un produs chiar merită banii, înainte să-l cumperi: machiajul de aici l-am cumpărat, l-am testat și l-am evaluat eu — fără PR-uri, fără sponsorizări."** → Problemă: propoziție lungă, idee-cheie îngropată la final. → De ce nu funcționează: „fără PR-uri, fără sponsorizări" ar trebui să fie prima informație, nu ultima.

- Citat: **„Lasă și tu o părere rapidă la orice produs, fără cont."** → Problemă: diferențiator real, dar diluat în mijlocul paragrafului. → De ce nu funcționează: cititoarele care scanează rar citesc paragrafe întregi.

- Structura narativă (unde ești → risc al inacțiunii → rezultat): **absentă**. Textul sare direct la „ce facem noi", fără riscul din perspectiva cititoarei.

## Despre

- Citat: **„Salut, sunt Deea 💕"** → Observație pozitivă: tonul cald funcționează bine aici.

- Citat: **„Dacă un produs e bun, spun că e bun. Dacă nu ține cât promite eticheta, spun și asta."** → Problemă: aproape identică cu fraza similară de pe Contact. → De ce nu funcționează: repetiția de formulă slăbește impactul fiecărei apariții.

- Citat: **„Fiecare postare are nota și poza mea, cu părerea scrisă în cuvinte proprii"** → Problemă: „cu părerea scrisă în cuvinte proprii" e redundant. → De ce nu funcționează: sună ca umplutură de propoziție.

- Structura narativă: parțial prezentă, nedezvoltată ca motivație centrală.

## Colecții

- Citat: **„Produsele testate, grupate pe teme — selecții curate de Deea"** → Problemă: „selecții curate" e clișeu de marketing generic. → De ce nu funcționează: nu spune nimic concret despre beneficiul unei colecții.

- Citat: **„Mai vin colecții curând ✨"** → Problemă: promisiune vagă, fără orizont de timp. → De ce nu funcționează: nu creează nicio așteptare concretă.

## Contact

- Citat: **„Hai să vorbim"** → Problemă: titlu generic, identic cu mii de pagini de contact. → De ce nu funcționează: nu spune nimic specific despre scopul precis al paginii.

- Citat: **„Ai un produs pe care vrei să-l testez? Trimite-mi-l..."** → Observație: cel mai puternic punct de copy de pe tot site-ul. Problemă: continuarea pare adresată exclusiv brandurilor. → De ce nu funcționează pentru tot publicul: nu există nicio opțiune pentru „vreau doar să-ți scriu ceva".

- CTA-uri: un singur tip (formular) + Instagram — suficient pentru scopul real; „variante CTA: formular, consultație, portofoliu" nu are echivalent aici.

## Pagina de produs

- Citat: **„las[ă] pe ten acel glow care face pielea să arate mai vie, fără să simt"** → Problemă: pare tăiată abrupt. → De ce nu funcționează: propoziție incompletă la finalul argumentului.

- Categorie afișată: **„Altele"** → Problemă: etichetă neinformativă. → De ce nu funcționează: non-informație pentru un produs hibrid SPF+glow.

- CTA-uri (Salvează / Copiază linkul / Descarcă pentru Story): clare ca text, dar niciunul nu invită spre acțiunea cu cea mai mare valoare — lăsarea unei păreri.

---

# PROMPT 4/5 — AUDIT „PRIMA IMPRESIE"

## 1. În primele 5 secunde, ce impresie lasă site-ul?

Impresie de blog personal de beauty, cald și îngrijit vizual, nu corporate. Trei semnale împing spre „proiect abia început": rândul de categorii cu 12/13 dezactivate, stat chip-ul cu dată în loc de număr de produse, un singur card vizibil pe feed. Element pozitiv: sigiliul „TESTED BY DEEA" repetat dă senzație de brand recognoscibil. Mic decalaj: fontul de titlu geometric vs. vocea foarte personală a textului.

## 2. Se înțelege clar ce oferă brandul și pentru cine?

Da, relativ rapid, din primul paragraf. Ce nu se înțelege: nivelul de preț țintă (drugstore vs. lux) sau tipul de ten/public pentru care sunt relevante recenziile.

## 3. Portofoliul convinge — pare real și relevant, sau umplutură?

Nu, în starea actuală: un singur produs live, o singură colecție cu un singur produs. Contrastul cu infrastructura elaborată din spate (13 categorii, sortare, paginare, căutare live) accentuează senzația de site construit pentru volum viitor, dar încă necopt. Zero comentarii existente pe tot site-ul.

## 4. Ce ar face un vizitator sceptic să nu mai aibă încredere?

Volumul mic de conținut; categoriile dezactivate vizibil; absența comentariilor; linkul de Instagram fără dovadă vizibilă de audiență; tagline-ul în engleză ca unică frază non-română; categoria „Altele" pe singurul produs afișat.

## 5. Ce ar face un vizitator să rămână și să exploreze mai mult?

Sigiliul „TESTED BY DEEA"; tratamentul de citat/testimonial pentru „Părerea mea"; posibilitatea de a lăsa o părere fără cont; poza personală a Deei din Despre; tonul sincer din Contact („fără sponsorizare și fără notă garantată dinainte").

---

# PROMPT 5/5 — AUDIT DE CLARITATE ȘI UTILIZARE

## 1. Se înțelege din prima ce face brandul și ce rezolvă?

Da, dar necesită citirea paragrafului de intro complet — titlul și tagline-ul singure nu explică nimic fără context suplimentar.

## 2. Navigarea este intuitivă?

Meniul cu 5 opțiuni e clar denumit. Fricțiuni: meniul ascuns după hamburger pe mobil; niciun link rapid de tip „highlights"/"cel mai popular".

## 3. Fiecare CTA e clar în ce se întâmplă la click?

- „Vezi colecțiile mele curate →" — clar.
- **„Salvează"** → Confuzia: nu se explică înainte de click unde/cum se salvează (fără cont, doar în acel browser) — informația vine abia pe pagina Favorite. → Cum ar trebui: o mențiune scurtă lângă buton.
- **„Descarcă pentru Story"** → Confuzia: detaliile (format, dimensiune) sunt doar în tooltip, invizibil pe mobil. → Cum ar trebui: text vizibil pe buton, nu ascuns în tooltip.
- **„Copiază linkul"** → Ambiguitate reziduală doar din lipsă de test real, nu problemă confirmată.

## 4. Există pași sau formulare confuze?

- **Formularul de comentariu** → Confuzia: nu se specifică dacă apare imediat public sau trece prin moderare. → Cum ar trebui: o propoziție scurtă ar clarifica.
- **Formularul de Contact** → Confuzia: nicio așteptare stabilită despre când/cum vine răspunsul. → Cum ar trebui: „răspund de obicei în X zile".
- **Câmpul de notă din comentariu** → Confuzia: nu se explică relația dintre nota cititoarei și nota Deei. → Cum ar trebui: o propoziție care leagă cele două note.

## 5. Site-ul funcționează la fel de clar pe mobil ca pe desktop?

Structural da, dar: meniul ascuns după hamburger pe mobil; tooltip-urile despre Story dispar complet pe touch, exact pe canalul unde contează cel mai mult; rândul de categorii cere scroll lateral pe mobil.
