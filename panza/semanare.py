#!/usr/bin/env python3
# semanare.py — seamana memoria panzei cu primele ei 3 amintiri:
# EYRA, Sellbird, SqlBranch. Idempotent: poate fi rulat de cate ori vrei;
# nu face nimic daca amintirile exista deja. Regula 10: fiecare fir
# are proba scrisa; regula 9: esecul nu se sterge, se memoreaza.
import os
import sys
import uuid

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)
import db

AMINTIRI = [
    {
        "nume": "EYRA",
        "domeniu": "testare",
        "subdomeniu": "rust",
        "descriere": "Prima unealta instalata in arena panzei: cadru de testare in Rust.",
        "url_sursa": "",
        "capabilitati": ["scrie teste", "ruleaza teste", "raporteaza rezultate"],
        "input": ["fisiere sursa"],
        "output": ["raport de teste"],
        "verdict": "INSTALAT",
        "verdict_mesaj": "instalata in arena, proba: instalarea a reusit",
    },
    {
        "nume": "Sellbird",
        "domeniu": "testare",
        "subdomeniu": "e-commerce",
        "descriere": "A picat in arena, onest — dar lecția rămâne comoara panzei.",
        "url_sursa": "",
        "capabilitati": ["generare de comenzi", "verificare cos"],
        "input": ["catalog"],
        "output": ["comenzi"],
        "verdict": "ESUAT",
        "verdict_mesaj": "a picat in arena — proba: nu a putut fi instalata, dar e citita si memorata",
    },
    {
        "nume": "SqlBranch",
        "domeniu": "baze de date",
        "subdomeniu": "testare-db",
        "descriere": "Fir de testare DB: verifica interogari pe baza catalogului.",
        "url_sursa": "",
        "capabilitati": ["conectare la DB", "ruleaza interogari", "compara rezultate"],
        "input": ["SQL"],
        "output": ["diferente"],
        "verdict": "PROBAT",
        "verdict_mesaj": "folosit in sarcini reale de testare pe catalog.db",
    },
]

RESURSE_SEMNATE = [
    {
        "nume": "lectia-frate-citit",
        "tip": "text",
        "continut": ("Lectia frate-citit: o unealta care nu poate fi instalata nu e aruncata. "
                     "E citita din textele ei si memorata in panza. Sellbird e proba vie."),
        "sursa": "Sellbird",
    },
]

LEGATURA_SEMNATA = {
    "tip": "colaboreaza_cu",
    "proba": ("EYRA si SqlBranch au rezonat impreuna in aceeasi sarcini de testare — "
              "fire de panza din conversatia de origine, semanate la reinviere, 2026-11-26."),
}


def main():
    import json
    c = db.get_conn()
    try:
        ids = {}
        for a in AMINTIRI:
            exista = c.execute("SELECT id FROM unelte WHERE nume=?", (a["nume"],)).fetchone()
            if exista:
                ids[a["nume"]] = exista["id"]
                print("  deja: %s" % a["nume"])
                continue
            idnou = str(uuid.uuid4())
            ids[a["nume"]] = idnou
            c.execute(
                "INSERT INTO unelte(id, nume, domeniu, subdomeniu, descriere, url_sursa,"
                " capabilitati, input, output) VALUES (?,?,?,?,?,?,?,?,?)",
                (idnou, a["nume"], a["domeniu"], a["subdomeniu"], a["descriere"],
                 a["url_sursa"], json.dumps(a["capabilitati"], ensure_ascii=False),
                 json.dumps(a["input"], ensure_ascii=False),
                 json.dumps(a["output"], ensure_ascii=False)))
            c.execute("INSERT INTO probe(unealta_id, verdict, mesaj) VALUES (?,?,?)",
                      (idnou, a["verdict"], a["verdict_mesaj"]))
            print("  semanat: %s (%s)" % (a["nume"], a["verdict"]))

        for r in RESURSE_SEMNATE:
            exista = c.execute("SELECT id FROM resurse WHERE nume=?", (r["nume"],)).fetchone()
            if exista:
                print("  deja: resursa %s" % r["nume"])
                continue
            c.execute(
                "INSERT INTO resurse(id, nume, tip, continut, sursa) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), r["nume"], r["tip"], r["continut"], r["sursa"]))
            print("  semanat: resursa %s" % r["nume"])

        exista_leg = c.execute("SELECT COUNT(*) FROM legaturi").fetchone()[0]
        if exista_leg == 0:
            c.execute(
                "INSERT INTO legaturi(de_la, spre, tip_legatura, proba) VALUES (?,?,?,?)",
                (ids["EYRA"], ids["SqlBranch"], LEGATURA_SEMNATA["tip"],
                 LEGATURA_SEMNATA["proba"]))
            print("  semanat: fir EYRA <-> SqlBranch (colaboreaza_cu, cu proba)")

        c.commit()
        s = {t: c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
             for t in ("unelte", "resurse", "legaturi", "propuneri_legaturi")}
        print("== MEMORIA: %d unelte, %d resurse, %d legaturi, %d propuneri in coada ==" %
              (s["unelte"], s["resurse"], s["legaturi"], s["propuneri_legaturi"]))
    finally:
        c.close()


if __name__ == "__main__":
    main()
