#!/usr/bin/env python3
# panza-test.py — suita de teste a pânzei. Fiecare test se autoregistrează în DB
# (nume, categorie, descriere, LOCUL = fișierul), iar fiecare rulare lasă urmă.
# Un test trece doar pe fapte măsurate acum; nimic presupus.
#
# Folosire:
#   python teste/panza-test.py                # toate testele rapide (~30s)
#   python teste/panza-test.py --linkuri      # + sondă de linkuri în cloud
#   python teste/panza-test.py --linkuri --max 25
import json, os, py_compile, socket, subprocess, sys, time
import urllib.request, urllib.error

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR)
import db

BASE = "http://127.0.0.1:8080"
FISIER = "teste/panza-test.py"      # locul suitei — apare în interfață

def init(c):
    c.executescript("""
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
    """)
    c.commit()

def srv_sus():
    try:
        s = socket.create_connection(("127.0.0.1", 8080), timeout=3); s.close()
        return True
    except OSError:
        return False

def http_get(cale, timeout=5):
    with urllib.request.urlopen(BASE + cale, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")

def http_post_json(cale, obj, timeout=5):
    req = urllib.request.Request(BASE + cale, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")

# ---------- A. BAZA DE DATE (memoria) ----------
def db_sumar():
    c = db.get_conn()
    n = {t: c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
         for t in ("unelte", "resurse", "legaturi")}
    if n["unelte"] < 1 or n["resurse"] < 1 or n["legaturi"] < 1:
        return "pica", "memoria goala sau aproape goala: %s" % n
    return "trece", "unelte=%d resurse=%d legaturi=%d" % (n["unelte"], n["resurse"], n["legaturi"])

def db_fire_orfane():
    c = db.get_conn()
    n = c.execute("""
        SELECT COUNT(*) FROM legaturi l
        WHERE (l.de_la NOT IN (SELECT id FROM unelte UNION SELECT id FROM resurse))
           OR (l.spre  NOT IN (SELECT id FROM unelte UNION SELECT id FROM resurse))
    """).fetchone()[0]
    if n == 0:
        return "trece", "zero fire orfane — tot ce e legat exista"
    return "pica", "%d fire orfane (spre noduri care nu exista)" % n

def db_triggere_fts():
    c = db.get_conn()
    t = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'resurse_%'")]
    lipsa = [x for x in ("resurse_ai", "resurse_ad", "resurse_au") if x not in t]
    if lipsa:
        return "pica", "lipsesc triggerele FTS: %s — cautarea ar putea minti" % lipsa
    return "trece", "FTS sincronizat (insert/update/delete -> index)"

def db_propuneri_cu_proba():
    c = db.get_conn()
    bad = c.execute("SELECT COUNT(*) FROM propuneri_legaturi "
                    "WHERE proba IS NULL OR trim(proba)=''").fetchone()[0]
    if bad:
        return "pica", "%d propuneri FARA proba — regula 10 incalcata" % bad
    n = c.execute("SELECT COUNT(*) FROM propuneri_legaturi WHERE stare='propus'").fetchone()[0]
    return "trece", "%d propuneri in asteptare, toate cu proba" % n

# ---------- B. INTERFATA (ferestrele) ----------
def http_acasa():
    if not srv_sus(): return "sarit", "panza-web nu raspunde pe 8080"
    cod, _ = http_get("/")
    if cod == 200: return "trece", "GET / -> 200"
    return "pica", "GET / -> %d" % cod

def http_api_sumar():
    if not srv_sus(): return "sarit", "server oprit"
    cod, trup = http_get("/api/sumar")
    if cod == 200 and "unelte" in trup:
        return "trece", "GET /api/sumar -> 200 cu numaratoare reale"
    return "pica", "GET /api/sumar -> %d %r" % (cod, trup[:60])

# ---------- C. VALIDARE INPUT (tot ce primeste se testeaza) ----------
# Doar cai de RESPINGERE: nu scriem nimic real in panza. Calea de acceptare
# o testam separat, pe o baza temporara — pasul urmator, nu azi.
def http_url_invalid():
    if not srv_sus(): return "sarit", "server oprit"
    cod, trup = http_post_json("/api/adauga", {"url": "notaurl"})
    if "invalid" in trup.lower():
        return "trece", "input murdar respins onest: %r" % trup[:40]
    return "pica", "input invalid ACCEPTAT (cod %d): %r" % (cod, trup[:40])

def http_url_ftp():
    if not srv_sus(): return "sarit", "server oprit"
    cod, trup = http_post_json("/api/adauga", {"url": "ftp://exemplu.ro/x"})
    if "invalid" in trup.lower():
        return "trece", "ftp:// respins — doar http(s) e comoara valida"
    return "pica", "ftp:// acceptat (cod %d): %r" % (cod, trup[:40])

def http_url_gol():
    if not srv_sus(): return "sarit", "server oprit"
    cod, trup = http_post_json("/api/adauga", {"url": "   "})
    if cod != 200 or "invalid" in trup.lower():
        return "trece", "gol respins (cod %d): %r" % (cod, trup[:40])
    return "pica", "gol ACCEPTAT: %r" % trup[:40]

def http_feedback_nod_inexistent():
    if not srv_sus(): return "sarit", "server oprit"
    cod, trup = http_post_json("/api/feedback",
        {"nod_id": "test-inexistent-000", "sarcina": "proba", "folosit": False})
    if cod == 500 and "eroare" in trup:
        return "trece", "nod inexistent tratat curat (500+eroare, nu crash)"
    if cod == 200:
        return "trece", "nod inexistent inregistrat fara sa rupa nimic"
    return "pica", "comportament neasteptat: %d %r" % (cod, trup[:60])

# ---------- D. INFRASTRUCTURA (inima si reflexul) ----------
def infra_cron():
    out = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    lipsa = [x for x in ("panza-puls.sh", "panza-frate.sh") if x not in out]
    if lipsa:
        return "pica", "lipsesc din cron: %s" % lipsa
    return "trece", "inima si reflexul sunt in crontab"

def infra_serviciu():
    r = subprocess.run(["systemctl", "is-active", "panza-web"], capture_output=True, text=True)
    if r.stdout.strip() == "active":
        return "trece", "panza-web active (supravietuieste restarturilor)"
    return "pica", "panza-web: %s" % r.stdout.strip()

def infra_sintaxa():
    lipsa = []
    for f in ("panza.py", "fire.py", "db.py", "feedback.py", "rating.py", "clasificare.py"):
        try:
            py_compile.compile(os.path.join(DIR, f), doraise=True)
        except Exception as e:
            lipsa.append("%s: %s" % (f, e))
    if lipsa:
        return "pica", "; ".join(lipsa)[:300]
    return "trece", "toate modulele compileaza (zero erori de sintaxa)"

# ---------- E. LINKURI IN CLOUD (sonda) ----------
def linkuri_cloud(max_n):
    c = db.get_conn()
    urls = [r[0] for r in c.execute(
        "SELECT url_sursa FROM unelte WHERE url_sursa LIKE 'http%' "
        "UNION ALL SELECT url FROM resurse WHERE url LIKE 'http%'")]
    if not urls:
        return "sarit", "niciun URL de sondat"
    pas = max(1, len(urls) // max_n)
    esantion = urls[::pas][:max_n]
    vii, tacute = [], []
    for u in esantion:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "panza-test/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                cod = r.status
            ok = 200 <= cod < 400
        except urllib.error.HTTPError as e:
            cod, ok = e.code, e.code in (401, 403)   # login/plata = viu, dar inchis
        except Exception as e:
            cod, ok = str(e)[:40], False
        (vii if ok else tacute).append((u[:55], cod))
    if tacute:
        return "pica", "%d/%d tacute: %s" % (len(tacute), len(esantion),
               "; ".join("%s->%s" % t for t in tacute)[:250])
    return "trece", "%d/%d vii: %s" % (len(vii), len(esantion),
           "; ".join("%s->%s" % t for t in vii)[:250])

# ---------- motor ----------
def ruleaza(c, nume, categorie, descriere, fn):
    c.execute("INSERT OR IGNORE INTO teste(nume,categorie,descriere,fisier) VALUES (?,?,?,?)",
              (nume, categorie, descriere, FISIER))
    tid = c.execute("SELECT id FROM teste WHERE nume=?", (nume,)).fetchone()[0]
    c.commit()  # FIX: elibereaza lock-ul de scriere INAINTE ca testul sa ruleze
    t0 = time.time()
    try:
        stare, mesaj = fn()
    except Exception as e:
        stare, mesaj = "pica", "exceptie: %s" % e
    ms = int((time.time() - t0) * 1000)
    c.execute("INSERT INTO test_rulari(test_id,stare,mesaj,durata_ms) VALUES (?,?,?,?)",
              (tid, stare, str(mesaj)[:500], ms))
    c.commit()
    print("%s  %-30s %s" % ({"trece":"OK ","pica":"PIC","sarit":"SRT"}[stare], nume, str(mesaj)[:110]))
    return stare

def main():
    with_linkuri = "--linkuri" in sys.argv
    max_n = 10
    if "--max" in sys.argv:
        try:
            max_n = int(sys.argv[sys.argv.index("--max") + 1])
        except (IndexError, ValueError):
            sys.exit("eroare: --max fara valoare intreaga")
    c = db.get_conn()
    init(c)
    print("== TESTE PANZA — %s UTC ==" % time.strftime("%Y-%m-%d %H:%M", time.gmtime()))
    A, B, C, D, E = ("A. Baza de date", "B. Interfata", "C. Validare input",
                     "D. Infrastructura", "E. Linkuri in cloud")
    rez = [
        ruleaza(c, "db_sumar", A, "numaratoare reala: unelte, resurse, legaturi — memoria nu e goala", db_sumar),
        ruleaza(c, "db_fire_orfane", A, "zero fire catre noduri care nu exista", db_fire_orfane),
        ruleaza(c, "db_triggere_fts", A, "cautarea full-text e sincronizata cu tabela resurse", db_triggere_fts),
        ruleaza(c, "db_propuneri_cu_proba", A, "regula 10: orice propunere are proba scrisa", db_propuneri_cu_proba),
        ruleaza(c, "http_acasa", B, "pagina principala raspunde 200", http_acasa),
        ruleaza(c, "http_api_sumar", B, "API-ul de sumar da numaratoare reale", http_api_sumar),
        ruleaza(c, "http_url_invalid", C, "text fara http respins, nu acceptat orbeste", http_url_invalid),
        ruleaza(c, "http_url_ftp", C, "ftp:// respins — doar http(s) e valida", http_url_ftp),
        ruleaza(c, "http_url_gol", C, "URL gol / spatii respins", http_url_gol),
        ruleaza(c, "http_feedback_nod", C, "feedback pe nod inexistent nu rupe serverul", http_feedback_nod_inexistent),
        ruleaza(c, "infra_cron", D, "pulsul si fratele sunt in crontab", infra_cron),
        ruleaza(c, "infra_serviciu", D, "panza-web e sub systemd, activ", infra_serviciu),
        ruleaza(c, "infra_sintaxa", D, "toate scripturile panzei compileaza", infra_sintaxa),
    ]
    if with_linkuri:
        rez.append(ruleaza(c, "linkuri_cloud", E,
            "esantion de %d URL-uri din panza raspund in cloud" % max_n,
            lambda: linkuri_cloud(max_n)))
    t = {"trece": 0, "pica": 0, "sarit": 0}
    for r in rez:
        t[r] += 1
    print("== FINAL: %d trec, %d pica, %d sarite ==" % (t["trece"], t["pica"], t["sarit"]))

if __name__ == "__main__":
    main()
