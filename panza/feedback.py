#!/usr/bin/env python3
# feedback.py — ce fire au resonat, in ce sarcini. Sursa covibrarii.
# GARDI: nodul trebuie sa existe; nodul inexistent nu rupe nimic,
# dar e raportat onest (testul http_feedback_nod cere fix asta).
import db


def inregistreaza(nod_id, sarcina="", folosit=False):
    """Returneaza (ok, mesaj)."""
    c = db.get_conn()
    try:
        n = (c.execute("SELECT 1 FROM unelte WHERE id=?", (nod_id,)).fetchone()
             or c.execute("SELECT 1 FROM resurse WHERE id=?", (nod_id,)).fetchone())
        if not n:
            return False, "eroare: nodul %s nu exista in panza" % nod_id
        c.execute("INSERT INTO feedback(nod_id, sarcina, folosit) VALUES (?,?,?)",
                  (nod_id, str(sarcina), 1 if folosit else 0))
        c.commit()
        return True, "feedback inregistrat pentru %s" % nod_id
    finally:
        c.close()
