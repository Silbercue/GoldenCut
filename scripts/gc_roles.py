#!/usr/bin/env python3
"""gc_roles — weist jedem Text einer Messung eine Leseart (Rolle) zu.

Rollen (nach Willberg/Forssman und DIN 1450, siehe reference/schriftgroessen-abstaende.md §2):
  number    dominante Zahl (Kachel-Kennzahl, Punktestand)
  title     Schautext: Seitentitel, Kachel-Titel (h1–h3 oder deutlich groesser als Body)
  subtitle  kleinere Ueberschrift / Zwischentitel
  body      Lesetext: mehrzeilig oder laenger, in Grundgroesse
  consult   Konsultationstext: Sekundaer-/Hinweistext, Caption, Einheit, Fussnote
  label     UI-Label: kurz, an Kachel/Feld/Legende
  action    Beschriftung eines Buttons/Links

Heuristik, kein Modell: Tag, Groesse relativ zur Grundgroesse, Laenge, Zeilenzahl, Ziffern,
Versalien, interaktiver Kontext. Liefert Konfidenz 0–1; unter 0,6 wird eine Rueckfrage
in Alltagssprache formuliert. Die Rolle entscheidet, welcher Korridor gilt (gc_typo).
"""

import re
from collections import Counter

NUM_RX = re.compile(r"^[\d.,%+\-/ ×x:]+$")
HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


def text_elements(els):
    """Sichtbare Texte mit Schriftgroesse; Effekt-Kopien (gleicher Text, gleiche Groesse) werden markiert,
    die aeusserste Kopie ist die primaere."""
    texts = [e for e in els if e.get("textLen", 0) > 0 and not e.get("isIcon") and e.get("fs", 0) > 0]
    groups = {}
    for e in texts:
        key = (e["text"], round(e["fs"], 1))
        groups.setdefault(key, []).append(e)
    primaries = []
    for key, grp in groups.items():
        grp.sort(key=lambda e: (e.get("depth", 0), e["i"]))
        prim = grp[0]
        prim["dup"] = False
        prim["dupCount"] = len(grp) - 1
        ctrs = [g.get("contrast") for g in grp if g.get("contrast")]
        prim["contrastMax"] = max(ctrs) if ctrs else None
        prim["bgUncertain"] = any(g.get("bgViaImage") for g in grp)
        for g in grp[1:]:
            g["dup"] = True
        primaries.append(prim)
    primaries.sort(key=lambda e: e["i"])
    return primaries


def detect_base(texts):
    """Grundgroesse = haeufigste Groesse unter Nicht-Ziffern, Nicht-Ueberschriften (nach Zeichen gewichtet)."""
    w = Counter()
    for e in texts:
        if e["tag"] in HEADINGS or NUM_RX.match(e["text"] or ""):
            continue
        w[round(e["fs"] * 2) / 2] += max(e["textLen"], 1)
    if not w:
        w = Counter({round(e["fs"] * 2) / 2: e["textLen"] for e in texts})
    if not w:
        return 16.0
    top = max(w.values())
    cands = [fs for fs, n in w.items() if n >= top * 0.6]
    return float(min(cands)) if cands else float(w.most_common(1)[0][0])


