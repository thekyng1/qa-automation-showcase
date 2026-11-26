#!/usr/bin/env bash
# ============================================================================
# panza-frate.sh — REFLEXUL DE LEGATURI (autonomie nivel 2)
# ----------------------------------------------------------------------------
# Ce face: cauta singur posibile legaturi intre fire, pe 3 semnale:
#   1. ASEMANARE       — acelasi domeniu + capabilitati comune
#                        -> propune `alternativa_la`
#   2. COMPLEMENTARITATE — output-ul unuia seamana cu input-ul altuia
#                        -> propune `completeaza`
#   3. COVIBRARE       — fire care au rezonat in aceleasi sarcini
#                        -> propune `colaboreaza_cu`
#
# GARDI (cele mai importante linii din tot pachetul):
#   - scrie DOAR in tabela propuneri_legaturi, NICIODATA direct in legaturi
#   - fiecare propunere intra cu proba text (regula 10)
#   - deduplicare: nu propune o pereche care exista deja (in legaturi sau coada)
#   - idempotent: re-rularea nu produce duplicate
#   - NU sterge si NU respinge nimic — decizia e a omului
#
# Programare recomandata: dupa puls, o data pe zi (ex. 20:15).
# ============================================================================
set -u

DB="${PANZA_DB:-/root/muncitor/proiecte/Proiecte/catalog-app/catalog.db}"
LOGDIR="/root/panza"
DATA_ZI="$(date -u +%F)"
LOG="$LOGDIR/frate-$DATA_ZI.log"
PRAG_ASEMANARE=2     # min. capabilitati comune pt. `alternativa_la`
PRAG_COVIBRARE=2     # min. sarcini comune pt. `colaboreaza_cu`

mkdir -p "$LOGDIR"

# --- asigura tabela de coada exista (idempotent) ---
sqlite3 "$DB" < "$(dirname "$0")/propuneri.sql"

