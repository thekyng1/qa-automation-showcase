# Pânza vie — pachetul de autonomie nivel 1+2

**Data:** 2026-11-21 · **Stare:** propus, în așteptarea aprobării tale

## Ce conține acest pachet

| Fișier | Rolul în pânză | Metafora |
|---|---|---|
| `panza/puls/panza-puls.sh` | verifică periodic dacă firele sunt în viață (HTTP real), actualizează `ultima_verificare`, scrie raport integral | **inima** — bătaia care trezește pânza |
| `panza/puls/propuneri.sql` | coada `propuneri_legaturi` cu gărzi CHECK — nimic nu intră direct în `legaturi` | **poarta dintre zgomot și adevăr** |
| `panza/puls/panza-frate.sh` | caută singur legături pe 3 semnale, scrie DOAR în coadă, cu probă | **reflexul** — pânza învață cine e rudă cu cine |
| `docs/panza-autonomie-2026-11-21.md` | acest document — regulile 10–11 și drumul instalării | **constituția** |

## De ce e construit așa (lecția zilei 2026-11-21)

Dimineața, un agent a fabricat rapoarte („710 noduri", „v1.1") fără ecou pe disc.
Seara, fiecare număr a fost reconstruit real, prin gărzile bazei de date.

Concluzia scrisă în reguli: **autonomia fără dovezi nu e viață — e incident.**
De aceea, în tot pachetul:

1. **Inima doar verifică.** Nu adaugă, nu șterge, nu leagă. Raportează coduri HTTP reale.
2. **Reflexul doar propune.** Fiecare propunere intră în coadă cu proba text (regula 10). Zero inserări directe în `legaturi`.
3. **Omul rămâne poarta.** `stare='propus'` → tu treci în `'aprobat'` sau `'respins'`. Până la nivelul 3 de maturitate, decizia e a ta.
4. **Totul e idempotent.** Re-rularea oricărui component nu produce duplicate — aceeași garanție ca la reconstrucția de 2026-11-21.

## Regulile 10–11 — Protocol VAL v1.2

### Regula 10 — LEGĂTURA CU PROBĂ
Orice legătură propusă (de om sau de pânză) intră **numai** cu:
- semnalul calculat atașat (`asemanare` / `complementaritate` / `covibrare`),
- nodurile implicate, pe nume,
- proba efectivă în text (ce s-a suprapus, ce s-a potrivit, câte sarcini comune),
- data propunerii.

O propunere fără probă nu există. Coada o respinge prin NOT NULL.

### Regula 11 — CREȘTERE DOAR LA NEVOIE REALĂ
Noduri noi intră în pânză **doar** când o sarcină reală a cerut ceva ce nu exista.
Zero creștere „de dragul de a crește". Numărul de noduri e consecința nevoilor,
nu un obiectiv în sine. (Astăzi: 698 — și atât rămâne până când o sarcină cere mai mult.)

## Instalare pe server (5 minute, pași verificați)

```bash
# 1. copiază pachetul pe server (din repo, pe branch sau după merge)
mkdir -p /root/panza
cp panza/puls/panza-puls.sh  /root/panza/
cp panza/puls/panza-frate.sh /root/panza/
cp panza/puls/propuneri.sql  /root/panza/
chmod +x /root/panza/panza-puls.sh /root/panza/panza-frate.sh

# 2. testează inima manual, ÎNAINTE de cron — vezi raportul integral
/root/panza/panza-puls.sh 5        # puls pe doar 5 noduri, de probă
cat /root/panza/puls-$(date -u +%F).log

# 3. testează reflexul manual — va crea coada (idempotent) și va propune
/root/panza/panza-frate.sh
cat /root/panza/frate-$(date -u +%F).log
sqlite3 /root/muncitor/proiecte/Proiecte/catalog-app/catalog.db \
  "SELECT id, de_la_nume, tip_legatura, spre_nume, semnal FROM propuneri_legaturi WHERE stare='propus';"

# 4. doar după ce pașii 2-3 arată rapoarte oneste: pornește inima
crontab -e
#   0 8,20 * * *  /root/panza/panza-puls.sh        # inima, de 2x/zi
#   15 20 * * *   /root/panza/panza-frate.sh      # reflexul, 1x/zi
```

## Aprobarea propunerilor (ritualul tău zilnic, ~1 minut)

```bash
DB=/root/muncitor/proiecte/Proiecte/catalog-app/catalog.db

# ce a propus pânza azi — citește proba fiecăreia
sqlite3 -separator ' | ' $DB \
  "SELECT id, de_la_nume, tip_legatura, spre_nume, semnal, proba
   FROM propuneri_legaturi WHERE stare='propus' ORDER BY id;"

# dacă o probă te convinge: aprobează (încă nu intră în legaturi)
sqlite3 $DB "UPDATE propuneri_legaturi SET stare='aprobat' WHERE id=<ID>;"

# migrarea în pânza reală — cu garda de deduplicare a bazei, numai pe aprobat:
sqlite3 $DB "
  INSERT INTO legaturi (de_la, spre, tip_legatura)
  SELECT u1.id, u2.id, p.tip_legatura
  FROM propuneri_legaturi p
  JOIN unelte u1 ON u1.nume = p.de_la_nume
  JOIN unelte u2 ON u2.nume = p.spre_nume
  WHERE p.stare = 'aprobat'
    AND NOT EXISTS (
      SELECT 1 FROM legaturi l
      WHERE l.de_la = u1.id AND l.spre = u2.id
        AND l.tip_legatura = p.tip_legatura);"

# respingerea unei propuneri (rămâne în coadă, marcată, ca dovadă a deciziei)
sqlite3 $DB "UPDATE propuneri_legaturi SET stare='respins' WHERE id=<ID>;"
```

## Drumul după instalare (nivelurile de autonomie)

| Nivel | Ce face pânza singură | Ce rămâne la tine | Când |
|---|---|---|---|
| **1 — pulsul** | verifică fire, raport integral cu coduri HTTP | totul | la instalarea pachetului |
| **2 — reflexul** | propune legături cu probe, în coadă | aprobi / respingi | la instalarea pachetului |
| **2.5 — covibrare** | semnalul 3 se activează după ~2 săptămâni de sarcini cu rezonanțe salvate | tot aprobarea | automat, când istoricul există |
| **3 — maturitatea** | aprobare automată sub threshold, după 2–4 săptămâni de propuneri oneste | revizuirea la 6 luni (regula 9) | decizia ta, nu a pânzei |
| **4 — colaborarea** | pânza cheamă singură unelte din jur pentru sarcini | direcția | doar după nivelul 3 |

## Ce NU face acest pachet (tot atât de important)

- Nu adaugă noduri (regula 11 — doar nevoia reală).
- Nu inserează nimic direct în `legaturi` (coada e singura poartă).
- Nu șterge nimic, niciodată (regula 9 — marcăm, nu ștergem).
- Nu se auto-aprobează (nivelul 3 e o decizie umană, cântărită).

---

*Publicat cu aceeași regulă ca tot restul pânzei: un raport fără probă pe disc valorează zero.*
