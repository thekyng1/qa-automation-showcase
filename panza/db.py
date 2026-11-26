#!/usr/bin/env python3
# db.py — poarta catre memoria panzei. Portabila: catalog.db sta langa cod,
# nu la o cale moarta de pe un server mort. Se poate suprascrie cu PANZA_DB.
import os
import sqlite3

DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(DIR, "schema.sql")


def cale_db():
    return os.environ.get("PANZA_DB", os.path.join(DIR, "catalog.db"))


def get_conn():
    """Deschide catalog.db, aplica schema daca lipseste (idempotent) si
    returneaza conexiunea. Testele panzei apeleaza fix aceasta functie."""
    c = sqlite3.connect(cale_db())
    c.row_factory = sqlite3.Row
    with open(SCHEMA, "r", encoding="utf-8") as f:
        c.executescript(f.read())
    c.commit()
    return c