def assign(e, base, ctx=None):
    ctx = ctx or {}
    t = e["text"] or ""
    fs, rel = e["fs"], e["fs"] / base
    n, lines = e["textLen"], e.get("lines") or 1
    tag = e["tag"]
    upper = e.get("textTransform") == "uppercase" or (n >= 2 and t.isupper() and any(c.isalpha() for c in t))
    inter = e.get("interactive") or e.get("inInteractive")
    bold = str(e.get("fw", "400")).isdigit() and int(e["fw"]) >= 600
    num = bool(NUM_RX.match(t))

    if num and rel >= 1.5:
        return "number", 0.9, "nur Ziffern, deutlich groesser als Grundgroesse"
    if tag in HEADINGS:
        if HEADINGS[tag] <= 3 or rel >= 1.25:
            return "title", 0.9, f"{tag}"
        return "subtitle", 0.85, f"{tag}, nahe Grundgroesse"
    if num and rel <= 1.1:
        return ("consult", 0.7, "Ziffern in Grundgroesse oder kleiner (Wert, Einheit, Zaehler)")
    if rel >= 1.3 and n <= 60 and lines <= 2:
        return "title", 0.7, "deutlich groesser als Grundgroesse, kurz"
    if t.startswith(("/", "(", "·")) or (rel < 0.95 and n <= 8):
        return "consult", 0.75, "Einheit/Zusatz (Praefix oder sehr kurz und kleiner)"
    if lines >= 2 or n >= 60:
        if rel < 0.9:
            return "consult", 0.7, "mehrzeilig/lang, aber kleiner als Grundgroesse"
        return "body", 0.85, "mehrzeilig oder lang"
    if ctx.get("siblingNumber") and n <= 24:
        return "label", 0.85, "Beschriftung neben einer Kennzahl"
    if ctx.get("inPill") and n <= 30:
        return "label", 0.8, "Text in einer Pille"
    if inter and tag in ("button", "a") and n <= 30:
        return "action", 0.85, "Beschriftung eines Buttons/Links"
    if upper and n <= 30:
        return "label", 0.8, "Versalien, kurz"
    if rel < 0.93:
        return "consult", 0.6, "kleiner als Grundgroesse, kurz"
    if rel >= 1.1 and n <= 40:
        return "subtitle", 0.6, "etwas groesser als Grundgroesse, kurz"
    if n <= 24:
        return "label", 0.55, "kurz in Grundgroesse"
    return "body", 0.6, "Grundgroesse, mittellang"


ROLE_DE = {"number": "Kennzahl", "title": "Titel", "subtitle": "Zwischentitel", "body": "Lesetext",
           "consult": "Nebentext", "label": "Label", "action": "Button-Text"}


def question_for(e):
    t = e["text"][:30]
    r = e["role"]
    if r == "label":
        return f"„{t}“ — ist das eine Beschriftung (Label), oder ein Text zum Lesen?"
    if r == "consult":
        return f"„{t}“ — ist das ein Nebentext (Hinweis, Einheit), oder soll man ihn wirklich lesen?"
    if r == "subtitle":
        return f"„{t}“ — ist das eine Überschrift, oder normaler Text?"
    return f"„{t}“ — welche Aufgabe hat dieser Text (Titel, Lesetext, Hinweis, Label)?"


def assign_roles(data, overrides=None):
    """Setzt role/roleConf/roleWhy an die primaeren Texte; liefert (texts, base, questions)."""
    texts = text_elements(data["elements"])
    base = detect_base(texts)
    overrides = overrides or {}
    questions = []
    by_i = {x["i"]: x for x in data["elements"]}
    # Kontext: Kennzahl als Geschwister/Onkel, Pille als Elternelement
    num_parents = set()
    for e in texts:
        if NUM_RX.match(e["text"] or "") and e["fs"] / base >= 1.5:
            par = by_i.get(e["parent"])
            for _ in range(2):
                if par is None or par["parent"] is None or par["parent"] < 0:
                    break
                num_parents.add(par["i"]); par = by_i.get(par["parent"])
    for e in texts:
        ctx = {}
        par = by_i.get(e["parent"]) if e["parent"] is not None and e["parent"] >= 0 else None
        anc = par
        for _ in range(2):
            if anc is None:
                break
            if anc["i"] in num_parents:
                ctx["siblingNumber"] = True
            r = anc.get("radius")
            pill_cls = re.search(r"(^|[\s_-])(pill|chip|tag|badge)([\s_-]|$)", anc.get("cls") or "")
            if anc["h"] <= 48 and ((r and anc["h"] > 0 and r >= anc["h"] * 0.4) or pill_cls):
                ctx["inPill"] = True
            anc = by_i.get(anc["parent"]) if anc["parent"] is not None and anc["parent"] >= 0 else None
        role, conf, why = assign(e, base, ctx)
        ov = overrides.get(e["sel"]) or overrides.get(e["text"])
        if ov:
            role, conf, why = ov, 1.0, "Config"
        e["role"], e["roleConf"], e["roleWhy"] = role, conf, why
        if conf < 0.6:
            questions.append(question_for(e))
    return texts, base, questions[:3]
