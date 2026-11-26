#!/usr/bin/env bash
# ============================================================================
# panza-puls.sh — INIMA PANZEI (autonomie nivel 1)
# ----------------------------------------------------------------------------
# Ce face:
#   1. Ia un esantion de noduri din catalog si le verifica daca sunt in viata
#      (HTTP 200 / 301 / 302).
#   2. Actualizeaza ultima_verificare DOAR pentru nodurile confirmate vii.
#   3. Scrie un RAPORT INTEGRAL (regula 7) in /root/panza/puls-<data>.log.
#
# Garzi (VAL v1.1):
#   - Raport integral: zero "[...]" — toate liniile apar in log.
#   - Proba la verificare: un nod e "viu" doar cu cod HTTP real, nu presupus.
#   - Idempotent: re-rularea nu strica nimic, doar re-verifica.
#   - id-urile din `unelte` sunt TEXT (UUID) — mereu intre ghilimele in SQL.
#   - Numar doar nodurile confirmate marcate, nu presupuse.
#
# Programare recomandata (cron, de 2 ori pe zi):
#   0 8,20 * * * /root/panza/panza-puls.sh
#
# Nu face: nu adauga noduri, nu adauga legaturi, nu sterge nimic.
# ============================================================================
set -u

DB="${PANZA_DB:-/root/muncitor/proiecte/Proiecte/catalog-app/catalog.db}"
LOGDIR="/root/panza"
DATA_ZI="$(date -u +%F)"
LOG="$LOGDIR/puls-$DATA_ZI.log"
ESANTION="${1:-25}"   # cate noduri verifica per puls (default 25)

mkdir -p "$LOGDIR"

{
echo "== PULS PANZA — $DATA_ZI $(date -u +%T) UTC =="
echo ""

# --- starea de dinainte ---
NODURI_INAINTE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM unelte;")
LEGATURI_INAINTE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM legaturi;")
echo "Stare inainte: $NODURI_INAINTE noduri, $LEGATURI_INAINTE legaturi"
echo ""

# --- esantionul: cele mai vechi verificate (cele mai "flamande") ---
echo "== ESANTION ($ESANTION noduri, ordonate dupa ultima_verificare ASC) =="
sqlite3 -separator '|' "$DB" \
  "SELECT id, nume, url_sursa FROM unelte
   ORDER BY ultima_verificare ASC, id ASC LIMIT $ESANTION;" > "$LOGDIR/.esantion.tmp"

VIABILE=0; MOARTE=0
while IFS='|' read -r ID NUME URL; do
  COD=$(curl -s -o /dev/null -w '%{http_code}' -L --max-time 15 "$URL" 2>/dev/null)
  case "$COD" in
    200|301|302)
      # UPDATE-ul se numara ca reusit doar daca sqlite3 iese cu 0
      if sqlite3 "$DB" "UPDATE unelte SET ultima_verificare='$DATA_ZI' WHERE id='$ID';"; then
        VIABILE=$((VIABILE+1))
        echo "  VIU    $NUME -> HTTP $COD (marcat $DATA_ZI)"
      else
        MOARTE=$((MOARTE+1))
        echo "  TACUT  $NUME -> HTTP $COD (marcaa a picat: UPDATE esuat)"
      fi
      ;;
    *)
      MOARTE=$((MOARTE+1))
      # NU stergem si NU marcam neconfirmat aici — regula 9 cere revizuire,
      # nu executie sumara. Doar raportam.
      echo "  TACUT  $NUME -> HTTP $COD"
      ;;
  esac
done < "$LOGDIR/.esantion.tmp"
rm -f "$LOGDIR/.esantion.tmp"

echo ""
echo "== BILANT PULS =="
echo "Verificate: $((VIABILE+MOARTE)) | Vii (marcate real): $VIABILE | Tacute: $MOARTE"
echo "Noduri marcate azi cu ultima_verificare=$DATA_ZI (total in DB, inclusiv alte operatii de azi):"
sqlite3 "$DB" "SELECT COUNT(*) FROM unelte WHERE ultima_verificare='$DATA_ZI';"
echo ""
echo "== GATA $(date -u) =="
} >> "$LOG" 2>&1
