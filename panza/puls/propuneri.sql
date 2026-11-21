-- ============================================================================
-- propuneri.sql — COADA DE PROPUNERI (autonomie nivel 2)
-- ----------------------------------------------------------------------------
-- De ce exista: dimineața de 2026-11-21 a aratat ca un agent poate fabrica
-- rapoarte. Garda: orice legatura propusa de panza sta INTAI aici, cu proba
-- atasata. Nimic nu intra direct in `legaturi`. Aproba sau respinge omul
-- (pana la nivelul 3 de maturitate).
--
-- Idempotent: CREATE TABLE IF NOT EXISTS — poate fi rulat de cate ori vrei.
-- ============================================================================
CREATE TABLE IF NOT EXISTS propuneri_legaturi (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,

    -- cele doua fire implicate (nume, rezolvate in panza-frate.sh)
    de_la_nume     TEXT NOT NULL,
    spre_nume      TEXT NOT NULL,

    -- tipul de legatura — aceleasi valori ca in tabela `legaturi`
    tip_legatura   TEXT NOT NULL
                   CHECK (tip_legatura IN ('alternativa_la','completeaza',
                                           'colaboreaza_cu')),

    -- semnalul care a generat propunerea (regula 10: LEGATURA CU PROBA)
    semnal         TEXT NOT NULL
                   CHECK (semnal IN ('asemanare','complementaritate','covibrare')),

    -- proba efectiva: textul care arata DE CE e legatura (overlap, matching
    -- output->input, sarcini comune). Raportul integral il citeaza verbatim.
    proba          TEXT NOT NULL,

    -- starea propunerii — doar omul (sau nivelul 3) schimba in aprobat
    stare          TEXT NOT NULL DEFAULT 'propus'
                   CHECK (stare IN ('propus','aprobat','respins')),

    data_propunere TEXT NOT NULL DEFAULT (date('now'))
);

-- Index pe stare: raportul zilnic cauta rapid ce e in asteptare.
CREATE INDEX IF NOT EXISTS idx_propuneri_stare ON propuneri_legaturi(stare);
