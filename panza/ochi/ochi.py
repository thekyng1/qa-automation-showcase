#!/usr/bin/env python3
# ============================================================================
# ochi.py — OCHIUL PANZEI: citeste orice site/repo si extrage DOAR TEXTUL
# ----------------------------------------------------------------------------
# Mosteneste regulile panzei:
#   * doar http(s) — ftp:// sau orice altceva: respins onest
#   * NU descarca imagini, css, js, binare — textul spune tot
#   * fiecare text citit intra in `resurse` (indexat FTS automat)
#   * idempotent: acelasi url nu se memoreaza de doua ori
# Folosire:
#   python3 ochi.py https://exemple.com
#   python3 ochi.py https://github.com/user/repo
#   python3 ochi.py --cauta "ce vrei sa afli din memoria citita"
# ============================================================================
import json
import os
import re
import sqlite3
import sys
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urlparse

DB = os.environ.get("PANZA_DB") or "/opt/panza/catalog.db"
MAX_OCTETI = 2_000_000   # 2 MB — comoara, nu puhoiul
LIMITA_S = 20            # rabdarea ochiului
UA = {"User-Agent": "PanzaOchi/1.0 (text-only research)"}
OPRITE = {"care", "astfel", "aceasta", "acest", "pentru", "poate", "site",
          "text", "more", "with", "this", "that", "from", "will"}


def url_curat(s):
    """Aceeasi onestitate ca panza.py: doar http/https, altfel respins."""
    s = (s or "").strip()
    if not s:
        raise ValueError("url invalid: gol")
    p = urlparse(s)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError(f"url invalid: schema '{p.scheme}' — doar http(s) e comoara valida")
    return s


def aduce(url):
    cer = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(cer, timeout=LIMITA_S) as r:
        octeti = r.read(MAX_OCTETI + 1)[:MAX_OCTETI]
    return octeti.decode("utf-8", errors="replace")


class Cititor(HTMLParser):
    """Colecteaza textul vizibil; sare peste script/style/svg/noscript."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bucati, self.titlu, self.subtitluri = [], "", []
        self._skip = self._in_h = 0
        self._in_titlu = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        elif tag == "title":
            self._in_titlu = True
        elif tag in ("h1", "h2", "h3"):
            self._in_h = 1
            self.bucati.append("\n\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_titlu = False
        elif tag in ("h1", "h2", "h3"):
            self._in_h = 0
            self.bucati.append("\n")
        elif tag in ("p", "li", "div", "br", "tr"):
            self.bucati.append("\n")

    def handle_data(self, data):
        if self._in_titlu:
            self.titlu += data
            return
        if self._skip or not data.strip():
            return
        if self._in_h and data.strip():
            self.subtitluri.append(data.strip()[:120])
        self.bucati.append(data)

    @property
    def text(self):
        t = re.sub(r"[ \t]+", " ", "".join(self.bucati))
        return re.sub(r"\n\s*\n+", "\n\n", t).strip()


def citeste_repo_github(url):
    """Repo github: descriere, stele, limbaj, licenta, README — doar text."""
    p = urlparse(url)
    bucati = [x for x in p.path.split("/") if x]
    if len(bucati) < 2:
        raise ValueError("url github invalid: lipseste owner/repo")
    owner, repo = bucati[0], bucati[1].removesuffix(".git")
    try:
        meta = json.loads(aduce(f"https://api.github.com/repos/{owner}/{repo}"))
    except Exception:
        meta = {}  # onest: mergem mai departe si fara stele
    titlu = meta.get("name", repo)
    antet = [f"{titlu} — {meta.get('description') or '(fara descriere)'}"]
    if meta:
        lic = (meta.get("license") or {}).get("spdx_id", "?")
        antet.append(f"limbaj: {meta.get('language', '?')} | stele: {meta.get('stargazers_count', '?')}"
                     f" | fork-uri: {meta.get('forks_count', '?')} | licenta: {lic}")
        if meta.get("topics"):
            antet.append("teme: " + ", ".join(meta["topics"]))
        antet.append(f"actualizat: {meta.get('pushed_at', '?')}")
    readme = ""
    for nume in ("README.md", "README.rst", "README.txt", "README"):
        try:
            readme = aduce(f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{nume}")
            break
        except Exception:
            continue
    sub = [l.lstrip("#").strip() for l in readme.splitlines() if l.startswith("#")][:15]
    return titlu, "\n\n".join(antet) + "\n\n" + readme, sub


def citeste_site(url):
    c = Cititor()
    c.feed(aduce(url))
    titlu = c.titlu.strip() or urlparse(url).netloc
    return titlu, c.text, c.subtitluri


def db_con():
    con = sqlite3.connect(DB)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='resurse'").fetchone():
        sys.exit(f"eroare: tabela `resurse` nu exista in {DB} — ruleaza schema.sql intai")
    return con


def memoreaza(con, titlu, url, text, sursa):
    if con.execute("SELECT id FROM resurse WHERE url=?", (url,)).fetchone():
        print("  DEJA CITIT — nu dublam memoria")
        return
    con.execute("INSERT INTO resurse (id, nume, url, tip, continut, sursa) "
                "VALUES (lower(hex(randomblob(16))), ?, ?, 'text', ?, ?)",
                (titlu[:120], url, text, sursa))
    con.commit()
    print(f"  MEMORAT: {len(text):,} caractere in `resurse` (indexat FTS)")


def cuvinte_cheie(text, n=12):
    c = Counter(w for w in re.findall(r"[a-zA-ZăâîșțĂÂÎȘȚ]{4,}", text.lower())
                if w not in OPRITE)
    return c.most_common(n)


def rezumat(titlu, text, sub):
    print(f"\n== {titlu} ==")
    if sub:
        print("-- Ce trateaza (titlurile gasite in text) --")
        for s in sub[:15]:
            print(f"  * {s}")
    print("-- Cuvinte cheie (subiectul real) --")
    print("  " + ", ".join(f"{w} ({n})" for w, n in cuvinte_cheie(text)))


def cauta(con, q):
    r = con.execute('SELECT nume, url, snippet(resurse_fts, 3, "»", "«", "…", 14) '
                    'FROM resurse_fts WHERE resurse_fts MATCH ? LIMIT 8',
                    ('"' + q.replace('"', '""') + '"',)).fetchall()
    if not r:
        print("nimic in memorie despre asta — ochiul trebuie sa citeasca intai")
        return
    for nume, url, frag in r:
        print(f"\n* {nume} — {url}\n    …{frag}…")


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    con = db_con()
    if argv[0] == "--cauta":
        if len(argv) < 2:
            print('folosire: ochi.py --cauta "cuvinte"')
            return 2
        cauta(con, " ".join(argv[1:]))
        return 0
    esecuri = 0
    for url in argv:
        try:
            url = url_curat(url)
            p = urlparse(url)
            print(f"\n-- ochiul citeste: {url}")
            if p.netloc == "github.com" and len([x for x in p.path.split("/") if x]) >= 2:
                titlu, text, sub = citeste_repo_github(url)
                sursa = titlu
            else:
                titlu, text, sub = citeste_site(url)
                sursa = p.netloc
            memoreaza(con, titlu, url, text, sursa)
            rezumat(titlu, text, sub)
        except ValueError as e:
            print(f"  RESPINS onest: {e}")
            esecuri += 1
        except Exception as e:
            print(f"  ESUAT onest: {type(e).__name__}: {e}")
            esecuri += 1
    return 1 if esecuri else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