{
echo "== REFLEX LEGATURI — $DATA_ZI $(date -u +%T) UTC =="

# ---------------------------------------------------------------------------
# SEMNAL 1: ASEMANARE -> alternativa_la
# Perechi din acelasi domeniu cu >= PRAG_ASEMANARE capabilitati comune.
# ---------------------------------------------------------------------------
echo "-- Semnal 1: asemanare (alternativa_la) --"
sqlite3 -separator '|' "$DB" "
  SELECT a.nume, b.nume,
         (SELECT COUNT(*) FROM json_each(a.capabilitati) ja
          JOIN json_each(b.capabilitati) jb ON jb.value = ja.value) AS comune
  FROM unelte a JOIN unelte b
    ON a.domeniu = b.domeniu AND a.id < b.id
  WHERE (SELECT COUNT(*) FROM json_each(a.capabilitati)) >= $PRAG_ASEMANARE
    AND (SELECT COUNT(*) FROM json_each(b.capabilitati)) >= $PRAG_ASEMANARE
;" 2>/dev/null | while IFS='|' read -r A B COMUNE; do
  [ "${COMUNE:-0}" -ge "$PRAG_ASEMANARE" ] || continue
  # garda de deduplicare: exista deja legatura sau propunerea?
  EXISTA=$(sqlite3 "$DB" "
    SELECT (SELECT COUNT(*) FROM legaturi l JOIN unelte x ON x.id=l.de_la
             JOIN unelte y ON y.id=l.spre
             WHERE (x.nume='$A' AND y.nume='$B') OR (x.nume='$B' AND y.nume='$A'))
         + (SELECT COUNT(*) FROM propuneri_legaturi
             WHERE stare='propus' AND tip_legatura='alternativa_la'
               AND ((de_la_nume='$A' AND spre_nume='$B')
                 OR (de_la_nume='$B' AND spre_nume='$A')));")
  if [ "$EXISTA" = "0" ]; then
    sqlite3 "$DB" "INSERT INTO propuneri_legaturi
      (de_la_nume, spre_nume, tip_legatura, semnal, proba)
      VALUES ('$A','$B','alternativa_la','asemanare',
        'acelasi domeniu + $COMUNE capabilitati comune, verificat in SQL la $DATA_ZI');"
    echo "  PROPUSE: $A <-> $B (capabilitati comune: $COMUNE)"
  fi
done

# ---------------------------------------------------------------------------
# SEMNAL 2: COMPLEMENTARITATE -> completeaza
# Ce produce un fir (output) apare in ce consuma alt fir (input).
# ---------------------------------------------------------------------------
echo "-- Semnal 2: complementaritate (completeaza) --"
sqlite3 -separator '|' "$DB" "
  SELECT a.nume, b.nume,
         (SELECT COUNT(*) FROM json_each(a.output) ja
          JOIN json_each(b.input) jb ON jb.value LIKE '%' || ja.value || '%') AS potriviri
  FROM unelte a JOIN unelte b ON a.id <> b.id
  WHERE (SELECT COUNT(*) FROM json_each(a.output)) > 0
    AND (SELECT COUNT(*) FROM json_each(b.input)) > 0
;" 2>/dev/null | while IFS='|' read -r A B POT; do
  [ "${POT:-0}" -ge 1 ] || continue
  EXISTA=$(sqlite3 "$DB" "
    SELECT (SELECT COUNT(*) FROM legaturi l JOIN unelte x ON x.id=l.de_la
             JOIN unelte y ON y.id=l.sper
             WHERE x.nume='$A' AND y.nume='$B' AND l.tip_legatura='completeaza')
         + (SELECT COUNT(*) FROM propuneri_legaturi
             WHERE stare='propus' AND tip_legatura='completeaza'
               AND de_la_nume='$A' AND spre_nume='$B');")
  if [ "$EXISTA" = "0" ]; then
    sqlite3 "$DB" "INSERT INTO propuneri_legaturi
      (de_la_nume, spre_nume, tip_legatura, semnal, proba)
      VALUES ('$A','$B','completeaza','complementaritate',
        'output-ul lui $A se potriveste cu $POT elemente din input-ul lui $B (SQL la $DATA_ZI)');"
    echo "  PROPUSE: $A -> $B (potriviri output->input: $POT)"
  fi
done

# ---------------------------------------------------------------------------
# SEMNAL 3: COVIBRARE -> colaboreaza_cu
# Fire care au rezonat impreuna in >= PRAG_COVIBRARE sarcini.
# Sursa: istoricul de rezonanta (val-pas1b / rezonantele salvate in sarcini).
# Daca nu exista istoric de sarcini inca, semnalul raporteaza 0 — onest.
# ---------------------------------------------------------------------------
echo "-- Semnal 3: covibrare (colaboreaza_cu) --"
ISTORIC=$(ls "$HOME/.hermes/cache/scratch/"rezonanta*.json 2>/dev/null | wc -l)
echo "  Istorice de rezonanta disponibile: $ISTORIC"
if [ "$ISTORIC" -lt "$PRAG_COVIBRARE" ]; then
  echo "  SUB PRAG: nu exista inca $PRAG_COVIBRARE sarcini cu rezonanta salvata."
  echo "  Onest (regula 10): fara istoric, zero propuneri pe acest semnal."
else
  echo "  ANALIZA COVIBRARE: de implementat cand istoricul exista (nivel 2.5)."
fi

# ---------------------------------------------------------------------------
# BILANT — raport integral
# ---------------------------------------------------------------------------
echo ""
echo "== BILANT REFLEX =="
echo "Propuneri noi azi: $(sqlite3 "$DB" "SELECT COUNT(*) FROM propuneri_legaturi WHERE data_propunere='$DATA_ZI';")"
echo "In coada, in asteptare: $(sqlite3 "$DB" "SELECT COUNT(*) FROM propuneri_legaturi WHERE stare='propus';")"
echo "Aprobate de om, in asteptarea migrarii in legaturi: $(sqlite3 "$DB" "SELECT COUNT(*) FROM propuneri_legaturi WHERE stare='aprobat';")"
echo "== GATA $(date -u) =="
} >> "$LOG" 2>&1
