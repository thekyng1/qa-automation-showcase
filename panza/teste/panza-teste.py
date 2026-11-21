#!/usr/bin/env python3
# panza-teste.py — fereastra spre sanatatea panzei (port 8081, doar localhost).
# Arata: fiecare test, LOCUL lui in cod, ultima stare, mesajul, istoricul.
import os, subprocess, sys
from http.server import HTTPServer, BaseHTTPRequestHandler

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)
import db

def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def pagina():
    c = db.get_conn()
    randuri = c.execute("""
        SELECT t.nume, t.categorie, t.descriere, t.fisier,
               (SELECT r.stare FROM test_rulari r WHERE r.test_id=t.id ORDER BY r.id DESC LIMIT 1),
               (SELECT r.data  FROM test_rulari r WHERE r.test_id=t.id ORDER BY r.id DESC LIMIT 1),
               (SELECT r.mesaj FROM test_rulari r WHERE r.test_id=t.id ORDER BY r.id DESC LIMIT 1),
               (SELECT COUNT(*) FROM test_rulari r WHERE r.test_id=t.id)
        FROM teste t ORDER BY t.categorie, t.nume
    """).fetchall()
    if not randuri:
        trup = "<p>Niciun test inregistrat inca — ruleaza <code>teste/panza-test.py</code> o data.</p>"
    else:
        cul = {"trece": "#16a34a", "pica": "#dc2626", "sarit": "#d97706", None: "#94a3b8"}
        l = ["<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse'>",
             "<tr><th>Test</th><th>Categorie</th><th>Loc in cod</th><th>Ultima stare</th>"
             "<th>Ultimul mesaj</th><th>Cand</th><th>Rulari</th></tr>"]
        for (nume, cat, descr, fis, stare, data, mesaj, n) in randuri:
            l.append("<tr><td><b>%s</b><br><small>%s</small></td><td>%s</td><td><code>%s</code></td>"
                     "<td><b style='color:%s'>%s</b></td><td><small>%s</small></td>"
                     "<td><small>%s</small></td><td>%d</td></tr>"
                     % (esc(nume), esc(descr), esc(cat), esc(fis),
                        cul.get(stare), stare or "niciodata", esc(mesaj or ""),
                        esc(data or "-"), n))
        l.append("</table>")
        trup = "".join(l)
    return ("<html><head><meta charset='utf-8'><title>Teste panza</title></head>"
            "<body style='font-family:monospace;max-width:1200px;margin:20px auto'>"
            "<h2>🕸️ Testele panzei — locul, starea, istoricul</h2>"
            "<form method='POST' action='/ruleaza'><button>Ruleaza acum suita rapida</button></form>"
            "<p>%s</p></body></html>" % trup)

class H(BaseHTTPRequestHandler):
    def _send(self, trup, code=200, ctype="text/html; charset=utf-8"):
        b = trup.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/"):
            self._send(pagina())
        else:
            self._send("nu exista", 404)

    def do_POST(self):
        if self.path == "/ruleaza":
            subprocess.run([sys.executable, os.path.join(DIR, "teste", "panza-test.py")],
                           cwd=DIR, capture_output=True, timeout=300)
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
        else:
            self._send("nu exista", 404)

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    print("panza-teste pornita: http://127.0.0.1:8081")
    HTTPServer(("127.0.0.1", 8081), H).serve_forever()
