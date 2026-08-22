#!/usr/bin/env python3
"""gc_layout — Bauschritt 2: Ordnung und Aufteilung beurteilen (nur Urteil, kein Patch).

Liest eine Messung (gc_measure, before.json) und prueft die Beziehungen ZWISCHEN den Elementen —
das, was die Einzelmass-Pruefung (gc_analyze) nicht sieht. Gemessen wird, wie der Grafiker misst
(D4): von Versalkante/Grundlinie zum Nachbarn, nicht von Zeilenkasten zu Zeilenkasten.

  Reihenfolge des Urteils (Prinzip seit 2026-08-22, Versagensanalyse Probedurchlauf):
    Zugehoerigkeit erkennen (gleiche Klasse/Rolle/Reihe) → Konsistenz IN der Gruppe als hartes Gate →
    Ordnung ZWISCHEN den Gruppen → erst zuletzt die Reihe (gc_analyze). Abstaende werden zwischen Massen
    gemessen, Text und Grafik gleich, das dominante Element bestimmt die Zeile.

  Gruppen (Familie G — neu)
    G1  Geschwister        gleiche Klasse + gleicher Elternteil/Reihe → identische Innenmasse (Hoehe, Breite,
                           Polster, Luecken; bei Chips Polster um den Text). Abweichung > 1 px knapp, > 2 px
                           Verstoss. HARTES GATE: ein G1-Verstoss deckelt „Ordnung" bei 50 %.
    G3  Stellung           Ueberschriften gleicher Rolle und Groesse sitzen in jeder Kachel gleich (Polster oben, links)
    G2  Polaritaet         hell-auf-dunkel-Text wirkt groesser/fetter als dunkel-auf-hell — Hinweis, kein Gate
  Ordnung (Familie C, mathematische-prinzipien-ui.md §3; regeln.md P8/P9)
    C1  Naehe-Ordnung      innen < aussen (hart); Soll aussen = innen·φ ±10 % (P8)
    C2  Ueberschrift       Abstand oben > unten; Konvention oben ≈ unten·φ…φ² (≈ 2–2,5 : 1), weiche Toleranz
    C8  Titel-Bindung      in der Kachel: Titel→Text ≤ Zeile→Zeile ≤ Text→naechster Block;
                           Soll Titel→Text ≈ Zeile/φ, Soll Block = Zeile·φ (Ueberschrift gehoert zum Folgenden)
    C3  Polster an Schrift Innenabstand ≥ x-Hoehe des Haupttexts (hart), Soll ≈ Versalhoehe des Haupttexts (A4);
                           gilt fuer Grafik (Balken, Icon) genauso wie fuer Schrift
    C9  Grafik-Rand        Balken/Kasten am Kachelrand: links = rechts = unten (gleiches Polster)
    B4  Randkanon          Polster unten ≥ oben (R5)
    B6  Radien             r_innen = r_aussen − Polster (konzentrisch)
    B8  Chip↔Kachel        Chip-Hoehe = Kachel-Hoehe / φⁿ (n ganz; Beobachtung φ²) — weiche Relation
    M1  Gemalte Kante      bei Bild-/9-Slice-Kacheln: sichtbare Kante aus dem Screenshot, Einzug zur CSS-Box (Hinweis)
    C4  Rhythmus           vertikale Strecken als Vielfache der Grund-Zeilenhoehe (Reste)
    C5  Kanten             Anzahl linker Ausrichtungskanten im Scope
  Aufteilung (Familie B)
    B1  Stapel-Teilung     die Stapelgrenze, die einer φ-Teilung (38,2 / 61,8 %) am naechsten liegt — nie 50 % (R1/K3)
    B3  Optische Mitte     Inhaltsblock einer zentriert gebauten Kachel bei 46 % der Hoehe (R6/P10, ±1,5 %)
  Gesamtbild (Familie E, Ngo/Teo/Byrne 2003) — Zahlen, keine Gates
    E1  Balance            Drehmoment der Flaechen um die Mittelachsen (Objekte werden an der Achse geteilt)
    E2  Gleichgewicht      EM = 1 − (|EMx| + |EMy|)/2, EMx = 2·Σaᵢ(xᵢ−xc)/(n·b·Σaᵢ)
    E3  Dichte             Objektflaeche / Rahmenflaeche (Tullis-Band 0,3–0,5, nur Hinweis)
    E4  Wert-Entropie      wie viele verschiedene Abstandswerte (Ruhe, nur Hinweis)

Grundsatz 5 (SKILL.md): Der Skill urteilt nach Vorgaben und Mathematik — nie danach, was sich „aendern
laesst". Jede verletzte Relation bekommt ein Soll; Nicht-Anwendbarkeit wird genannt, nicht verschwiegen.

Bekannte Grenzen: Die Stapel-Analyse ist eindimensional (Zeilen nach y). Spalten-Layouts pro Spalte als
Scope messen. Kachel-Erkennung braucht sichtbare Kaesten (Farbe, Rahmen, Schatten, Bild, interaktiv).

Aufruf:
  gc_layout.py <before.json> --out DIR [--config goldencut.config.json] [--suffix ""]
  → layout-report.md, layout.json, layout-overlay.png, Klartext + Aenderungen auf stdout
"""

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gc_analyze import DEFAULT_CFG, build_series, fmt, nearest  # noqa: E402
from gc_roles import ROLE_DE, assign_roles  # noqa: E402

PHI = (1 + 5 ** 0.5) / 2
TALL = set("bdfhkltßÄÖÜ")   # Kleinbuchstaben mit Oberlaenge + Umlaut-Versalien: Zeile reicht bis zur Versalkante
LN = math.log

DEFAULT = {
    "tileMinArea": 0.02,      # Anteil der Scope-Flaeche ODER absolute Mindestgroesse (tileMinW × tileMinH)
    "tileMinW": 120,
    "tileMinH": 44,           # px: darunter ist ein Kasten ein Chip (Pille, Knopf), keine Kachel
    "tileMaxArea": 0.85,
    "ratioTol": 0.10,         # C1: ±10 % um φ (P8)
    "headingBand": [PHI, PHI * PHI],
    "headingTol": 0.06,       # C2: weiche Toleranz (schriftgroessen-abstaende §9.3)
    "edgeTol": 1.0,           # px: Kanten gelten als gleich
    "edgesTarget": 4,         # C5: Ziel „eine Kante je Hierarchieebene" — Hausgroesse, kein Gate
    "densityBand": [0.30, 0.50],
    "opticalCenter": 0.46, "opticalTol": 0.015,   # R6 / P10
    "rhythmTol": 0.06,        # C4: Rest (normiert, ½-Schritte erlaubt → Zufall ≈ 0,125)
    "splitTol": 0.03,         # B1: ±3 % auf a/b (P1), logarithmisch
    "balanceOk": 0.85, "equilibriumOk": 0.90,    # E1/E2: Hausgroessen, keine Gates
    "siblingTol": 1.0,        # G1/G3: px, bis hierhin „gleich" (Nudges < 1 px sind Rauschen)
    "siblingSoft": 2.0,       # G1/G3: px, bis hierhin „knapp", darueber Verstoss
    "sizeSimilar": 0.15,      # Gruppen: Mitglieder duerfen sich in Hoehe/Breite um 15 % unterscheiden (sonst getrennte Gruppen)
    "titleTol": 0.10,         # C8: ±10 % um Zeile/φ bzw. Zeile·φ
    "chipStepTol": 0.20,      # B8: |n − round(n)| ≤ 0,2 Stufen (≈ ±10 %)
    "paintedScan": 14,        # M1: so viele CSS-px von der Box-Kante nach innen nach Tinte suchen
    "gateCap": 50,            # G1-Verstoss deckelt Ordnung bei diesem Wert
}

RANK = {"ok": 0, "info": 0, "knapp": 1, "verstoß": 2}


# ------------------------------------------------------------------ Geometrie

def area(e):
    return max(0.0, e["w"]) * max(0.0, e["h"])


def overlap_x(a, b):
    return min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])


def overlap_y(a, b):
    return min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])


def label(e):
    name = e["tag"] + ("." + e["cls"].split(" ")[0] if e["cls"] else "")
    if e.get("text"):
        name += f' „{e["text"][:18]}{"…" if len(e["text"]) > 18 else ""}“'
    return name


def logdev(a, b):
    """relative Abweichung im Logarithmus: |ln(a/b)|"""
    return abs(LN(a / b)) if a > 0 and b > 0 else float("inf")


# ------------------------------------------------------------------ Struktur

