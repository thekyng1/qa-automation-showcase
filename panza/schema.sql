-- ============================================================================
-- schema.sql — MEMORIA PANZEI (idempotent: poate fi rulat de cate ori vrei)
-- ----------------------------------------------------------------------------
-- Toate tabelele panzei, refacute 1:1 dupa conversatie si dupa ce cer
-- testele salvate (panza-test.py). Nicio regula incalcata:
--   regula 7  = raport integral; regula 9 = revizuire, nu executie sumara;
--   regula 10 = orice legatura are proba scrisa.
-- ============================================================================

-- ---------- UNELTE (firele principale) ----------
CREATE TABLE IF NOT EXISTS unelte (
    id                 TEXT PRIMARY KEY,            -- UUID
    nume               TEXT NOT NULL UNIQUE,
    domeniu            TEXT NOT NULL DEFAULT '',
    subdomeniu         TEXT NOT NULL DEFAULT '',
    descriere          TEXT NOT NULL DEFAULT '',
    url_sursa          TEXT NOT NULL DEFAULT '',
    capabilitati       TEXT NOT NULL DEFAULT '[]',  -- JSON array
    input              TEXT NOT NULL DEFAULT '[]',  -- JSON array
    output             TEXT NOT NULL DEFAULT '[]',  -- JSON array
    ultima_verificare  TEXT,                        -- data ISO (doar daca VIU, nu presupus)
    creat               TEXT NOT NULL DEFAULT (date('now'))
);

CREATE INDEX IF NOT EXISTS idx_unelte_domeniu ON unelte(domeniu);

-- ---------- RESURSE (comoara citita din textele uneltelor — REA) ----------
CREATE TABLE IF NOT EXISTS resurse (
    id         TEXT PRIMARY KEY,            -- UUID
    nume       TEXT NOT NULL,
    url        TEXT NOT NULL DEFAULT '',
    tip        TEXT NOT NULL DEFAULT 'text', -- text/link/document/manifest
    continut    TEXT NOT NULL DEFAULT '',
    sursa      TEXT NOT NULL DEFAULT '',    -- numele uneltei-mama
    creat      TEXT NOT NULL DEFAULT (date('now'))
);

-- Indexul de cautare full-text, sincronizat cu triggerele de mai jos.
CREATE VIRTUAL TABLE IF NOT EXISTS resurse_fts USING fts5(
    nume, url, tip, continut, content='resurse', content_rowid='rowid'
);

-- Triggerele FTS pe care le cere testul db_triggere_fts (resurse_ai/ad/au):
CREATE TRIGGER IF NOT EXISTS resurse_ai AFTER INSERT ON resurse BEGIN
    INSERT INTO resurse_fts(rowid, nume, url, tip, continut)
    VALUES (new.rowid, new.nume, new.url, new.tip, new.continut);
END;
CREATE TRIGGER IF NOT EXISTS resurse_ad AFTER DELETE ON resurse BEGIN
    INSERT INTO resurse_fts(resurse_fts, rowid, nume, url, tip, continut)
    VALUES ('delete', old.rowid, old.nume, old.url, old.tip, old.continut);
END;
CREATE TRIGGER IF NOT EXISTS resurse_au AFTER UPDATE ON resurse BEGIN
    INSERT INTO resurse_fts(resurse_fts, rowid, nume, url, tip, continut)
    VALUES ('delete', old.rowid, old.nume, old.url, old.tip, old.continut);
    INSERT INTO resurse_fts(rowid, nume, url, tip, continut)
    VALUES (new.rowid, new.nume, new.url, new.tip, new.continut);
END;

-- ---------- LEGATURI (firele dintre noduri — doar cu acordul omului) ----------
CREATE TABLE IF NOT EXISTS legaturi (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    de_la        TEXT NOT NULL,               -- id din unelte sau resurse
    spre         TEXT NOT NULL,
    tip_legatura TEXT NOT NULL
                 CHECK (tip_legatura IN ('alternativa_la','completeaza','colaboreaza_cu')),
    proba        TEXT NOT NULL,              -- regula 10: DE CE exista firele
    creat        TEXT NOT NULL DEFAULT (date('now')),
    UNIQUE(de_la, spre, tip_legatura)
);

CREATE INDEX IF NOT EXISTS idx_legaturi_de_la ON legaturi(de_la);
CREATE INDEX IF NOT EXISTS idx_legaturi_spre  ON legaturi(spre);

-- ---------- PRODUNERI LEGATURI (coada fratelui — omul decide) ----------
-- Aceeasi structura ca in puls/propuneri.sql, ca sa functioneze si acolo,
-- si aici, indiferent care ruleaza primul. Idempotent.
CREATE TABLE IF NOT EXISTS propuneri_legaturi (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    de_la_nume      TEXT NOT NULL,
    spre_nume       TEXT NOT NULL,
    tip_legatura    TEXT NOT NULL
                     CHECK (tip_legatura IN ('alternativa_la','completeaza',
                                             'colaboreaza_cu')),
    semnal          TEXT NOT NULL
                     CHECK (semnal IN ('asemanare','complementaritate','covibrare')),
    proba           TEXT NOT NULL,
    stare           TEXT NOT NULL DEFAULT 'propus'
                     CHECK (stare IN ('propus','aprobat','respins')),
    data_propunere  TEXT NOT NULL DEFAULT (date('now'))
);

CREATE INDEX IF NOT EXISTS idx_propuneri_stare ON propuneri_legaturi(stare);

-- ---------- PROBE (arena: verdicturi PROBAT / INSTALAT / ESUAT / ANALIZA_REA) ----------
CREATE TABLE IF NOT EXISTS probe (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    unealta_id  TEXT NOT NULL REFERENCES unelte(id),
    data        TEXT NOT NULL DEFAULT (date('now')),
    verdict     TEXT NOT NULL
                CHECK (verdict IN ('PROBAT','INSTALAT','ESUAT','ANALIZA_REA')),
    mesaj       TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_probe_unealta ON probe(unealta_id);

-- ---------- FEEDBACK (ce fire au resonat, in ce sarcini) ----------
CREATE TABLE IF NOT EXISTS feedback (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nod_id    TEXT NOT NULL,                 -- id din unelte sau resurse
    sarcina   TEXT NOT NULL DEFAULT '',
    folosit   INTEGER NOT NULL DEFAULT 0,    -- 1 = a fost folosit in acea sarcina
    data      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_feedback_nod ON feedback(nod_id);

-- ---------- TESTE (suita isi scrie singura istoricul aici) ----------
CREATE TABLE IF NOT EXISTS teste (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nume      TEXT UNIQUE NOT NULL,
    categorie TEXT NOT NULL,
    descriere TEXT NOT NULL,
    fisier    TEXT NOT NULL,
    creat     TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS test_rulari (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id   INTEGER NOT NULL REFERENCES teste(id),
    data      TEXT NOT NULL DEFAULT (datetime('now')),
    stare     TEXT NOT NULL CHECK (stare IN ('trece','pica','sarit')),
    mesaj     TEXT,
    durata_ms INTEGER
);
