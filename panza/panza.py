#!/usr/bin/env python3
# panza.py — SERVERUL PANZEI (port 8080). Interfata si API-ul.
#
# Rute:
#   GET  /                — pagina principala (HTML, sumar + clasament + mesaj)
#   GET  /api/sumar       — numaratoare reala (unelte, resurse, legaturi, propuneri)
#   POST /api/adauga      — adauga o unealta noua (respinge ftp://, gol, non-http)
#   POST /api/feedback    — inregistreaza rezonanta (nod, sarcina, folosit)
#
# GARDI:
#   - input murdar respins onest, cu explicatie, nu acceptat orbeste;
#   - doar http(s) e comoara valida;
#   - nimic nu rupe serverul: orice exceptie -> JSON de eroare curat.
import json
import os
import sys
import uuid
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
import feedback as fb
import rating

from http.server import HTTPServer, BaseHTTPRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def sumar(c):
    return {
        "unelte": c.execute("SELECT COUNT(*) FROM unelte").fetchone()[0],
        "resurse": c.execute("SELECT COUNT(*) FROM resurse").fetchone()[0],
        "legaturi": c.execute("SELECT COUNT(*) FROM legaturi").fetchone()[0],
        "propuneri": c.execute(
            "SELECT COUNT(*) FROM propuneri_legaturi WHERE stare='propus'").fetchone()[0],
    }


def pagina_principala(mesaj=""):
    c = db.get_conn()
    try:
        s = sumar(c)
        top = rating.clasament(10)
        randuri = "".join(
            "<li>%s — %s folosiri, verificat: %s</li>" % (esc(n), f, esc(v))
            for n, f, v in top)
        mesaj_html = ("<p style='color:#070'>%s</p>" % esc(mesaj)) if mesaj else ""
        return ("<html><head><meta charset='utf-8'><title>Panza</title></head>"
                "<body style='font-family:monospace;max-width:900px;margin:30px auto'>"
                "<h2>🕸️ Panza</h2>%s"
                "<p>Fire: <b>%d</b> unelte · <b>%d</b> resurse · <b>%d</b> legaturi · "
                "<b>%d</b> propuneri in asteptare</p>"
                "<h3>Clasament (pe fapte, nu impresii)</h3><ul>%s</ul>"
                "<h3>Adauga o comoara</h3>"
                "<form method='POST' action='/api/adauga'>"
                "<input name='url' placeholder='https://github.com/...' size='60'>"
                "<button>Împletește</button></form>"
                "</body></html>"
                % (mesaj_html, s["unelte"], s["resurse"], s["legaturi"], s["propuneri"],
                   randuri or "<li>panza e tanara — inca nicio rezonanta</li>"))
    finally:
        c.close()


def valideaza_url(url):
    """Returneaza (ok, mesaj). Doar http(s), fara spatii, fara gol."""
    url = (url or "").strip()
    if not url:
        return False, "url invalid: gol"
    if " " in url:
        return False, "url invalid: contine spatii"
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, "url invalid: schema %r — doar http(s) e comoara valida" % parsed.scheme
    if not parsed.netloc:
        return False, "url invalid: lipseste host-ul"
    return True, "ok"


class Handler(BaseHTTPRequestHandler):
    def _send(self, trup, code=200, ctype="text/html; charset=utf-8"):
        b = trup.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _send_json(self, obj, code=200):
        self._send(json.dumps(obj, ensure_ascii=False), code, "application/json; charset=utf-8")

    def _redirect(self, mesaj):
        self.send_response(303)
        self.send_header("Location", "/?mesaj=" + urllib.parse.quote(str(mesaj)))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            mesaj = qs.get("mesaj", [""])[0]
            self._send(pagina_principala(mesaj))
        elif self.path == "/api/sumar":
            c = db.get_conn()
            try:
                self._send_json(sumar(c))
            finally:
                c.close()
        else:
            self._send_json({"eroare": "nu exista"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else "{}"
        era_json = raw.lstrip().startswith("{")
        # acceptam JSON si form-encoded — interfața trimite form
        try:
            if era_json:
                date = json.loads(raw)
            else:
                date = {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}
        except Exception:
            date = {}

        if self.path == "/api/adauga":
            ok, mesaj = valideaza_url(date.get("url"))
            if not ok:
                if era_json:
                    self._send_json({"eroare": mesaj}, 400)
                else:
                    self._redirect(mesaj)
                return
            import clasificare
            c = db.get_conn()
            try:
                nume = clasificare.extrage_nume("", date.get("url", ""))
                idnou = str(uuid.uuid4())
                c.execute("INSERT INTO unelte(id, nume, url_sursa) VALUES (?,?,?)",
                          (idnou, nume or "fara-nume", date.get("url", "")))
                c.commit()
                if era_json:
                    self._send_json({"ok": "adaugat", "id": idnou, "nume": nume})
                else:
                    self._redirect("comoara impletita: %s" % (nume or "fara-nume"))
            except Exception as e:
                if era_json:
                    self._send_json({"eroare": "nu am putut adauga: %s" % e}, 500)
                else:
                    self._redirect("nu am putut adauga: %s" % e)
            finally:
                c.close()
        elif self.path == "/api/feedback":
            ok, mesaj = fb.inregistreaza(date.get("nod_id", ""),
                                         date.get("sarcina", ""),
                                         bool(date.get("folosit")))
            if not ok:
                if era_json:
                    self._send_json({"eroare": mesaj}, 500)
                else:
                    self._redirect(mesaj)
            else:
                if era_json:
                    self._send_json({"ok": mesaj})
                else:
                    self._redirect(mesaj)
        else:
            self._send_json({"eroare": "nu exista"}, 404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("panza pornita: http://127.0.0.1:8080")
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
