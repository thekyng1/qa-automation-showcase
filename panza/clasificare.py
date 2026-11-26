#!/usr/bin/env python3
# clasificare.py — cum citeste panza o unealta noua: nume, url, text.
# Extrage: numele, domeniul, subdomeniul, descrierea, capabilitati,
# input si output (toate JSON). Fara AI fabricat: doar extragere onesta
# din textele uneltei (README, titlu, descriere) — REA ramanand acelasi
# principiu: nicio comoara necitita.
import json
import re
import urllib.parse


def extrage_nume(text, url=""):
    """Numele din url (github.com/x/Nume -> Nume) sau primul titlu din text."""
    if url:
        m = re.search(r"([^/]+?)(?:\.git)?/?$", url.rstrip("/"))
        if m and m.group(1):
            return m.group(1)
    m = re.search(r"^#\s*(.+)$", text or "", re.MULTILINE)
    return m.group(1).strip() if m else ""


def extrage_domeniu(text, url=""):
    text = (text or "").lower()
    domeniile = {
        "automatizare": ["automat", "workflow", "pipeline", "ci/cd"],
        "testare": ["test", "qa", "assert", "verific"],
        "baze de date": ["sql", "database", "sqlite", "postgres", "mysql"],
        "web": ["web", "html", "http", "api", "endpoint"],
        "securitate": ["securit", "vulnerab", "pentest", "hash"],
        "productivitate": ["productiv", "todo", "agenda", "calendar"],
    }
    for domeniu, cuvinte in domeniile.items():
        for cuv in cuvinte:
            if cuv in text:
                return domeniu
    return "neclasificat"


def extrage_subdomeniu(text, url=""):
    """Subdomeniul: portiunea din url dupa owner (github.com/x/Y -> Y)."""
    if url:
        parti = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
        if len(parti) >= 2:
            return parti[1].replace(".git", "")
    m = re.search(r"^##\s*(.+)$", (text or ""), re.MULTILINE)
    return m.group(1).strip().lower() if m else ""


def extrage_capabilitati(text):
    """Capabilitati = primele verbe/pagini de feature din text."""
    text = text or ""
    cap = []
    # cautam liste de tipul "- face X" sau "* face X"
    for m in re.finditer(r"^[\-\*]\s+([a-zăâîșț][^:\n]{3,60})", text, re.MULTILINE):
        cap.append(m.group(1).strip().rstrip("."))
        if len(cap) >= 5:
            break
    return cap


def extrage_descriere(text):
    """Descrierea = primul paragraf ne-gol, ne-titlu."""
    for paragraf in (text or "").split("\n\n"):
        p = paragraf.strip()
        if p and not p.startswith("#") and not p.startswith("```"):
            return p[:300]
    return ""


def clasifica(text, url=""):
    """Returneaza un dictionar gata de INSERT in tabela unelte."""
    nume = extrage_nume(text, url)
    return {
        "nume": nume or "fara-nume",
        "domeniu": extrage_domeniu(text, url),
        "subdomeniu": extrage_subdomeniu(text, url),
        "descriere": extrage_descriere(text),
        "capabilitati": json.dumps(extrage_capabilitati(text), ensure_ascii=False),
        "input": "[]",
        "output": "[]",
    }
