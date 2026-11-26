#!/usr/bin/env python3
# fire.py — firele dintre nodurile panzei.
# GARDI:
#   - regula 10: nicio legatura fara proba scrisa;
#   - nu accepta dubluri (aceeasi pereche + acelasi tip);
#   - nu accepta fire orfane (ambele capete trebuie sa existe);
#   - scrie direct in `legaturi` DOAR dincoace, la aprobarea omului.
import json
import uuid

import db

TIPURI = ("alternativa_la", "completeaza", "colaboreaza_cu")


def nod_exista(c, id_nod):
    return (c.execute("SELECT 1 FROM unelte WHERE id=?", (id_nod,)).fetchone()
            or c.execute("SELECT 1 FROM resurse WHERE id=?", (id_nod,)).fetchone()) is not None


def adauga_legatura(de_la, spre, tip, proba):
    """Adauga un fir. Returneaza (ok, mesaj). Niciodata nu arunca exceptii murdare."""
    if tip not in TIPURI:
        return False, "tip_legatura invalid: %r (permise: %s)" % (tip, ", ".join(TIPURI))
    if not proba or not str(proba).strip():
        return False, "regula 10 incalcata: legatura fara proba"
    c = db.get_conn()
    try:
        if not nod_exista(c, de_la):
            return False, "nod de_la inexistent: %s" % de_la
        if not nod_exista(c, spre):
            return False, "nod spre inexistent: %s" % spre
        dublu = c.execute(
            "SELECT 1 FROM legaturi WHERE de_la=? AND spre=? AND tip_legatura=?",
            (de_la, spre, tip)).fetchone()
        if dublu:
            return False, "legatura exista deja (%s -> %s, %s)" % (de_la, spre, tip)
        c.execute(
            "INSERT INTO legaturi(de_la, spre, tip_legatura, proba) VALUES (?,?,?,?)",
            (de_la, spre, tip, str(proba)))
        c.commit()
        return True, "fir adaugat: %s -> %s (%s)" % (de_la, spre, tip)
    finally:
        c.close()


def aproba_propunere(id_propunere):
    """Muta o propunere din coada in legaturi (stare='aprobat') si crea firul.
    Omul decide; fratele doar propune. Returneaza (ok, mesaj)."""
    c = db.get_conn()
    try:
        p = c.execute("SELECT * FROM propuneri_legaturi WHERE id=?", (id_propunere,)).fetchone()
        if not p:
            return False, "propunere inexistenta: %s" % id_propunere
        if p["stare"] != "propus":
            return False, "propunerea nu mai e in asteptare (stare=%s)" % p["stare"]
        a = c.execute("SELECT id FROM unelte WHERE nume=?", (p["de_la_nume"],)).fetchone()
        b = c.execute("SELECT id FROM unelte WHERE nume=?", (p["spre_nume"],)).fetchone()
        if not a or not b:
            return False, "unul dintre noduri nu mai exista in catalog"
        c.execute("INSERT INTO legaturi(de_la, spre, tip_legatura, proba) VALUES (?,?,?,?)",
                  (a["id"], b["id"], p["tip_legatura"], p["proba"]))
        c.execute("UPDATE propuneri_legaturi SET stare='aprobat' WHERE id=?", (id_propunere,))
        c.commit()
        return True, "aprobat: %s %s %s" % (p["de_la_nume"], p["tip_legatura"], p["spre_nume"])
    finally:
        c.close()


def respinge_propunere(id_propunere):
    c = db.get_conn()
    try:
        cur = c.execute("UPDATE propuneri_legaturi SET stare='respins' WHERE id=? AND stare='propus'",
                        (id_propunere,))
        c.commit()
        if cur.rowcount:
            return True, "respins: propunerea %s" % id_propunere
        return False, "propunerea %s nu e in asteptare" % id_propunere
    finally:
        c.close()