class Layout:
    def __init__(self, data, cfg, lcfg):
        self.d = data
        self.cfg = cfg
        self.lc = lcfg
        self.els = data["elements"]
        self.fonts = data.get("fonts") or {}
        self.scope = self.els[0]
        self.children = defaultdict(list)
        for e in self.els:
            if e["parent"] is not None and e["parent"] >= 0:
                self.children[e["parent"]].append(e)
        sp = cfg["spacing"]
        self.spacing = build_series(sp["bases"], sp["ratio"], sp["min"], sp["max"], sp["round"])
        self.findings = []
        self.relations = []    # (rule, ok, weight)
        self.glob = {"balance": 1.0, "bmv": 0, "bmh": 0, "equilibrium": 1.0, "centroid": [0, 0], "density": 0,
                     "entropy": 0, "distinctSpacings": 0, "spacingSamples": 0, "objects": 0}
        self.rhythm = {"unit": 0, "meanRest": 0, "n": 0}
        self.edges = {"all": 0, "strong": []}
        self.calm_parts = {"kanten": 100, "werte": 100, "rhythmus": 100}
        self.texts, self.base, _ = assign_roles(data, {})
        self.role = {e["i"]: e["role"] for e in self.texts}
        self.tiles = self.find_tiles()
        self.tile_ids = {t["i"] for t in self.tiles}
        self.chips, self.leaves = self.find_leaves()
        self.unit = self.body_unit()
        self.groups = self.find_groups()
        self.gate = {"capped": False, "raw": None}
        self.painted = {}
        self.c8_heads = set()   # Ueberschriften, die C8 in der Kachel beurteilt — C2 zaehlt dort nicht doppelt

    # ---------------------------------------------------------------- Klassen
    def ancestors(self, e):
        p = e["parent"]
        while p is not None and p >= 0:
            yield self.els[p]
            p = self.els[p]["parent"]

    def in_absolute(self, e):
        return any(a["position"] in ("absolute", "fixed") for a in self.ancestors(e))

    def visible_box(self, e):
        if e["hasBox"] or e["interactive"]:
            return True
        # Pseudo-Element als Flaeche nur, wenn das Element selbst Inhalt traegt und kein reiner Grid-/Flex-Wrapper ist
        if e.get("hasPseudo") and e["position"] == "relative" and e["allTextLen"] > 0:
            kids = self.children[e["i"]]
            wrapper = e["display"] in ("flex", "grid", "inline-flex") and len(kids) >= 2 and all(k["hasBox"] or k["interactive"] for k in kids)
            return not wrapper
        return False

    def find_tiles(self):
        A = area(self.scope)
        min_area = min(self.lc["tileMinArea"] * A, self.lc["tileMinW"] * self.lc["tileMinH"])
        cands = []
        for e in self.els[1:]:
            if e["h"] < self.lc["tileMinH"] or e["w"] < 40:
                continue
            a = area(e)
            if a < min_area or a > self.lc["tileMaxArea"] * A:
                continue
            if not self.visible_box(e):
                # Kachel mit absolut positioniertem Hintergrund-Kind (Bild/Flaeche ≈ eigene Box) → Eltern adoptieren
                bg = [k for k in self.children[e["i"]] if k["position"] == "absolute" and (k["hasBox"] or k["tag"] in ("img", "canvas", "svg", "picture"))
                      and area(k) >= 0.85 * a]
                if not bg:
                    continue
            cands.append(e)
        ids = {c["i"] for c in cands}
        tiles = [e for e in cands if not any(a["i"] in ids for a in self.ancestors(e))]
        tiles.sort(key=lambda t: (round(t["y"]), t["x"]))
        return tiles

    def find_leaves(self):
        """Sichtbare Massen unterhalb der Kacheln:
        chips  = kleine sichtbare Kaesten mit Inhalt (Pille, Knopf, Listenzeile mit Rahmen) — zaehlen als Ganzes
        leaves = Texte, Icons, textlose Kaesten (Balken, Bilder)
        Absolut positionierte Elemente sind Deko (Blatt in der Ecke, Flagge) und zaehlen nicht zur Struktur."""
        chips, leaves = [], []
        chip_ids = set()
        for e in self.els[1:]:
            if e["i"] in self.tile_ids or e["position"] in ("absolute", "fixed") or self.in_absolute(e):
                continue
            if any(a["i"] in chip_ids for a in self.ancestors(e)):
                continue  # Inhalt eines Chips: der Chip vertritt ihn
            is_text = e["textLen"] > 0 and e["fs"] > 0
            boxed = e["hasBox"] or e["interactive"]
            if boxed and e["w"] >= 16 and e["h"] >= 12 and e["allTextLen"] > 0 and (not is_text or (e["pt"] + e["pb"] + e["pl"] + e["pr"] > 0)):
                chips.append(e); chip_ids.add(e["i"]); continue
            is_box = (not is_text and e["allTextLen"] == 0 and e["hasBox"] and e["w"] >= 8 and e["h"] >= 4
                      and not any(a["hasBox"] and a["allTextLen"] == 0 and a["i"] not in self.tile_ids for a in self.ancestors(e)))
            if e["isIcon"] or is_text or is_box:
                if is_text and any(a["textLen"] > 0 and a["text"] == e["text"] and abs(a["fs"] - e["fs"]) < 0.01 for a in self.ancestors(e)):
                    continue  # Effekt-Kopie (Wash/Schatten-Overlay)
                leaves.append(e)
        return chips, leaves

    # ---------------------------------------------------------------- Massen-Boxen (D4, Massen-Konvention 2026-08-22)
    def metrics(self, e):
        fm = self.fonts.get(e.get("fontKey") or "") or {}
        return (fm.get("xHeight") or 0.5), (fm.get("capHeight") or 0.7), not fm

    def fmetrics(self, e):
        fm = self.fonts.get(e.get("fontKey") or "") or {}
        return {"xh": fm.get("xHeight") or 0.5, "cap": fm.get("capHeight") or 0.7,
                "digit": fm.get("digitHeight") or fm.get("capHeight") or 0.7,
                "asc": fm.get("ascent"), "desc": fm.get("descent"), "est": not fm}

    def gbox(self, e):
        """Sichtbare Masse eines Elements (Massen-Konvention):
        Text  — Grundlinie je Zeile aus den Schriftmetriken (Zeilenoben + halber Durchschuss + Ascent);
                y0 = Kante nach oben (Versalkante, wenn die Zeile Versalien/Ziffern/Oberlaengen hat, sonst x-Hoehe),
                y1 = letzte Grundlinie (Unterlaengen sind duenn und zaehlen nicht),
                mass0 = Oberkante der Schriftmasse der ersten Zeile (x-Hoehe bei Gemischtschrift,
                        Versal-/Ziffernhoehe bei reinen Versalien/Ziffern) — das ist die Kante, die das Auge
                        zwischen zwei Zeilen liest (Durchschuss wirkt als Lücke Grundlinie → x-Hoehe).
        Grafik — Elementbox (Balken, Icon, Bild); mass0 = y0. Grafik ist Inhalt wie Schrift.
        dict x0,y0,x1,y1,mass0,kind,e (+ base0, lh, n, xh bei Text)."""
        if e["textLen"] > 0 and e["fs"] > 0:
            m = self.fmetrics(e); fs = e["fs"]
            n = max(1, e.get("lines") or 1)
            # line-height: normal -> aus der Boxhoehe OHNE Padding schaetzen (h/n zaehlte Padding als Zeilenhoehe)
            lh = e.get("lh") or max(1.0, (e["h"] - (e.get("pt") or 0) - (e.get("pb") or 0)) / n)
            top = e["textTop"] if e.get("textTop") is not None else e["y"]
            # textTop ist die Oberkante des SCHRIFTKASTENS (Range-Rect des Textknotens = Ascent+Descent), nicht des
            # Zeilenkastens — der halbe Durchschuss liegt darueber. Grundlinie = textTop + Ascent. Pixel-geprueft
            # 2026-08-22 (Cabin lh normal und lh 22,25; Bilderbuch-Ziffern mit negativem Durchschuss): ±0,3 px.
            if m["asc"]:
                base0 = top + m["asc"] * fs
            elif e.get("textTop") is not None:
                # Messung mit textTop (Schriftkasten-Oberkante), aber ohne Ascent: Naeherung asc ≈ cap + 0,10 em
                base0 = top + (m["cap"] + 0.10) * fs
            else:   # ganz alte Messung (nur Zeilenkasten): Versalbox symmetrisch im Zeilenkasten
                base0 = top + lh - max(0.0, (lh - m["cap"] * fs) / 2)
            txt = e.get("text") or ""
            has_lower = any(c.islower() for c in txt)
            has_tall = any(c.isupper() or c.isdigit() or c in TALL for c in txt)
            digits_only = txt.strip() != "" and all(c.isdigit() or c in " .,/%+-" for c in txt.strip())
            mass_h = (m["xh"] if has_lower else (m["digit"] if digits_only else m["cap"])) * fs
            edge_h = (m["cap"] if has_tall else m["xh"]) * fs
            x0 = e.get("textMinLeft") if e.get("textMinLeft") is not None else (e.get("textLeft") if e.get("textLeft") is not None else e["x"])
            x1 = e.get("textMaxRight") if e.get("textMaxRight") is not None else (x0 + (e.get("lineMaxW") or e["w"]))
            return {"x0": x0, "y0": base0 - edge_h, "x1": x1, "y1": base0 + lh * (n - 1),
                    "mass0": base0 - mass_h, "base0": base0, "lh": lh, "n": n, "xh": m["xh"] * fs,
                    "massh": mass_h, "kind": "text", "e": e}
        kind = "icon" if e["isIcon"] else "box"
        return {"x0": e["x"], "y0": e["y"], "x1": e["x"] + e["w"], "y1": e["y"] + e["h"], "mass0": e["y"], "kind": kind, "e": e}

    def tbox(self, t):
        return {"x0": t["x"], "y0": t["y"], "x1": t["x"] + t["w"], "y1": t["y"] + t["h"], "kind": "tile", "e": t}

    def body_unit(self):
        cands = [e for e in self.texts if abs(e["fs"] - self.base) < 0.3]
        lhs = [e["lh"] / e["fs"] for e in cands if e.get("lh")]
        q = sorted(lhs)[len(lhs) // 2] if lhs else 1.4
        return self.base * q

    def tile_of(self, e):
        for a in [e] + list(self.ancestors(e)):
            if a["i"] in self.tile_ids:
                return self.els[a["i"]]
        return None

    def tile_label(self, t):
        kids = sorted((e for e in self.leaves if e["textLen"] > 0 and self.tile_of(e) is t), key=lambda e: (e["y"], e["x"]))
        base = t["tag"] + ("." + t["cls"].split(" ")[0] if t["cls"] else "")
        return base + (f' „{kids[0]["text"][:14]}“' if kids else "")

    def name(self, e):
        return self.tile_label(e) if e["i"] in self.tile_ids else label(e)

    def add(self, rule, cat, e, prop, ist, soll, level, note, weight=1.0, unit="px", count=True, group=None):
        dev = None
        if isinstance(ist, (int, float)) and isinstance(soll, (int, float)):
            if unit in ("%", "pp"):
                dev = round(ist - soll, 1)                       # Prozentpunkte
            elif soll:
                dev = round((ist - soll) / soll * 100, 1)
        t = self.tile_of(e)
        self.findings.append({"rule": rule, "cat": cat, "label": self.name(e), "sel": e["sel"], "prop": prop,
                              "ist": round(ist, 2) if isinstance(ist, (int, float)) else ist,
                              "soll": round(soll, 2) if isinstance(soll, (int, float)) else soll,
                              "dev": dev, "level": level, "note": note, "unit": unit, "group": group,
                              "box": [e["x"], e["y"], e["w"], e["h"]],
                              "tileBox": [t["x"], t["y"], t["w"], t["h"]] if t is not None else None})
        if count and level != "info":
            self.relations.append((rule, level == "ok", weight))

    # ---------------------------------------------------------------- Struktur-Abfragen
    def items(self):
        """Alles, was im Stapel als Masse sichtbar ist: Kacheln, freie Chips, freie Blaetter (als Boxen)."""
        out = [self.tbox(t) for t in self.tiles]
        out += [self.gbox(c) for c in self.chips if self.tile_of(c) is None]
        out += [self.gbox(e) for e in self.leaves if self.tile_of(e) is None]
        return out

    def rows(self, boxes=None):
        boxes = sorted(boxes if boxes is not None else self.items(), key=lambda b: b["y0"])
        rows = []
        for b in boxes:
            R = rows[-1] if rows else None
            if R and b["y0"] < R["y1"] - 1:
                R["items"].append(b); R["y0"] = min(R["y0"], b["y0"]); R["y1"] = max(R["y1"], b["y1"])
            else:
                rows.append({"items": [b], "y0": b["y0"], "y1": b["y1"]})
        return rows

    def content(self, tile):
        """Inhalt einer Kachel als Glyph-Boxen: Texte (Zeilen/Polster) getrennt von Icons/Boxen/Chips."""
        texts = [self.gbox(e) for e in self.leaves if e["textLen"] > 0 and self.tile_of(e) is tile]
        other = [self.gbox(e) for e in self.leaves if e["textLen"] == 0 and self.tile_of(e) is tile]
        other += [self.gbox(c) for c in self.chips if self.tile_of(c) is tile]
        return texts, other

    def text_lines(self, boxes):
        """Inhaltszeilen: das DOMINANTE Element (groesste Schrift) bestimmt Kante, Masse und Grundlinie der Zeile;
        kleinere Elemente, die es vertikal ueberlappen (Nenner „/120", Legendenpunkt, Icon), werden aufgenommen,
        verlaengern die Zeile aber nicht. Reine Grafikzeilen = Vereinigung ihrer Boxen."""
        rows = []
        key = lambda b: (-(b["e"]["fs"] if b["kind"] == "text" else 0), b["y0"])
        for b in sorted(boxes, key=key):
            placed = False
            for R in rows:
                d = R["dom"]
                ov = min(b["y1"], d["y1"]) - max(b["y0"], d["y0"])
                hb = max(1.0, b["y1"] - b["y0"]); cb = (b["y0"] + b["y1"]) / 2
                # aufnehmen: halbe Hoehe ueberlappt ODER die Mitte des Kleineren liegt (mit 30 % Luft) im Dominanten —
                # ein tiefer gestellter Nenner „/120" haengt unter der Ziffern-Grundlinie und gehoert trotzdem zur Zeile
                if ov >= 0.5 * min(hb, max(1.0, d["y1"] - d["y0"])) or (d["y0"] - 0.3 * hb <= cb <= d["y1"] + 0.3 * hb):
                    R["members"].append(b)
                    if d["kind"] != "text":
                        R["y0"] = min(R["y0"], b["y0"]); R["y1"] = max(R["y1"], b["y1"]); R["mass0"] = R["y0"]
                    placed = True
                    break
            if not placed:
                rows.append({"dom": b, "members": [b], "y0": b["y0"], "y1": b["y1"], "mass0": b.get("mass0", b["y0"])})
        rows.sort(key=lambda R: R["y0"])
        return rows

    def content_rows(self, tile):
        texts, other = self.content(tile)
        return self.text_lines(texts + other)

    def row_label(self, R):
        e = R["dom"]["e"]
        if R["dom"]["kind"] == "text":
            return "„" + (e.get("text") or "")[:12] + ("…" if len(e.get("text") or "") > 12 else "") + "“"
        if R["dom"]["kind"] == "icon":
            return "Icon"
        return "Balken" if (R["y1"] - R["y0"]) < (max(b["x1"] for b in R["members"]) - min(b["x0"] for b in R["members"])) * 0.5 else "Kasten"

    def inner_gaps(self, tile):
        """Luecken zwischen Inhaltszeilen: Grundlinie (bzw. Unterkante Grafik) → Schriftmasse/Oberkante der naechsten."""
        rows = self.content_rows(tile)
        return [round(b["mass0"] - a["y1"], 2) for a, b in zip(rows, rows[1:]) if b["mass0"] - a["y1"] > 0.5]

    def row_gaps(self, tile):
        """ALLE Reihenpaar-Luecken (auch ≤ 0,5/negative) — fuer Geschwister-Signaturen, damit „Luecke n"
        bei jedem Mitglied dasselbe Reihenpaar meint und der Index nicht verrutscht."""
        rows = self.content_rows(tile)
        return [round(b["mass0"] - a["y1"], 2) for a, b in zip(rows, rows[1:])]

    def gap_list(self, tile):
        """Lesbare Folge fuer Bericht/Klartext: [(von, nach, luecke)], Zeile→Zeile bei mehrzeiligem Text eingeschoben."""
        rows = self.content_rows(tile)
        out = []
        for a, b in zip(rows, rows[1:]):
            da = a["dom"]
            if da["kind"] == "text" and da.get("n", 1) > 1:
                out.append(("Zeile→Zeile in " + self.row_label(a), "", round(da["lh"] - da.get("massh", da["xh"]), 2)))
            out.append((self.row_label(a), self.row_label(b), round(b["mass0"] - a["y1"], 2)))
        if rows:
            db = rows[-1]["dom"]
            if db["kind"] == "text" and db.get("n", 1) > 1:
                out.append(("Zeile→Zeile in " + self.row_label(rows[-1]), "", round(db["lh"] - db.get("massh", db["xh"]), 2)))
        return out

    def insets(self, tile, boxes):
        if not boxes:
            return None
        tb = self.tbox(tile)
        return {"top": min(b["y0"] for b in boxes) - tb["y0"], "bottom": tb["y1"] - max(b["y1"] for b in boxes),
                "left": min(b["x0"] for b in boxes) - tb["x0"], "right": tb["x1"] - max(b["x1"] for b in boxes)}

    def neighbour_gaps(self, tile):
        """Abstaende zu allen Nachbarn (Kacheln, Chips, freie Blaetter) in vier Richtungen."""
        tb = self.tbox(tile)
        out = []
        for o in self.items():
            if o["e"] is tile:
                continue
            if overlap_x(o, tb) > 10:
                if o["y0"] >= tb["y1"] - 1:
                    out.append(o["y0"] - tb["y1"])
                if o["y1"] <= tb["y0"] + 1:
                    out.append(tb["y0"] - o["y1"])
            if overlap_y(o, tb) > 10:
                if o["x0"] >= tb["x1"] - 1:
                    out.append(o["x0"] - tb["x1"])
                if o["x1"] <= tb["x0"] + 1:
                    out.append(tb["x0"] - o["x1"])
        return [g for g in out if g > 0.5]

    # ---------------------------------------------------------------- Gruppen (Zugehoerigkeit, seit 2026-08-22)
    def ckey(self, e, freq=None):
        """Gruppenschluessel: die im Pool HAEUFIGSTE Klasse des Elements (nicht die erste — „pill pill--a" und
        „pill--a pill" muessen denselben Schluessel liefern); ohne Klassen der Tag."""
        toks = [t for t in (e["cls"] or "").split(" ") if t]
        if not toks:
            return e["tag"]
        if not freq:
            return toks[0]
        return max(toks, key=lambda t: (freq.get(t, 0), -toks.index(t)))

    def group_label(self, g):
        n = len(g["members"])
        if g["kind"] == "tile":
            return f"Kacheln .{g['key']} ({n})"
        if g["kind"] == "chip":
            return f"Chips .{g['key']} ({n})"
        return f"Überschriften {g['key']} ({n})"

    def find_groups(self):
        """Zugehoerigkeit: Kacheln/Chips mit gleicher Klasse, die denselben Elternteil haben oder in einer Reihe
        stehen und aehnlich gross sind; Ueberschriften gleicher Rolle und Groesse ueber Kacheln hinweg.
        Jede Kachel wird sonst einzeln geprueft — genau das hat im Probedurchlauf die Geschwister auseinandergezogen."""
        groups = []
        sim = self.lc["sizeSimilar"]
        for kind, pool in (("tile", self.tiles), ("chip", self.chips)):
            freq = Counter(t for e in pool for t in (e["cls"] or "").split(" ") if t)
            by_key = defaultdict(list)
            for e in pool:
                by_key[self.ckey(e, freq)].append(e)
            for key, members in by_key.items():
                if len(members) < 2:
                    continue
                clusters = []
                struct = {}
                if kind == "tile":   # Reihen-Struktur: gleiche Anzahl und Art der Inhaltszeilen
                    for e in members:
                        struct[e["i"]] = tuple(R["dom"]["kind"] for R in self.content_rows(e))
                for e in sorted(members, key=lambda m: (round(m["y"]), m["x"])):
                    for c in clusters:
                        o = c[0]
                        in_row = overlap_y(self.tbox(o), self.tbox(e)) > 0.5 * min(o["h"], e["h"])
                        # gleicher Elternteil allein reicht im vertikalen Stapel nicht — zwei verschiedene
                        # „card"-Kacheln in einer Spalte sind keine Geschwister; dann muss die Struktur passen
                        same = in_row or (o["parent"] == e["parent"] and struct.get(o["i"]) == struct.get(e["i"]))
                        if same and logdev(o["h"], e["h"]) <= LN(1 + sim):
                            c.append(e); break
                    else:
                        clusters.append([e])
                for c in clusters:
                    if len(c) >= 2:
                        groups.append({"kind": kind, "key": key, "members": c})
        heads = [e for e in self.leaves if e["textLen"] > 0 and self.role.get(e["i"]) in ("title", "subtitle") and self.tile_of(e) is not None]
        by_fs = defaultdict(list)
        for h in heads:
            by_fs[(self.role[h["i"]], round(h["fs"] * 2) / 2)].append(h)
        for (role, fs), members in by_fs.items():
            first = {}
            for h in sorted(members, key=lambda m: (m["y"], m["x"])):
                first.setdefault(self.tile_of(h)["i"], h)     # je Kachel zaehlt die erste Ueberschrift
            if len(first) >= 2:
                groups.append({"kind": "heading", "key": f"{ROLE_DE[role]} {fmt(fs)} px", "members": list(first.values())})
        for g in groups:
            g["label"] = self.group_label(g)
        return groups

    def chip_texts(self, c):
        out = []
        for e in self.els:
            if e is c or e["textLen"] == 0 or e["fs"] <= 0 or e["position"] in ("absolute", "fixed") or self.in_absolute(e):
                continue
            if not any(a is c for a in self.ancestors(e)):
                continue
            if any(a["textLen"] > 0 and a["text"] == e["text"] and abs(a["fs"] - e["fs"]) < 0.01 for a in self.ancestors(e)):
                continue  # Effekt-Kopie
            out.append(self.gbox(e))
        return out

    def sig_tile(self, t):
        """Innenmasse einer Kachel, die Geschwister teilen muessen."""
        texts, other = self.content(t)
        sig = {"Höhe": t["h"], "Breite": t["w"]}
        ins = self.insets(t, texts + other)
        if ins:
            sig.update({"Polster oben": ins["top"], "Polster unten": ins["bottom"], "Polster links": ins["left"], "Polster rechts": ins["right"],
                        "Mitte-Versatz": (ins["left"] - ins["right"]) / 2})
        for i, g in enumerate(self.row_gaps(t)):
            sig[f"Lücke {i + 1}"] = g
        return sig

    @staticmethod
    def compare_keys(keys, sigs):
        """Ausrichtung entscheidet, welche Seitenmasse Geschwister teilen muessen (nur Kacheln/Ueberschriften —
        Chips umschliessen ihren Text, dort zaehlen beide Seiten):
        zentriert (Mitte-Versatz ≈ 0 bei der MEHRHEIT — nicht bei allen, sonst versteckt genau der gesuchte
        Ausreisser die Zentrierung) → die Mitte zaehlt, die Seiten haengen von der Textbreite ab;
        randbuendig → die buendige Seite zaehlt, die offene Seite ist Textlaenge (kein Designmass).
        Liefert (keys, notiz) — die Auslassung wird im Befund GENANNT, nicht verschwiegen (Grundsatz 5)."""
        sides = [k for k in ("Polster links", "Polster rechts", "Stellung links") if k in keys]
        if "Mitte-Versatz" not in keys or not sides:
            return keys, ""
        centered = sum(1 for sg in sigs if abs(sg["Mitte-Versatz"]) <= 1.5) * 2 >= len(sigs)
        if centered:
            drop = set(sides)
            note = "; nicht verglichen: " + ", ".join(sides) + " (zentriert gebaut — Textbreite bestimmt sie, die Mitte zählt)"
        else:
            drop = {"Mitte-Versatz"}
            note = "; nicht verglichen: Mitte-Versatz (randbündig)"
            if "Polster links" in keys and "Polster rechts" in keys:
                ml = sum(sg.get("Polster links", 0) for sg in sigs) / len(sigs)
                mr = sum(sg.get("Polster rechts", 0) for sg in sigs) / len(sigs)
                far = "Polster rechts" if ml <= mr else "Polster links"
                drop.add(far)
                note = f"; nicht verglichen: {far} (Inhaltslänge, kein Designmaß) und Mitte-Versatz"
        return [k for k in keys if k not in drop], note

    def sig_chip(self, c):
        sig = {"Höhe": c["h"]}
        tx = self.chip_texts(c)
        if tx:
            ins = self.insets(c, tx)
            sig.update({"Polster oben": ins["top"], "Polster unten": ins["bottom"], "Polster links": ins["left"], "Polster rechts": ins["right"],
                        "Schrift": tx[0]["e"]["fs"]})
        return sig

    def sig_heading(self, h):
        t = self.tile_of(h); b = self.gbox(h)
        left = b["x0"] - t["x"]; right = (t["x"] + t["w"]) - b["x1"]
        return {"Stellung oben": b["y0"] - t["y"], "Stellung links": left, "Mitte-Versatz": (left - right) / 2}

    @staticmethod
    def reference(vals, tol=1.0):
        """Soll einer Gruppe: Mittel des groessten Nachbarschafts-Clusters (Werte, die hoechstens tol
        auseinanderliegen, gehoeren zusammen — keine festen Bins, die 10,2 und 10,3 trennen koennten);
        ohne Mehrheit das erste (oberste/linke) Mitglied."""
        srt = sorted(vals)
        clusters = [[srt[0]]]
        for v in srt[1:]:
            if v - clusters[-1][-1] <= tol:
                clusters[-1].append(v)
            else:
                clusters.append([v])
        best = max(clusters, key=len)
        if len(best) >= 2:
            return sum(best) / len(best)
        return vals[0]

    def deco_side(self, e):
        """Platz fuer Deko/Icon? Pseudo-Element oder absolutes Kind am Element, am Elternteil oder an der Kachel."""
        par = self.els[e["parent"]] if e["parent"] is not None and e["parent"] >= 0 else None
        cands = [e] + ([par] if par is not None else []) + ([self.tile_of(e)] if self.tile_of(e) is not None else [])
        return any(c.get("hasPseudo") or c.get("hasAbsChild") for c in cands)

    def check_groups(self):
        tol, soft = self.lc["siblingTol"], self.lc["siblingSoft"]
        for g in self.groups:
            sigf = {"tile": self.sig_tile, "chip": self.sig_chip, "heading": self.sig_heading}[g["kind"]]
            sigs = [sigf(m) for m in g["members"]]
            keys, dropped = self.compare_keys([k for k in sigs[0] if all(k in s for s in sigs)], sigs)
            g["sigs"], g["keys"], g["issues"] = sigs, keys, []
            rule = "G3" if g["kind"] == "heading" else "G1"
            cat = "Stellung" if g["kind"] == "heading" else "Geschwister"
            worst = "ok"
            for k in keys:
                vals = [s[k] for s in sigs]
                ref = self.reference(vals)
                if max(vals) - min(vals) <= tol:
                    continue
                for m, s in zip(g["members"], sigs):
                    v = s[k]
                    if abs(v - ref) <= tol:
                        continue
                    level = "knapp" if abs(v - ref) <= soft else "verstoß"
                    note = (f"{g['label']}: {k} = {' · '.join(fmt(x) for x in vals)} — "
                            + ("gleiche Rolle, gleiche Stellung in der Kachel" if rule == "G3" else "Geschwister haben identische Innenmaße")
                            + f"; Soll {fmt(ref)} (Mehrheit, sonst erstes Mitglied)")
                    if level == "verstoß" and k in ("Polster links", "Polster rechts", "Stellung links") and self.deco_side(m):
                        level = "knapp"; note += "; vermutlich Platz für Deko/Icon (Pseudo-Element oder absolutes Kind) — prüfen, nicht blind angleichen"
                    g["issues"].append((k, self.name(m), v, ref, level))
                    worst = max(worst, level, key=lambda x: RANK[x])
                    self.add(rule, cat, m, k, v, ref, level, note, count=False, group=g["label"])
            members = ", ".join(self.name(m) for m in g["members"])
            if worst == "ok":
                self.add(rule, cat, g["members"][0], "Konsistenz", "gleich", "gleich", "ok",
                         f"{g['label']} [{members}]: {len(keys)} Maße verglichen ({', '.join(keys)}), alle gleich (±{fmt(tol)} px){dropped}",
                         weight=2.0 if rule == "G1" else 1.0, group=g["label"])
            else:
                n_bad = len([i for i in g["issues"] if i[4] == "verstoß"])
                self.add(rule, cat, g["members"][0], "Konsistenz", "ungleich", "gleich", worst,
                         f"{g['label']} [{members}]: {len(g['issues'])} Abweichungen ({n_bad} Verstöße) in {', '.join(sorted({i[0] for i in g['issues']}))}"
                         + (" — HARTES GATE: Geschwister zuerst angleichen, alles andere danach" if worst == "verstoß" and rule == "G1" else "") + dropped,
                         weight=2.0 if rule == "G1" else 1.0, group=g["label"])
            if g["kind"] == "heading":
                lod = [m for m in g["members"] if m.get("lightOnDark")]
                dark = [m for m in g["members"] if not m.get("lightOnDark")]
                if lod and dark:
                    self.add("G2", "Polarität", lod[0], "hell auf dunkel", "–", "–", "info",
                             f"{g['label']}: „{lod[0]['text'][:18]}“ steht hell auf dunkel, „{dark[0]['text'][:18]}“ dunkel auf hell — gleiche Größe wirkt hell auf dunkel "
                             f"größer und fetter (Irradiation); wenn beide gleich wirken sollen: Größe −3…5 % oder ein Gewicht leichter. Hinweis, kein Gate.",
                             count=False, group=g["label"])

    # ---------------------------------------------------------------- C8 Titel-Bindung
    def check_title_binding(self):
        tol = self.lc["titleTol"]
        for t in self.tiles:
            rows = self.content_rows(t)
            ti = next((i for i, R in enumerate(rows) if R["dom"]["kind"] == "text" and self.role.get(R["dom"]["e"]["i"]) in ("title", "subtitle")), None)
            if ti is None:
                continue
            h = rows[ti]["dom"]["e"]
            if ti >= len(rows) - 1:
                self.add("C8", "Titel-Bindung", h, "Titel→Text", "–", "–", "info", "nichts unter der Überschrift in der Kachel — Relation nicht anwendbar", count=False)
                continue
            g_title = rows[ti + 1]["mass0"] - rows[ti]["y1"]
            blocks = [(rows[k], rows[k + 1], rows[k + 1]["mass0"] - rows[k]["y1"]) for k in range(ti + 1, len(rows) - 1)]

            def line_gap(R):
                """sichtbare Zeilenluecke einer mehrzeiligen Textreihe: Zeilenhoehe − Massenhoehe (x- bzw. Versal-/Ziffernhoehe)"""
                d = R["dom"]
                if d["kind"] == "text" and d.get("n", 1) > 1 and d.get("lh"):
                    v = d["lh"] - d.get("massh", d.get("xh", 0))
                    return v if v > 0 else None
                return None
            line = next((v for v in (line_gap(R) for R in rows[ti + 1:]) if v), None)
            self.c8_heads.add(h["i"])
            if g_title <= 0.5:
                self.add("C8", "Titel-Bindung", h, "Titel→Text", round(g_title, 2), round(line / PHI, 2) if line else "–", "verstoß",
                         f"Titel→Text {fmt(g_title)} — Überschrift berührt oder überlappt den Text"
                         + (f"; Soll ≈ Zeile/φ = {fmt(line / PHI)}" if line else ""), weight=2.0)
            elif line:
                soll = line / PHI
                r = g_title / line
                if r <= (1 / PHI) * (1 + tol):
                    level, why = "ok", "Titel sitzt am Text"
                elif r <= 1.03:
                    level, why = "knapp", ("Titel→Text so weit wie der Zeilenabstand — der Titel hängt lose über dem Text" if r > 0.9
                                           else "Titel→Text größer als Zeile/φ, aber noch unter dem Zeilenabstand — Soll enger")
                else:
                    level, why = "verstoß", "Titel→Text weiter als der Zeilenabstand — der Titel gehört nicht mehr erkennbar zum Text"
                self.add("C8", "Titel-Bindung", h, "Titel→Text", g_title, g_title if level == "ok" else soll, level,
                         f"Titel→Text {fmt(g_title)} · Zeile→Zeile {fmt(line)} → {r:.2f}; Überschrift gehört zum Folgenden: Titel→Text ≤ Zeile→Zeile ≤ Text→Block, "
                         f"Soll Titel→Text ≈ Zeile/φ = {fmt(soll)}; {why}", weight=2.0)
                for a, b, g in blocks:
                    ln = line_gap(a) or line   # Zeilenmass der ANGRENZENDEN oberen Reihe, sonst das erste gefundene
                    r = g / ln
                    soll_b, _ = nearest(self.spacing, ln * PHI)
                    if r < 0.97:
                        level, why = "verstoß", "Blockabstand enger als der Zeilenabstand — der nächste Block klebt am Text"
                    elif r < PHI * (1 - tol):
                        level, why = "knapp", "Blockabstand kaum größer als der Zeilenabstand — Block setzt sich nicht ab"
                    else:
                        level, why = "ok", "Block setzt sich ab"
                    self.add("C8", "Titel-Bindung", a["dom"]["e"], f"Text→{self.row_label(b)}", g, g if level == "ok" else soll_b, level,
                             f"Text→Block {fmt(g)} · Zeile→Zeile {fmt(ln)} → {r:.2f}; Soll Block = Zeile·φ = {fmt(soll_b)}; {why}", weight=1.0)
            elif blocks:
                mb = min(g for _, _, g in blocks)
                r = mb / g_title
                level = "ok" if r >= 1.0 else ("knapp" if r >= 0.97 else "verstoß")
                self.add("C8", "Titel-Bindung", h, "Titel→Text", g_title, g_title if level == "ok" else mb / PHI, level,
                         f"Titel→Text {fmt(g_title)} · kleinster Blockabstand danach {fmt(mb)} → {r:.2f}; Titel→Text muss der engste Abstand der Kachel sein"
                         + ("" if level == "ok" else f"; Soll ≈ Block/φ = {fmt(mb / PHI)}"), weight=2.0)
            else:
                self.add("C8", "Titel-Bindung", h, "Titel→Text", round(g_title, 2), "–", "info",
                         f"nur eine Zeile unter der Überschrift ({fmt(g_title)}) — keine Vergleichsstrecke, Relation nicht anwendbar", count=False)

    # ---------------------------------------------------------------- C9 Grafik-Rand, B8 Chip↔Kachel, M1 gemalte Kante
    def check_graphic_edge(self):
        for t in self.tiles:
            rows = self.content_rows(t)
            if not rows or rows[-1]["dom"]["kind"] != "box":
                continue
            R = rows[-1]
            x0 = min(b["x0"] for b in R["members"]); x1 = max(b["x1"] for b in R["members"])
            if x1 - x0 < 0.5 * t["w"]:
                continue
            ins = {"links": x0 - t["x"], "rechts": t["x"] + t["w"] - x1, "unten": t["y"] + t["h"] - R["y1"]}
            vals = list(ins.values()); ref = sorted(vals)[1]
            spread = max(vals) - min(vals)
            level = "ok" if spread <= self.lc["siblingTol"] else ("knapp" if spread <= self.lc["siblingSoft"] else "verstoß")
            side = max(ins, key=lambda k: abs(ins[k] - ref))
            self.add("C9", "Grafik-Rand", t, f"Balken-Rand {side}", ins[side], ref, level,
                     f"Balken links {fmt(ins['links'])} · rechts {fmt(ins['rechts'])} · unten {fmt(ins['unten'])} — Grafik am Kachelrand braucht ringsum dasselbe Polster"
                     + ("" if level == "ok" else f"; Soll alle {fmt(ref)} (Median der drei), Polster-Soll nach C3 siehe dort"), weight=1.0)

    def check_chip_tile(self):
        cg = [g for g in self.groups if g["kind"] == "chip"]
        if not cg:
            if self.chips and self.tiles:
                self.add("B8", "Chip↔Kachel", self.chips[0], "Höhe zur Kachel", "–", "–", "info",
                         f"{len(self.chips)} Chip(s), aber keine Chip-Gruppe (≥ 2 gleiche) — φ-Stufe nicht geprüft", count=False)
            return
        tol = self.lc["chipStepTol"]
        tg = [g for g in self.groups if g["kind"] == "tile"]
        targets = [(g["label"], sorted(m["h"] for m in g["members"])[len(g["members"]) // 2],
                    sum(m["y"] + m["h"] / 2 for m in g["members"]) / len(g["members"])) for g in tg]
        targets = targets or [(self.tile_label(t), t["h"], t["y"] + t["h"] / 2) for t in self.tiles]
        for c in cg:
            ch = sorted(m["h"] for m in c["members"])[len(c["members"]) // 2]
            cy = sum(m["y"] + m["h"] / 2 for m in c["members"]) / len(c["members"])
            # nur die NAECHSTGELEGENE Kachel(-Gruppe) — Kreuzprodukt gegen alle wuerde die Ordnung fluten
            near = [t for t in targets if t[1] > ch]
            if ch <= 0 or not near:
                self.add("B8", "Chip↔Kachel", c["members"][0], "Höhe zur Kachel", ch, "–", "info",
                         f"{c['label']} Höhe {fmt(ch)} — keine höhere Kachel im Scope, φ-Stufe nicht prüfbar", count=False)
                continue
            tl, th, _ = min(near, key=lambda t: abs(t[2] - cy))
            n = LN(th / ch) / LN(PHI)
            k = max(1, round(n)); frac = abs(n - k)
            soll = th / PHI ** k
            level = "ok" if frac <= tol else "knapp"
            self.add("B8", "Chip↔Kachel", c["members"][0], f"Höhe zu {tl}", ch, ch if level == "ok" else soll, level,
                     f"{c['label']} Höhe {fmt(ch)} · {tl} Höhe {fmt(th)} (nächstgelegene) → {th / ch:.2f} = φ^{n:.2f}; "
                     + (f"Chip liegt {k} φ-Stufen unter der Kachel" if level == "ok" else
                        (f"fast Kachelhöhe — mindestens eine φ-Stufe darunter, Soll Chip {fmt(soll)}" if n < 0.5 else
                         f"zwischen den Stufen — Soll Chip {fmt(soll)} (φ^{k}) oder Kachel {fmt(ch * PHI ** k)}")),
                     weight=0.5)

    def painted_edges(self, t):
        """M1: sichtbare Kante einer gemalten Kachel aus dem Screenshot — wie viele CSS-px innerhalb der CSS-Box
        beginnt die Tinte? Probe 3 px ausserhalb der Box als Hintergrund; Treffer = 3 Pixel in Folge deutlich anders."""
        try:
            from PIL import Image
        except ImportError:
            return None
        shot = self.d.get("shot")
        if not shot or not Path(shot).exists():
            return None
        if not hasattr(self, "_img"):
            self._img = Image.open(shot).convert("RGB")
        img = self._img; s = img.width / self.scope["w"]; W, H = img.size

        def px(x, y):
            return img.getpixel((int(min(max(x, 0), W - 1)), int(min(max(y, 0), H - 1))))

        def diff(a, b):
            return max(abs(a[i] - b[i]) for i in range(3))
        scan = int(self.lc["paintedScan"] * s)
        x0, y0, x1, y1 = t["x"] * s, t["y"] * s, (t["x"] + t["w"]) * s - 1, (t["y"] + t["h"]) * s - 1
        # drei Messlinien je Seite (25/50/75 %), Median der Treffer — eine Linie kann eine Ecke, ein Icon oder eine Naht treffen
        fr = (0.25, 0.5, 0.75)
        sides = {"top": [((x0 + (x1 - x0) * f, y0), (0, 1)) for f in fr], "bottom": [((x0 + (x1 - x0) * f, y1), (0, -1)) for f in fr],
                 "left": [((x0, y0 + (y1 - y0) * f), (1, 0)) for f in fr], "right": [((x1, y0 + (y1 - y0) * f), (-1, 0)) for f in fr]}
        out = {}
        for side, lines in sides.items():
            hits = []
            for (x, y), (dx, dy) in lines:
                ox, oy = x - dx * 3 * s, y - dy * 3 * s
                if ox < 0 or oy < 0 or ox >= W or oy >= H:
                    continue       # keine Probe ausserhalb moeglich (Scope-Rand)
                bg = px(ox, oy); run = 0
                for k in range(scan):
                    run = run + 1 if diff(px(x + dx * k, y + dy * k), bg) > 60 else 0
                    if run >= 3:
                        hits.append((k - 2) / s); break
            out[side] = None if not hits else round(sorted(hits)[len(hits) // 2], 1)
        return out

    def check_painted(self):
        for t in self.tiles:
            if not (t.get("bgImage") or t.get("borderImage") or t.get("hasPseudo")):
                continue
            pe = self.painted_edges(t)
            if not pe or all(v is None for v in pe.values()):
                self.add("M1", "Gemalte Kante", t, "Einzug der sichtbaren Kante", "–", "–", "info",
                         "gemalte Kachel, aber Kante nicht messbar (" + ("kein Screenshot/Pillow" if not pe else "keine Tinte im Randband gefunden oder Probe außerhalb nicht möglich") + ") — wird genannt, nicht geraten", count=False)
                continue
            self.painted[t["i"]] = pe
            known = {k: v for k, v in pe.items() if v is not None}
            inside = {k: v for k, v in known.items() if v >= 1.0}
            de = {"top": "oben", "right": "rechts", "bottom": "unten", "left": "links"}
            if inside:
                self.add("M1", "Gemalte Kante", t, "Einzug der sichtbaren Kante", max(inside.values()), 0, "info",
                         "sichtbare Kante liegt innerhalb der CSS-Box: " + ", ".join(f"{de[k]} {fmt(v)}" for k, v in inside.items())
                         + " px — das Auge misst Polster ab dieser Kante, nicht ab der Box (sichtbares Polster = CSS-Polster − Einzug); "
                         + "Kachelabstände wirken entsprechend größer", count=False)
            elif known:
                self.add("M1", "Gemalte Kante", t, "Einzug der sichtbaren Kante", 0, 0, "info",
                         "gemalte Kachel, sichtbare Kante deckt sich mit der CSS-Box (" + ", ".join(de[k] for k in known) + ")", count=False)

    # ---------------------------------------------------------------- C1 Naehe-Ordnung
    def judge_ratio(self, r):
        """C1-Band: r<1 verstoß · |ln(r/φ)| ≤ ln(1+tol) ok · sonst knapp"""
        if r < 1.0:
            return "verstoß"
        return "ok" if logdev(r, PHI) <= LN(1 + self.lc["ratioTol"]) else "knapp"

    def check_proximity(self):
        tol = self.lc["ratioTol"]
        all_outer = []
        for t in self.tiles:
            gaps = self.inner_gaps(t)
            ext = self.neighbour_gaps(t)
            if ext:
                all_outer.append(min(ext))
            if not gaps:
                self.add("C1", "Nähe-Ordnung", t, "innen → außen", "–", "–", "info",
                         "nur eine Inhaltszeile — keine Innenlücke, Relation nicht anwendbar", count=False)
                continue
            if not ext:
                self.add("C1", "Nähe-Ordnung", t, "innen → außen", max(gaps), "–", "info",
                         f"innen {fmt(max(gaps))}, aber kein Nachbar im Scope — Außenabstand nicht messbar", count=False)
                continue
            inner, out = max(gaps), min(ext)
            r = out / inner
            level = self.judge_ratio(r)
            soll_out, _ = nearest(self.spacing, inner * PHI)
            soll_in, _ = nearest(self.spacing, out / PHI)
            why = {"verstoß": "Gruppen verschmelzen — außen muss größer sein als innen",
                   "ok": f"außen/innen = {r:.2f} ≈ φ (±{tol * 100:.0f} %)",
                   "knapp": f"außen/innen = {r:.2f}, Soll φ = 1,62 (P8 ±{tol * 100:.0f} %)"}[level]
            self.add("C1", "Nähe-Ordnung", t, "innen → außen", out, out if level == "ok" else soll_out, level,
                     f"innen {fmt(inner)} (größte Lücke zwischen Inhaltszeilen, Grundlinie → Masse, Grafik eingeschlossen) · außen {fmt(out)} (kleinster Abstand zum Nachbarn); {why}"
                     + ("" if level == "ok" else f"; Soll außen = innen·φ = {fmt(soll_out)} oder innen = außen/φ = {fmt(soll_in)}"), weight=2.0)
        inners = [max(self.inner_gaps(t) or [0]) for t in self.tiles]
        inners = [i for i in inners if i > 0]
        if inners and all_outer:
            mi, mo = max(inners), min(all_outer)
            r = mo / mi
            level = self.judge_ratio(r)
            soll, _ = nearest(self.spacing, mi * PHI)
            self.add("C1", "Nähe-Ordnung", self.scope, "Ebenen: Kachel-innen → Kachel-außen", mo, mo if level == "ok" else soll, level,
                     f"größte Innenlücke {fmt(mi)} · kleinster Abstand zwischen Kacheln/Nachbarn {fmt(mo)} → {r:.2f}; Soll eine φ-Stufe darüber ({fmt(soll)}); "
                     f"Zusammenfassung der C1-Zeilen — zählt nicht doppelt in die Ordnung", count=False)

    # ---------------------------------------------------------------- C2 Ueberschrift
    def check_headings(self):
        lo, hi = self.lc["headingBand"]
        tol = self.lc["headingTol"]
        heads = [e for e in self.leaves if e["textLen"] > 0 and self.role.get(e["i"]) in ("title", "subtitle")]
        seen = set()
        for h in heads:
            key = (h["text"], round(h["y"]))
            if key in seen:
                continue
            seen.add(key)
            hb = self.gbox(h)
            tile = self.tile_of(h)
            pool = [self.gbox(e) for e in self.leaves if e is not h and e["textLen"] > 0 and self.tile_of(e) is tile]
            pool += [self.gbox(c) for c in self.chips if self.tile_of(c) is tile]
            pool = [b for b in pool if overlap_x(b, hb) > 4]
            below = [b["mass0"] - hb["y1"] for b in pool if b["y0"] >= hb["y1"] - 1]
            above = [hb["mass0"] - b["y1"] for b in pool if b["y1"] <= hb["y0"] + 1]
            if not below:
                self.add("C2", "Überschrift", h, "oben : unten", "–", "–", "info", "nichts darunter — Relation nicht anwendbar", count=False)
                continue
            d_below = min(below)
            weight, src = 2.0, "zum Vorigen"
            if above:
                d_above = min(above)
            elif tile is not None:
                d_above = hb["y0"] - tile["y"]; src = "zum Kachelrand (= Polster, siehe C3)"; weight = 1.0
            else:
                self.add("C2", "Überschrift", h, "oben : unten", "–", round(d_below, 2), "info",
                         f"erste Zeile des Scopes — kein Voriges; unten {fmt(d_below)}", count=False)
                continue
            if d_below <= 0.5:
                self.add("C2", "Überschrift", h, "oben : unten", d_above, d_below, "knapp",
                         f"unten 0 — Überschrift sitzt direkt auf dem Folgenden; oben {fmt(d_above)}", weight=weight)
                continue
            r = d_above / d_below
            if r < 1.0:
                level = "verstoß" if weight == 2.0 else "knapp"   # Kachelrand ist Polster (C3) — kein hartes Urteil
            elif lo * (1 - tol) <= r <= hi * (1 + tol):
                level = "ok"
            else:
                level = "knapp"
            soll = d_above if level == "ok" else (d_below * lo if r < lo else d_below * hi)
            dbl = h["i"] in self.c8_heads
            self.add("C2", "Überschrift", h, "Abstand oben", d_above, soll, level,
                     f"oben {fmt(d_above)} ({src}) · unten {fmt(d_below)} → {r:.2f}; Konvention oben ≈ unten·φ…φ² (≈ 2–2,5 : 1, Butterick/Schöndorfer) — "
                     + ("Überschrift hängt am Vorigen statt am Folgenden" if level == "verstoß" else "weiche Toleranz, kein hartes Gate")
                     + ("; zählt nicht in die Ordnung — C8 beurteilt dieselbe Lücke in der Kachel" if dbl else ""), weight=weight, count=not dbl)

    # ---------------------------------------------------------------- C3 Polster↔Schrift, B4 Randkanon, B6 Radien
    def check_padding_font(self):
        for t in self.tiles:
            texts, other = self.content(t)
            if not texts:
                self.add("C3", "Polster↔Schrift", t, "Innenabstand", "–", "–", "info", "kein Text in der Kachel — Relation nicht anwendbar", count=False)
                continue
            ins = self.insets(t, texts + other)
            inset = min(ins.values())
            side = min(ins, key=ins.get)
            main = min((b["e"] for b in texts), key=lambda k: abs(k["fs"] - self.base))
            xh, cap, est = self.metrics(main)
            xh_px, cap_px = xh * main["fs"], cap * main["fs"]
            soll, _ = nearest(self.spacing, cap_px)
            if inset < xh_px * 0.97:
                level, note = "verstoß", f"Innenabstand {fmt(inset)} unter der x-Höhe des Haupttexts ({fmt(xh_px)}) — Text klebt am Rand"
            elif inset < cap_px * 0.9:
                level, note = "knapp", f"Innenabstand {fmt(inset)} ≥ x-Höhe {fmt(xh_px)}, aber unter der Versalhöhe des Haupttexts ({fmt(cap_px)})"
            else:
                level, note = "ok", f"Innenabstand {fmt(inset)} ≥ Versalhöhe des Haupttexts ({fmt(cap_px)})"
            if other:
                oi = self.insets(t, other); ti = self.insets(t, texts)
                if min(oi.values()) < min(ti.values()) - 0.5:
                    note += f"; engste Stelle ist Grafik ({ {'top': 'oben', 'bottom': 'unten', 'left': 'links', 'right': 'rechts'}[side] } {fmt(inset)}), Schrift {fmt(min(ti.values()))} — Grafik ist Inhalt, gleiches Polster-Soll"
            if est:
                note += "; Schriftmetrik geschätzt (x 0,5 / Versal 0,7), nicht gemessen"
            self.add("C3", "Polster↔Schrift", t, "Innenabstand (Inhalt, kleinster)", inset, inset if level == "ok" else soll, level, note)
            top, bottom = ins["top"], ins["bottom"]
            rows = self.content_rows(t)
            bar_end = bool(rows) and rows[-1]["dom"]["kind"] == "box" and (max(b["x1"] for b in rows[-1]["members"]) - min(b["x0"] for b in rows[-1]["members"])) >= 0.5 * t["w"]
            if bar_end:
                self.add("B4", "Randkanon", t, "Polster unten", bottom, "–", "info",
                         f"Kachel endet mit einem Balken (unten {fmt(bottom)}) — der Randkanon gilt für Textblöcke; für Grafik am Rand gilt links = rechts = unten (C9)", count=False)
            elif top > 0.5 and bottom > -0.5:
                lvl = "ok" if bottom >= top * 0.94 else "knapp"
                self.add("B4", "Randkanon", t, "Polster unten", bottom, bottom if lvl == "ok" else top, lvl,
                         f"oben {fmt(top)} · unten {fmt(bottom)} (Inhaltskante → Rand, Schrift und Grafik); Kanon unten ≥ oben, klassisch unten = oben·φ = {fmt(top * PHI)}")
        for t in self.tiles:
            if t.get("radius") in (None, 0):
                continue
            for c in self.els:
                if c.get("radius") in (None, 0) or c is t or not (c.get("hasBox") or c["isIcon"]) or c["w"] < 24:
                    continue
                if self.tile_of(c) is not t or c["position"] in ("absolute", "fixed"):
                    continue
                inset = min(c["x"] - t["x"], c["y"] - t["y"], t["x"] + t["w"] - c["x"] - c["w"], t["y"] + t["h"] - c["y"] - c["h"])
                if inset < 0.5:
                    continue
                soll = max(0.0, t["radius"] - inset)
                level = "ok" if abs(c["radius"] - soll) <= max(1.0, 0.12 * max(soll, 1)) else "knapp"
                self.add("B6", "Radius", c, "border-radius (innen)", c["radius"], soll, level,
                         f"außen {fmt(t['radius'])} − Polster {fmt(inset)} = {fmt(soll)} (konzentrisch" + ("; Polster ≥ Außenradius → innen eckig" if soll == 0 else "") + ")")

    # ---------------------------------------------------------------- C4 Rhythmus, C5 Kanten
    def check_rhythm_edges(self):
        u = self.unit
        rows = self.rows()
        lengths = [t["h"] for t in self.tiles] + [b["y0"] - a["y1"] for a, b in zip(rows, rows[1:]) if b["y0"] - a["y1"] > 0.5]
        if u > 0 and lengths:
            res = []
            for v in lengths:
                k = v / u
                res.append(min(abs(k - round(k)), abs(k - (math.floor(k) + 0.5))))
            mean = sum(res) / len(res)
            self.rhythm = {"unit": round(u, 2), "meanRest": round(mean, 3), "n": len(res)}
            level = "ok" if mean <= self.lc["rhythmTol"] else ("knapp" if mean <= self.lc["rhythmTol"] * 2 else "verstoß")
            self.add("C4", "Rhythmus", self.scope, "Rest zur Grund-Zeilenhöhe", round(mean, 3), 0.0, level,
                     f"Einheit {fmt(u)} px (Grundgröße {fmt(self.base)} × Zeilenhöhe); {len(res)} Strecken (Kachelhöhen, Stapelabstände), mittlerer Rest {mean:.2f} "
                     f"(0 = Vielfache oder ½-Schritte; Zufall ≈ 0,125)", unit="")
        xs = [t["x"] for t in self.tiles] + [self.gbox(e)["x0"] for e in self.leaves + self.chips]
        edges = []
        for x in sorted(xs):
            if not edges or x - edges[-1][0] > self.lc["edgeTol"]:
                edges.append([x, 1])
            else:
                edges[-1][1] += 1
        strong = [(round(x, 1), c) for x, c in edges if c >= 2]
        self.edges = {"all": len(edges), "strong": strong}
        n = len(strong)
        level = "ok" if n <= self.lc["edgesTarget"] else ("knapp" if n <= self.lc["edgesTarget"] + 2 else "verstoß")
        self.add("C5", "Kanten", self.scope, "linke Ausrichtungskanten", n, min(n, self.lc["edgesTarget"]), level,
                 f"{n} Kanten mit ≥ 2 Elementen (x = {', '.join(fmt(x) for x, _ in strong[:8])}); Ziel: eine Kante je Hierarchieebene "
                 f"(zentrierte/rechtsbündige Texte erzeugen Scheinkanten — text-align wird nicht gemessen)", unit="")

    # ---------------------------------------------------------------- B1 Stapel-Teilung, B3 optische Mitte
    def check_division(self):
        rows = self.rows()
        H = self.scope["h"]
        best = None
        for i, (a, b) in enumerate(zip(rows, rows[1:])):
            mid = (a["y1"] + b["y0"]) / 2
            p = mid / H
            if not 0.02 < p < 0.98:
                continue
            for tgt in (0.382, 0.618):
                dev = logdev(p / (1 - p), tgt / (1 - tgt))
                if best is None or dev < best[0]:
                    best = (dev, i, p, tgt, mid)
        if best is None:
            self.add("B1", "Stapel-Teilung", self.scope, "Hauptteilung", "–", "–", "info", "weniger als zwei Blöcke — keine Teilung messbar", count=False)
        else:
            dev, i, p, tgt, mid = best
            level = "ok" if dev <= LN(1 + self.lc["splitTol"]) else ("knapp" if dev <= LN(1.10) else "verstoß")
            name = "Minor 38,2 %" if tgt < 0.5 else "Major 61,8 %"
            self.add("B1", "Stapel-Teilung", self.scope, f"Hauptteilung (Grenze Block {i + 1}|{i + 2})", round(p * 100, 1), round(tgt * 100, 1), level,
                     f"die φ-nächste Stapelgrenze liegt bei {fmt(round(mid))} px = {p * 100:.1f} % der Höhe; Ziel {name} = {fmt(round(tgt * H))} px "
                     f"(a/b-Abweichung {(math.exp(dev) - 1) * 100:.1f} %, P1 ±3 %); 50 % ist kein Ziel (R1/K3)", unit="%")
        for t in self.tiles:
            texts, other = self.content(t)
            blocks = texts + other   # Grafik (Balken, Icon) ist Inhalt
            if not blocks or t["h"] < 60:
                continue
            ins = self.insets(t, blocks)
            if abs(ins["top"] - ins["bottom"]) > 0.25 * t["h"]:
                self.add("B3", "Optische Mitte", t, "Inhaltsblock", "–", "–", "info",
                         f"nicht zentriert gebaut (oben {fmt(ins['top'])} / unten {fmt(ins['bottom'])}) — R6 gilt nur für zentrierte Elemente", count=False)
                continue
            top = min(b["y0"] for b in blocks); bottom = max(b["y1"] for b in blocks)
            c = ((top + bottom) / 2 - t["y"]) / t["h"]
            dev = c - self.lc["opticalCenter"]
            level = "ok" if abs(dev) <= self.lc["opticalTol"] else "knapp"
            self.add("B3", "Optische Mitte", t, "Inhaltsblock-Mitte", round(c * 100, 1), round(self.lc["opticalCenter"] * 100, 1), level,
                     f"Blockmitte (Inhaltskante → letzte Grundlinie/Unterkante, Schrift + Grafik) bei {c * 100:.1f} % der Kachelhöhe; optische Mitte 46 % (R6, ±1,5 %)"
                     + ("" if level == "ok" else f" → Block um {fmt(round(abs(dev) * t['h']))} px {'hoch' if dev > 0 else 'runter'}; Achtung: verschiebt das Polster (C3/B4)"), unit="%")

    # ---------------------------------------------------------------- E Gesamtbild (Ngo)
    def check_global(self):
        W, H = self.scope["w"], self.scope["h"]
        objs = self.items()
        if not objs or W <= 0 or H <= 0:
            return
        cx, cy = W / 2, H / 2

        def moments(lo, hi, c, thick):
            a = max(0.0, min(hi, c) - lo); b = max(0.0, hi - max(lo, c))
            return thick * a * a / 2, thick * b * b / 2          # Flaeche × Hebel je Seite (Objekt an der Achse geteilt)
        wl = wr = wt = wb = 0.0
        for o in objs:
            l, r = moments(o["x0"], o["x1"], cx, o["y1"] - o["y0"]); wl += l; wr += r
            t, b = moments(o["y0"], o["y1"], cy, o["x1"] - o["x0"]); wt += t; wb += b
        bmv = (wl - wr) / max(wl, wr) if max(wl, wr) else 0
        bmh = (wt - wb) / max(wt, wb) if max(wt, wb) else 0
        balance = 1 - (abs(bmv) + abs(bmh)) / 2
        n = len(objs)
        A = sum((o["x1"] - o["x0"]) * (o["y1"] - o["y0"]) for o in objs) or 1.0
        gx = sum((o["x1"] - o["x0"]) * (o["y1"] - o["y0"]) * (o["x0"] + o["x1"]) / 2 for o in objs) / A
        gy = sum((o["x1"] - o["x0"]) * (o["y1"] - o["y0"]) * (o["y0"] + o["y1"]) / 2 for o in objs) / A
        emx = 2 * (gx - cx) / (n * W)       # = 2·Σaᵢ(xᵢ−xc)/(n·b·Σaᵢ)
        emy = 2 * (gy - cy) / (n * H)
        equilibrium = 1 - (abs(emx) + abs(emy)) / 2
        density = A / (W * H)
        vals = []
        for e in self.els:
            for k in ("pt", "pr", "pb", "pl", "mt", "mb", "rowGap", "colGap"):
                v = e.get(k) or 0
                if v >= 2:
                    vals.append(round(v))
        cnt = Counter(vals)
        ns = sum(cnt.values())
        Hent = -sum(c / ns * LN(c / ns) for c in cnt.values()) if ns else 0
        self.glob = {"balance": round(balance, 3), "bmv": round(bmv, 3), "bmh": round(bmh, 3), "equilibrium": round(equilibrium, 3),
                     "centroid": [round(gx, 1), round(gy, 1)], "density": round(density, 3), "entropy": round(Hent, 3),
                     "distinctSpacings": len(cnt), "spacingSamples": ns, "objects": n}
        lvl = "ok" if balance >= self.lc["balanceOk"] else "knapp"
        self.add("E1", "Balance", self.scope, "Balance (Ngo, BM)", round(balance * 100), round(self.lc["balanceOk"] * 100), lvl,
                 f"Drehmoment {'links' if bmv > 0 else 'rechts'} {abs(bmv) * 100:.0f} %, {'oben' if bmh > 0 else 'unten'} {abs(bmh) * 100:.0f} % schwerer "
                 f"({n} Objekte: Kacheln, Chips, freie Texte; Schwelle {self.lc['balanceOk'] * 100:.0f} % Hausgröße). Auf einem scrollenden Stapel misst das die Reihenfolge, nicht das Kippen.", unit="%", count=False)
        lvl = "ok" if equilibrium >= self.lc["equilibriumOk"] else "knapp"
        self.add("E2", "Gleichgewicht", self.scope, "Gleichgewicht (Ngo, EM)", round(equilibrium * 100), round(self.lc["equilibriumOk"] * 100), lvl,
                 f"Schwerpunkt bei x {gx / W * 100:.0f} % / y {gy / H * 100:.0f} % der Fläche (Mitte 50/50); Versatz {abs(gx - cx) / (W / 2) * 100:.0f} % der halben Breite, "
                 f"{abs(gy - cy) / (H / 2) * 100:.0f} % der halben Höhe", unit="%", count=False)
        lo, hi = self.lc["densityBand"]
        self.add("E3", "Dichte", self.scope, "Objektfläche / Rahmen", round(density * 100, 1), round((lo + hi) / 2 * 100), "info",
                 f"{density * 100:.0f} % der Fläche sind Objekte; Tullis-Band {lo * 100:.0f}–{hi * 100:.0f} % stammt aus Desktop-Studien — Hinweis, kein Gate", unit="%", count=False)
        self.add("E4", "Ruhe", self.scope, "verschiedene Abstandswerte", len(cnt), "–", "info",
                 f"{len(cnt)} verschiedene Werte in {ns} Abständen (Entropie {Hent:.2f}); weniger Werte = ruhiger — Hinweis", unit="", count=False)

    # ---------------------------------------------------------------- Zahlen
    ORDER_RULES = ("G1", "G3", "C1", "C2", "C8", "C3", "C9", "B4", "B6", "B8", "C4", "C5")

    def scores(self):
        rel = [(ok, w) for rule, ok, w in self.relations if rule in self.ORDER_RULES]
        order = round(100 * sum(w for ok, w in rel if ok) / sum(w for _, w in rel)) if rel else None
        gated = any(f["rule"] == "G1" and f["level"] == "verstoß" and f["prop"] == "Konsistenz" for f in self.findings)
        self.gate = {"capped": gated, "raw": order}
        if gated and order is not None and order > self.lc["gateCap"]:
            order = self.lc["gateCap"]
        s_edges = max(0, 100 - max(0, len(self.edges["strong"]) - self.lc["edgesTarget"]) * 15)
        s_values = max(0, 100 - max(0, self.glob["distinctSpacings"] - 6) * 8)
        s_rhythm = max(0, round(100 * (1 - self.rhythm["meanRest"] / 0.25))) if self.rhythm["n"] else 100
        self.calm_parts = {"kanten": s_edges, "werte": s_values, "rhythmus": s_rhythm}
        calm = round((s_edges + s_values + s_rhythm) / 3)
        balance = round(100 * (self.glob["balance"] + self.glob["equilibrium"]) / 2)
        return {"ordnung": order, "ordnungRoh": self.gate["raw"], "gate": self.gate["capped"], "ruhe": calm, "balance": balance}

    def run(self):
        # Reihenfolge = Prinzip: Gruppen zuerst (Gate), dann Ordnung in und zwischen den Kacheln, dann Gesamtbild
        self.check_groups()
        self.check_proximity()
        self.check_title_binding()
        self.check_headings()
        self.check_padding_font()
        self.check_graphic_edge()
        self.check_chip_tile()
        self.check_painted()
        self.check_rhythm_edges()
        self.check_division()
        self.check_global()
        return self.findings


# ------------------------------------------------------------------ Ausgabe

def changes(findings):
    """Grundsatz 5: jede verletzte Relation als Soll-Punkt. Keine Bewertung, ob es „geht"."""
    out = []
    for f in findings:
        if f["level"] in ("ok", "info") or f["rule"] in ("E1", "E2", "E3", "E4", "C4", "C5"):
            continue
        if f["prop"] == "Konsistenz":
            continue  # Gruppen-Sammelzeile — die Einzelmasse stehen als eigene Punkte
        u = f["unit"]
        ist = f"{fmt(f['ist'])}{' ' + u if u else ''}" if isinstance(f["ist"], (int, float)) else f["ist"]
        soll = f"{fmt(f['soll'])}{' ' + u if u else ''}" if isinstance(f["soll"], (int, float)) else f["soll"]
        if f["rule"] == "C1" and "Soll außen" in f["note"]:
            out.append(f"{f['label']} — {f['note'].split('Soll ', 1)[1]} ({f['cat']}, C1)")
        else:
            out.append(f"{f['label']} — {f['prop']}: {ist} → {soll} ({f['cat']}, {f['rule']})")
    return out


def ordnung_text(sc):
    o = sc["ordnung"] if sc["ordnung"] is not None else "–"
    if not sc.get("gate"):
        return f"Ordnung {o} %"
    capped = sc.get("ordnungRoh") is not None and sc["ordnungRoh"] != sc["ordnung"]
    extra = ", ungedeckelt {} %".format(sc["ordnungRoh"]) if capped else ""
    return f"Ordnung {o} % (Gate{extra})"


def klartext(findings, sc, lay):
    L = [f"{ordnung_text(sc)} · Ruhe {sc['ruhe']} % · Balance {sc['balance']} % — "
         f"{len(lay.tiles)} Kacheln, {len(lay.chips)} Chips, {len(lay.groups)} Gruppen, Einheit {fmt(lay.unit)} px, {len(lay.edges['strong'])} Kanten"]
    if lay.groups:
        L.append("Gruppen: " + " · ".join(g["label"] + (" ✗" if any(i[4] == "verstoß" for i in g.get("issues", [])) else (" ~" if g.get("issues") else " ✓")) for g in lay.groups))
    if sc.get("gate"):
        L.append("GATE: Geschwister ungleich — erst die Gruppen angleichen, dann der Rest"
                 + (f" (Ordnung gedeckelt auf {sc['ordnung']} %)" if sc.get("ordnungRoh") != sc.get("ordnung") else ""))
    bad = [f for f in findings if f["level"] == "verstoß" and f["prop"] != "Konsistenz"]
    knapp = [f for f in findings if f["level"] == "knapp" and f["prop"] != "Konsistenz"]
    if bad:
        L.append("Verletzt: " + "; ".join(f"{f['label']} {f['prop']} ({f['cat']})" for f in bad[:5]) + ("; …" if len(bad) > 5 else ""))
    if knapp:
        L.append("Knapp: " + "; ".join(f"{f['label']} {f['prop']} ({f['cat']})" for f in knapp[:5]) + ("; …" if len(knapp) > 5 else ""))
    for t in lay.tiles:
        gl = lay.gap_list(t)
        if gl:
            L.append(f"Lücken {lay.tile_label(t)}: " + " · ".join((f"{a}→{b} {fmt(g)}" if b else f"{a} {fmt(g)}") for a, b, g in gl))
    hints = [f for f in findings if f["rule"] in ("G2", "M1")]
    for f in hints:
        L.append(f"Hinweis ({f['cat']}, {f['label']}): {f['note']}")
    ch = changes(findings)
    L.append("Änderungen (Aufteilung/Ordnung):" if ch else "Änderungen (Aufteilung/Ordnung): keine")
    for c in ch:
        L.append(f"- {c}")
    return L


def report(data, findings, sc, lay):
    mark = {"ok": "🟢", "knapp": "🟠", "verstoß": "🔴", "info": "⚪"}
    L = [f"# goldencut · Ordnung & Aufteilung — {data.get('name', 'Messung')}", ""]
    L.append(f"Ziel: `{data.get('target', '')}`  ·  Scope: `{data['scope']['sel']}` ({fmt(data['scope']['w'])}×{fmt(data['scope']['h'])} px)  ·  "
             f"Kacheln: {', '.join(lay.tile_label(t) for t in lay.tiles) or '–'}  ·  Chips: {len(lay.chips)}  ·  Einheit (Grund-Zeilenhöhe): {fmt(lay.unit)} px")
    L += ["", "## Zahlen", ""]
    L.append(f"- **{ordnung_text(sc)}** — Anteil erfüllter Relationen G1/G3 (Gruppen), C1, C2, C8, C3, C9, B4, B6, B8, C4, C5 "
             f"(Geschwister, Nähe-Ordnung, Überschrift und Titel-Bindung doppelt gewichtet, Chip↔Kachel halb)"
             + ("; **Gate**: ein Geschwister-Verstoß deckelt bei " + str(lay.lc["gateCap"]) + " % — Konsistenz in der Gruppe kommt vor allem anderen" if sc.get("gate") else ""))
    L.append(f"- **Ruhe {sc['ruhe']} %** — Mittel aus Kanten {lay.calm_parts['kanten']} ({len(lay.edges['strong'])} Ausrichtungskanten), Werten {lay.calm_parts['werte']} ({lay.glob['distinctSpacings']} verschiedene Abstände), Rhythmus {lay.calm_parts['rhythmus']} (Rest {lay.rhythm['meanRest']:.2f}) — Konstanten sind Hausgrößen")
    L.append(f"- **Balance {sc['balance']} %** — Ngo-Balance {lay.glob['balance']:.2f}, Gleichgewicht {lay.glob['equilibrium']:.2f}, Dichte {lay.glob['density'] * 100:.0f} % (auf scrollenden Stapeln schwach aussagekräftig)")
    L.append("- Die fünf Zahlen gehören zusammen: Reihen-Treue (run, gc_analyze), Lesbarkeit (Typo), Ordnung, Ruhe, Balance — keine davon allein heißt „Goldener Schnitt“.")
    L += ["", "## Änderungen (Soll nach Regelwerk — Entscheidung beim User)", ""]
    ch = changes(findings)
    for c in (ch or ["keine — alle Relationen erfüllt"]):
        L.append(f"- {c}")
    L += ["", "## Gruppen (Zugehörigkeit: gleiche Klasse + Elternteil/Reihe; Überschriften gleicher Rolle)", ""]
    if not lay.groups:
        L.append("- keine Gruppen mit ≥ 2 Mitgliedern im Scope")
    for g in lay.groups:
        keys = g.get("keys", [])
        state = "✗ ungleich" if any(i[4] == "verstoß" for i in g.get("issues", [])) else ("~ knapp" if g.get("issues") else "✓ gleich")
        L.append(f"- **{g['label']}** — {state}")
        if keys:
            L.append("")
            L.append("  | Maß | " + " | ".join(lay.name(m) for m in g["members"]) + " |")
            L.append("  |---|" + "---|" * len(g["members"]))
            for k in keys:
                vals = [s[k] for s in g["sigs"]]
                ref = lay.reference(vals)
                L.append(f"  | {k} | " + " | ".join(("**" + fmt(v) + "**" if abs(v - ref) > lay.lc["siblingTol"] else fmt(v)) for v in vals) + " |")
            L.append("")
    L += ["", "## Innenlücken je Kachel (Massen-Konvention: Grundlinie → Schriftmasse, Grafik ist Inhalt)", ""]
    de = {"top": "o", "right": "r", "bottom": "u", "left": "l"}
    for t in lay.tiles:
        texts, other = lay.content(t)
        ins = lay.insets(t, texts + other)
        gl = lay.gap_list(t)
        pad = f"Polster o/r/u/l {fmt(ins['top'])}/{fmt(ins['right'])}/{fmt(ins['bottom'])}/{fmt(ins['left'])}" if ins else "kein Inhalt"
        seq = " · ".join((f"{a}→{b} **{fmt(g)}**" if b else f"{a} {fmt(g)}") for a, b, g in gl) or "eine Zeile"
        pe = lay.painted.get(t["i"])
        painted = ""
        if pe:
            painted = " · gemalte Kante " + "/".join(f"{de[k]}+{fmt(v)}" for k, v in pe.items() if v is not None and v >= 1) or ""
            painted = painted if painted.strip() != "· gemalte Kante" else " · gemalte Kante = Box"
        L.append(f"- **{lay.tile_label(t)}** — {pad} · {seq}{painted}")
    L += ["", "## Prüfungen", "", "| Urteil | Regel | Element | Eigenschaft | Ist | Soll | Abw. | Befund |", "|---|---|---|---|---|---|---|---|"]
    for f in findings:
        u = f["unit"]
        ist = f"{fmt(f['ist'])}{(' ' + u) if u else ''}" if isinstance(f["ist"], (int, float)) else f["ist"]
        soll = f"{fmt(f['soll'])}{(' ' + u) if u else ''}" if isinstance(f["soll"], (int, float)) else f["soll"]
        if f["dev"] is None:
            dev = "–"
        elif u in ("%", "pp"):
            dev = f"{f['dev']:+.1f} pp"
        else:
            dev = f"{f['dev']:+.1f} %"
        L.append(f"| {mark[f['level']]} | {f['rule']} | {f['label']} | {f['prop']} | {ist} | {soll} | {dev} | {f['note']} |")
    L += ["", "## Lesart", ""]
    L.append("Dieses Urteil ändert nichts. Reihenfolge: Zugehörigkeit erkennen (gleiche Klasse/Rolle/Reihe) → Konsistenz in der Gruppe als hartes Gate (G1) "
             "→ Ordnung in und zwischen den Kacheln → erst zuletzt die Reihe (run). Massen-Konvention (D4): Lücken werden zwischen den sichtbaren Massen gemessen — von der Grundlinie "
             "zur Schriftmasse der nächsten Zeile (x-Höhe bei Gemischtschrift, Versal-/Ziffernhöhe bei Versalien/Ziffern), Polster von der Inhaltskante "
             "(Versalkante bzw. Grafikkante) zum Rand; das dominante Element bestimmt die Zeile, Grafik (Balken, Icon) ist Inhalt wie Schrift. "
             "Geprüft: Geschwister identisch (G1, Gate), Überschriften gleicher Rolle gleich gestellt (G3), Polarität als Hinweis (G2), "
             "Nähe-Ordnung (innen < außen, Soll φ ±10 %, P8), Überschrift gehört zum Folgenden (C2 oben ≈ unten·φ…φ²; C8 in der Kachel Titel→Text ≤ Zeile→Zeile ≤ Text→Block, Soll Zeile/φ und Zeile·φ), "
             "Polster an die Schrift gebunden (≥ x-Höhe hart, ≈ Versalhöhe des Haupttexts, A4/C3 — Grafik eingeschlossen), Grafik-Rand links = rechts = unten (C9), "
             "Randkanon unten ≥ oben (R5), konzentrische Radien (B6), Chip-Höhe als φ-Stufe der Kachel (B8, weich), gemalte Kante aus dem Screenshot (M1, Hinweis), "
             "Rhythmus (C4), Kanten (C5), Hauptteilung des Stapels an φ-Punkten (R1/P1 — 50 % ist kein Ziel), optische Mitte 46 % nur für zentriert "
             "gebaute Kacheln (R6/P10), Ngo-Balance/Gleichgewicht/Dichte als Zahlen ohne Gate. ⚪ = Relation hier nicht anwendbar (wird genannt, nicht verschwiegen). "
             "Grundsatz 5: Soll ist Soll — ob gemalt, hartkodiert oder vorausgesetzt, entscheidet der User. "
             "Quellen: reference/mathematische-prinzipien-ui.md §2 (B1, B3, B4, B6), §3 (C1–C5, C8, G), §5 (E); regeln.md R1, R5, R6, §6 P1, P8–P10.")
    return "\n".join(L) + "\n"


def overlay(shot, out_png, data, lay, findings, sc):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    img = Image.open(shot).convert("RGBA")
    s = img.width / data["scope"]["w"]
    lay_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay_img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", max(10, int(10 * s)))
    except Exception:
        font = ImageFont.load_default()
    COL = {"ok": (40, 160, 80), "knapp": (240, 150, 20), "verstoß": (220, 40, 40), "info": (140, 140, 140)}
    worst = {}
    for f in findings:
        if f["rule"] in ("G1", "G3", "C1", "C2", "C8", "C3", "C9", "B3", "B4") and f["level"] != "info":
            k = tuple(f["tileBox"] or f["box"])
            worst[k] = max(worst.get(k, "ok"), f["level"], key=lambda x: RANK[x])
            if f["rule"] == "G1":
                k2 = tuple(f["box"])
                worst[k2] = max(worst.get(k2, "ok"), f["level"], key=lambda x: RANK[x])
    gname = {}
    for gi, g in enumerate(lay.groups):
        for m in g["members"]:
            gname.setdefault(m["i"], []).append(chr(65 + gi))
    for t in lay.tiles:
        lvl = worst.get((t["x"], t["y"], t["w"], t["h"]), "ok")
        c = COL[lvl]
        r = [t["x"] * s, t["y"] * s, (t["x"] + t["w"]) * s, (t["y"] + t["h"]) * s]
        d.rectangle(r, outline=c + (255,), width=3 if lvl != "ok" else 2)
        gaps = lay.inner_gaps(t)
        texts, other = lay.content(t)
        ins = lay.insets(t, texts + other)
        rows = lay.content_rows(t)
        for R in rows:   # Masse (x-Hoehe/Versal) und Grundlinie je Inhaltszeile
            x0 = min(b["x0"] for b in R["members"]) * s; x1 = max(b["x1"] for b in R["members"]) * s
            d.line([x0, R["mass0"] * s, x1, R["mass0"] * s], fill=(0, 150, 170, 170), width=1)
            d.line([x0, R["y1"] * s, x1, R["y1"] * s], fill=(0, 150, 170, 170), width=1)
        for a, b in zip(rows, rows[1:]):
            g = b["mass0"] - a["y1"]
            if g > 0.5:
                xg = (t["x"] + t["w"]) * s - 6 * s
                d.line([xg, a["y1"] * s, xg, b["mass0"] * s], fill=(0, 150, 170, 255), width=2)
                lab = fmt(round(g, 1))
                d.text((xg - d.textlength(lab, font=font) - 3, (a["y1"] + b["mass0"]) / 2 * s - font.size / 2), lab, fill=(0, 110, 130, 255), font=font)
        tag = f"h{fmt(round(t['h']))} i{fmt(round(max(gaps))) if gaps else '–'} p{fmt(round(min(ins.values()))) if ins else '–'}"
        if t["i"] in gname:
            tag += " G" + "".join(gname[t["i"]])
        tw = d.textlength(tag, font=font)
        d.rectangle([r[0], r[1], r[0] + tw + 4, r[1] + font.size + 2], fill=c + (210,))
        d.text((r[0] + 2, r[1] + 1), tag, fill=(255, 255, 255, 255), font=font)
        pe = lay.painted.get(t["i"])
        if pe:   # M1: sichtbare Kante gestrichelt-grau innerhalb der Box
            ex = [t["x"] + (pe.get("left") or 0), t["y"] + (pe.get("top") or 0), t["x"] + t["w"] - (pe.get("right") or 0), t["y"] + t["h"] - (pe.get("bottom") or 0)]
            d.rectangle([v * s for v in ex], outline=(90, 90, 90, 160), width=1)
    for ch in lay.chips:
        b = lay.gbox(ch)
        lvl = worst.get((ch["x"], ch["y"], ch["w"], ch["h"]), "ok")
        d.rectangle([b["x0"] * s, b["y0"] * s, b["x1"] * s, b["y1"] * s], outline=(COL[lvl] + (230,)) if lvl != "ok" else (120, 120, 200, 200), width=2 if lvl != "ok" else 1)
        if ch["i"] in gname:
            tag = "G" + "".join(gname[ch["i"]])
            d.text((b["x1"] * s - d.textlength(tag, font=font) - 2, b["y0"] * s + 1), tag, fill=(90, 90, 170, 255), font=font)
    for g in lay.groups:   # Ueberschriften-Gruppen: Stellung markieren
        if g["kind"] != "heading":
            continue
        for m in g["members"]:
            b = lay.gbox(m)
            lvl = "ok"
            for i in g.get("issues", []):
                if i[1] == lay.name(m):
                    lvl = max(lvl, i[4], key=lambda x: RANK[x])
            if lvl != "ok":
                d.rectangle([b["x0"] * s, b["y0"] * s, b["x1"] * s, b["y1"] * s], outline=COL[lvl] + (230,), width=2)
    rows = lay.rows()
    for a, b in zip(rows, rows[1:]):
        g = b["y0"] - a["y1"]
        if g <= 0.5:
            continue
        y0, y1 = a["y1"] * s, b["y0"] * s
        x = img.width - 14 * s
        d.line([x, y0, x, y1], fill=(60, 90, 200, 255), width=2)
        d.line([x - 4 * s, y0, x + 4 * s, y0], fill=(60, 90, 200, 255), width=2)
        d.line([x - 4 * s, y1, x + 4 * s, y1], fill=(60, 90, 200, 255), width=2)
        tag = f"außen {fmt(round(g, 1))}"
        d.text((x - d.textlength(tag, font=font) - 6 * s, (y0 + y1) / 2 - font.size / 2), tag, fill=(60, 90, 200, 255), font=font)
    for x, cnt in lay.edges["strong"]:
        d.line([x * s, 0, x * s, img.height], fill=(120, 120, 220, 110), width=1)
    gx, gy = lay.glob["centroid"]
    cx, cy = data["scope"]["w"] / 2, data["scope"]["h"] / 2
    d.ellipse([cx * s - 5, cy * s - 5, cx * s + 5, cy * s + 5], outline=(0, 0, 0, 200), width=2)
    d.ellipse([gx * s - 6, gy * s - 6, gx * s + 6, gy * s + 6], fill=(220, 40, 40, 220))
    d.line([cx * s, cy * s, gx * s, gy * s], fill=(220, 40, 40, 200), width=2)
    pad = int(8 * s)
    legend_h = font.size * 2 + pad * 2
    canvas = Image.new("RGBA", (img.width, img.height + legend_h), (255, 255, 255, 255))
    canvas.paste(Image.alpha_composite(img, lay_img), (0, 0))
    d2 = ImageDraw.Draw(canvas)
    y0 = img.height + pad
    d2.text((pad, y0), f"{ordnung_text(sc)} · Ruhe {sc['ruhe']} % · Balance {sc['balance']} %  ·  Kachel: h Höhe · i Innenlücke · p Polster · G Gruppe  ·  türkis Masse/Grundlinie + Lücken · blau Stapelabstand · grau gemalte Kante · rot Schwerpunkt", fill=(0, 0, 0, 255), font=font)
    x = pad
    for name, c in (("Relation verletzt", COL["verstoß"]), ("knapp", COL["knapp"]), ("erfüllt", COL["ok"])):
        d2.rectangle([x, y0 + font.size + 4, x + font.size, y0 + 2 * font.size + 4], fill=c + (255,))
        d2.text((x + font.size + 4, y0 + font.size + 3), name, fill=(0, 0, 0, 255), font=font)
        x += font.size + 4 + d2.textlength(name, font=font) + pad * 2
    canvas.convert("RGB").save(out_png)
    return out_png


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("measure")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--suffix", default="")
    args = ap.parse_args()
    data = json.loads(Path(args.measure).read_text(encoding="utf-8"))
    cfg = json.loads(json.dumps(DEFAULT_CFG))
    lcfg = json.loads(json.dumps(DEFAULT))
    if args.config:
        user = json.loads(Path(args.config).read_text(encoding="utf-8"))
        for k, v in user.items():
            if k == "layout" and isinstance(v, dict):
                lcfg.update(v)
            elif isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    lay = Layout(data, cfg, lcfg)
    findings = lay.run()
    sc = lay.scores()
    (out / f"layout-report{args.suffix}.md").write_text(report(data, findings, sc, lay), encoding="utf-8")
    (out / f"layout{args.suffix}.json").write_text(json.dumps({
        "scores": sc, "global": lay.glob, "rhythm": lay.rhythm, "edges": lay.edges, "unit": lay.unit,
        "tiles": [{"label": lay.tile_label(t), "sel": t["sel"], "box": [t["x"], t["y"], t["w"], t["h"]]} for t in lay.tiles],
        "chips": [{"label": label(c), "sel": c["sel"]} for c in lay.chips],
        "groups": [{"kind": g["kind"], "label": g["label"], "members": [lay.name(m) for m in g["members"]],
                    "keys": g.get("keys", []), "sigs": [{k: round(v, 2) for k, v in s.items()} for s in g.get("sigs", [])],
                    "issues": [{"mass": i[0], "member": i[1], "ist": round(i[2], 2), "soll": round(i[3], 2), "level": i[4]} for i in g.get("issues", [])]} for g in lay.groups],
        "painted": {str(k): v for k, v in lay.painted.items()},
        "findings": findings, "changes": changes(findings)}, ensure_ascii=False, indent=1), encoding="utf-8")
    png = None
    if data.get("shot") and Path(data["shot"]).exists():
        png = overlay(data["shot"], out / f"layout-overlay{args.suffix}.png", data, lay, findings, sc)
    for line in klartext(findings, sc, lay):
        print(line)
    print(f"Report: {out / ('layout-report' + args.suffix + '.md')}" + (f"  ·  Overlay: {png}" if png else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
