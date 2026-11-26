#!/usr/bin/env python3
# rating.py — cine sunt firele bune ale panzei, pe fapte nu pe impresii.
# Scorul unui nod = de cate ori a fost folosit in sarcini reale, ajustat
# cu vechimea verificarii (un nod nevizitat de mult e raportat mai slab).
import time

import db


def scor(nod_id):
    """Returneaza (scor, detaliu). Scop: onestie masurabila, zero fabulari."""
    c = db.get_conn()
    try:
        n = c.execute("SELECT 1 FROM unelte WHERE id=?", (nod_id,)).fetchone()
        if not n:
            return 0, "nod inexistent"
        folosiri = c.execute(
            "SELECT COUNT(*) FROM feedback WHERE nod_id=? AND folosit=1", (nod_id,)).fetchone()[0]
        verif = c.execute(
            "SELECT ultima_verificare FROM unelte WHERE id=?", (nod_id,)).fetchone()[0] or ""
        return folosiri, "folosit de %d ori; ultima verificare: %s" % (folosiri, verif or "niciodata")
    finally:
        c.close()


def clasament(limita=10):
    """Topul firelor panzei, cu proba in mesaj (regula 7: raport integral)."""
    c = db.get_conn()
    try:
        randuri = c.execute("""
            SELECT u.nume, COUNT(f.id) AS folosiri,
                   COALESCE(u.ultima_verificare, 'niciodata') AS verif
            FROM unelte u
            LEFT JOIN feedback f ON f.nod_id = u.id AND f.folosit = 1
            GROUP BY u.id
            ORDER BY folosiri DESC, u.nume ASC
            LIMIT ?
        """, (limita,)).fetchall()
        return [(r["nume"], r["folosiri"], r["verif"]) for r in randuri]
    finally:
        c.close()
