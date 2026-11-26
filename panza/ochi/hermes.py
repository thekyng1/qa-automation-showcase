#!/usr/bin/env python3
# ============================================================================
# hermes.py — MESAGERUL PANZEI
# ----------------------------------------------------------------------------
# Citeste textele memorate de ochi si:
#   1. RAPORTEAZA: unde e mentionata fiecare unealta, de cate ori, in ce texte
#      (asa stim ce face fiecare si ce e mai pretios in ea)
#   2. PROPUNE: unelte mentionate in ACEEASI fraza = semnal de covibrare
#      -> coada propuneri_legaturi, cu proba (fraza exacta). Omul decide.
# Folosire:
#   python3 hermes.py            # doar raportul
#   python3 hermes.py --aplica   # scrie si propunerile in coada
# ============================================================================
import os
import re
import sqlite3
import sys

DB = os.environ.get("PANZA_DB") or "/opt/panza/catalog.db"


def raport_unelte(con):
    unelte = [r[0] for r in con.execute("SELECT nume FROM unelte")]
    texte = con.execute("SELECT nume, continut FROM resurse WHERE tip='text'").fetchall()
    print("== CE STIM DESPRE FIECARE UNEALTA (din textele citite) ==")
    gasit = False
    for u in unelte:
        r = re.compile(rf"\b{re.escape(u)}\b", re.I)
        surse = [(nume, len(r.findall(txt))) for nume, txt in texte if r.search(txt)]
        if not surse:
            print(f"  {u}: inca necitita — ochiul n-a intalnit-o in niciun text")
            continue
        gasit = True
        total = sum(n for _, n in surse)
        print(f"  {u}: {total} mentiuni in {len(surse)} texte")
        for nume, n in sorted(surse, key=lambda s: -s[1])[:5]:
            print(f"      - {nume} ({n}x)")
    if not gasit:
        print("  (ochiul n-a citit inca nimic relevant — da-i URL-uri mai intai)")


def propune(con, aplica):
    unelte = [r[0] for r in con.execute("SELECT nume FROM unelte")]
    texte = con.execute("SELECT nume, continut FROM resurse WHERE tip='text'").fetchall()
    nr = 0
    for rnume, txt in texte:
        for fraza in re.split(r"(?<=[.!?])\s+", txt):
            men = sorted({u for u in unelte
                          if re.search(rf"\b{re.escape(u)}\b", fraza, re.I)})
            for i in range(len(men)):
                for j in range(i + 1, len(men)):
                    a, b = men[i], men[j]
                    deja = con.execute(
                        "SELECT 1 FROM propuneri_legaturi WHERE tip_legatura='colaboreaza_cu' "
                        "AND ((de_la_nume=? AND spre_nume=?) OR (de_la_nume=? AND spre_nume=?))",
                        (a, b, b, a)).fetchone()
                    if deja:
                        continue
                    nr += 1
                    print(f"PROPUSE: {a} <-> {b} (covibrare) — sursa: {rnume}")
                    if aplica:
                        proba = f"Hermes: mentionate impreuna in '{rnume}': «{fraza.strip()[:300]}»"
                        con.execute("INSERT INTO propuneri_legaturi "
                                    "(de_la_nume, spre_nume, tip_legatura, semnal, proba) "
                                    "VALUES (?,?,'colaboreaza_cu','covibrare',?)", (a, b, proba))
    if aplica:
        con.commit()
    print(f"\n{nr} propuneri noi " +
          ("— scrise in coada, asteapta aprobarea ta (regula 9)" if aplica
           else "— mod raport; ruleaza cu --aplica ca sa intre in coada"))


def main():
    con = sqlite3.connect(DB)
    raport_unelte(con)
    print()
    propune(con, "--aplica" in sys.argv)


if __name__ == "__main__":
    main()
