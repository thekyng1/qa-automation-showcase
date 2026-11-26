# 🕸️ Panza — rețeaua care nu uită

> O unealtă care nu poate fi instalată nu e aruncată — e **citită din textele ei** și
> memorată în panză. O unealtă care se instalează intră în arenă și primește verdict
> doar pe **dovadă, nu impresie**. Nimic nu intră în `legaturi` fără **proba scrisă**
> și acordul omului.

## Structura

| Fișier | Rolul |
|---|---|
| `schema.sql` | memoria: `unelte`, `resurse`, `legaturi`, `propuneri_legaturi`, `probe`, `feedback`, `teste` + FTS |
| `db.py` | poarta: `get_conn()` — `catalog.db` lângă cod; suprascrivabil cu `PANZA_DB` |
| `panza.py` | serverul web (port **8080**): `/`, `/api/sumar`, `/api/adauga`, `/api/feedback` |
| `panza-teste.py` | fereastra de teste (port **8081**, doar localhost) |
| `fire.py` | firele: adăugare cu gărzi + aprobarea propunerilor frateului |
| `feedback.py` | rezonanța: ce fire au fost folosite, în ce sarcini |
| `rating.py` | clasament pe fapte măsurate (folosiri reale) |
| `clasificare.py` | citirea onestă a unei unelte noi din textele ei |
| `puls/panza-puls.sh` | inima: verifică nodurile vii, de 2 ori pe zi (cron) |
| `puls/panza-frate.sh` | reflexul: propune legături (asemănare, complementaritate, covibrare) |
| `puls/propuneri.sql` | coada de propuneri — omul aprobă, niciodata automat |
| `teste/panza-test.py` | suita de teste (13 testul rapid, + sonda de linkuri cu `--linkuri`) |
| `panza-web.service` | unitatea systemd pentru serverul web |

## Reinvie pe orice mașină Linux / WSL (5 minute)

```bash
git clone https://github.com/thekyng1/qa-automation-showcase.git
cd qa-automation-showcase/panza

# 1. memoria (idempotent — poate fi rulat de câte ori vrei)
python3 -c "import db; db.get_conn()"

# 2. verificarea sintaxei tuturor modulelor
python3 -m py_compile db.py fire.py feedback.py rating.py clasificare.py panza.py

# 3. serverul web (într-un terminal)
python3 panza.py          # http://127.0.0.1:8080

# 4. suita de teste (în alt terminal)
python3 teste/panza-test.py
# așteptat: == FINAL: 13 trec, 0 pica, 0 sarit ==

# 5. pulsul + fratele în cron (opțional, pe server)
crontab -e
#   0 8,20 * * * /opt/panza/puls/panza-puls.sh
#   30 20 * * * /opt/panza/puls/panza-frate.sh
```

## Regulile panzei (nu se încalcă niciodată)

1. **Raport integral** — zero „[...]": toate liniile apar în log.
2. **Proba la verificare** — un nod e „viu" doar cu cod HTTP real, nu presupus.
3. **Revizuire, nu execuție sumară** — nodurile tăcute nu se șterg; se raportează.
4. **Legătura cu probă** — nicio propunere fără textul care arată DE CE.
5. **Omul decide** — fratele propune în coadă; nimic nu intră în `legaturi` automat.

## Comoara pierdută — memoria istorică

Catalogul cu 790 de noduri a fost pierdut cu serverul (era exclus de `.gitignore`
cu `*.db`). Panza reînvie cu memorie nouă — dar de data asta **DB-ul stă în repo**
sau în backup regulat, ca să nu mai moară cu niciun server.
