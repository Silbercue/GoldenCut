#!/usr/bin/env python3
"""gc_analyze — prueft eine Messung (measure.json) gegen das Phi-Regelwerk
und liefert KONKRETE Korrekturwerte: report.md, patch.css, patch.override.css,
corrections.json.

Grundsatz (reference/regeln.md, Abschnitt 6): Erst die Zielreihe festlegen,
dann alles dagegen messen. Harmonisch ist ein Aufbau, wenn alle Masse auf
derselben Reihe liegen — nicht, wenn einzelne Verhaeltnisse zufaellig 1,6 ergeben.

Der Index heisst ehrlich „Reihen-Treue" (Harmonie-Index): Anteil der Einzelmasse auf der Reihe.
Er ist blind fuer Gruppen, Luecken und Augen-Masse — die sieht gc_layout (Ordnung). Die Reihe ist
im Urteil das LETZTE, nicht das Erste (Prinzip 2026-08-22): Zugehoerigkeit → Konsistenz in der
Gruppe → Ordnung zwischen den Gruppen → Reihe. Der Solver (Bauschritt 3, noch nicht gebaut) muss
in der Reihenfolge Schrift → Luecken → Polster → Kachel rechnen; dieser Einzel-Snap hier kann
Kachelpolster auf die Reihe setzen, waehrend das Innenleben bleibt — deshalb vergleicht run die
Ordnung vorher/nachher und warnt, wenn sie faellt.

Aufruf:
  gc_analyze.py before.json --out DIR [--config goldencut.config.json]
                [--type-base 16] [--type-ratio 1.272] [--spacing-bases 8,16]
                [--grid 1] [--protect 44,24] [--canon] [--fix-all]
"""

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

PHI = (1 + 5 ** 0.5) / 2
SQRT_PHI = PHI ** 0.5

DEFAULT_CFG = {
    "spacing": {"ratio": PHI, "bases": [8, 16], "round": 1, "min": 2, "max": 400},
    "type": {"ratio": SQRT_PHI, "base": "auto", "round": 0.5, "min": 8, "max": 160},
    "tolerance": {"series": 0.05, "type": 0.10, "ratio": 0.03, "symmetry": 0.06, "innerOuter": 0.10},
    "lineHeight": {"body": [1.2, 1.62], "heading": [1.0, 1.25], "headingFactor": 1.5},
    "protect": [44, 24],
    "icon": {"max": 64, "round": 0.5},
    "formats": {"1:1": 1.0, "5:4": 1.25, "4:3": 1.3333, "√2": 1.4142, "3:2": 1.5, "φ": PHI, "16:9": 1.7778},
}


# ---------------------------------------------------------------- Reihen

def round_to(v, step):
    return round(v / step) * step if step else v


def build_series(bases, ratio, lo, hi, step):
    vals = set()
    for b in bases:
        v = b
        while v <= hi:
            vals.add(round_to(v, step)); v *= ratio
        v = b / ratio
        while v >= lo:
            vals.add(round_to(v, step)); v /= ratio
    return sorted(x for x in vals if lo <= x <= hi)


def nearest(series, v):
    """Naechstes Reihenglied in logarithmischem Abstand -> (glied, rel_abw)."""
    if v <= 0 or not series:
        return None, None
    best = min(series, key=lambda m: abs(math.log(v / m)))
    return best, (v - best) / best


def scale_pos(v, base, ratio):
    """Position auf der Skala: n = log(v/base)/log(ratio); liefert (n, |n-round n|)."""
    n = math.log(v / base) / math.log(ratio)
    return n, abs(n - round(n))


def fmt(v):
    if v is None:
        return "–"
    if abs(v - round(v)) < 0.005:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------- Analyse

class Analyzer:
    def __init__(self, data, cfg, canon=False, fix_all=False, typo_min=None):
        self.d = data
        self.cfg = cfg
        self.els = data["elements"]
        self.canon = canon
        self.fix_all = fix_all
        self.typo_min = typo_min or {}   # Element-Index -> Rollen-Minimum px (aus gc_typo)
        self.findings = []   # dicts
        self.checked = 0     # Bias-Guard: geprueft
        self.on_series = 0   # Bias-Guard: schon auf der Reihe
        self.protect = [float(p) for p in cfg["protect"]]
        sp, ty = cfg["spacing"], cfg["type"]
        self.spacing = build_series(sp["bases"], sp["ratio"], sp["min"], sp["max"], sp["round"])
        self.type_base = self.detect_type_base() if ty["base"] == "auto" else float(ty["base"])
        self.type_series = build_series([self.type_base], ty["ratio"], ty["min"], ty["max"], ty["round"])
        self.children = defaultdict(list)
        for e in self.els:
            if e["parent"] is not None and e["parent"] >= 0:
                self.children[e["parent"]].append(e)

    # -- Hilfen
    def label(self, e):
        name = e["tag"] + ("." + e["cls"].split(" ")[0] if e["cls"] else "")
        if e["text"]:
            name += f' „{e["text"][:18]}{"…" if len(e["text"]) > 18 else ""}“'
        return name

    def is_protected(self, v):
        return any(abs(v - p) <= 0.5 for p in self.protect)

    def add(self, rule, cat, e, prop, ist, soll, dev, action, note="", unit="px"):
        self.findings.append({
            "rule": rule, "cat": cat, "sel": e["sel"], "label": self.label(e), "prop": prop,
            "ist": round(ist, 2) if isinstance(ist, (int, float)) else ist,
            "soll": round(soll, 2) if isinstance(soll, (int, float)) else soll,
            "dev": round(dev * 100, 1) if isinstance(dev, (int, float)) else dev,
            "action": action, "note": note, "unit": unit,
        })

    def inherited_dup(self, e):
        """Effekt-Overlays (gleicher Text, gleiche Groesse wie das Elternelement) nicht doppelt zaehlen."""
        if e["parent"] is None or e["parent"] < 0:
            return False
        p = self.els[e["parent"]]
        return p["textLen"] > 0 and abs(p["fs"] - e["fs"]) < 0.01 and p["text"] == e["text"]

    def leaf_fs(self, e, depth=0):
        """Schriftgroesse des ersten Textblatts im Teilbaum."""
        if e["textLen"] > 0 and e["fs"] > 0:
            return e["fs"]
        if depth > 4:
            return None
        for c in self.children[e["i"]]:
            r = self.leaf_fs(c, depth + 1)
            if r:
                return r
        return None

    def detect_type_base(self):
        w = Counter()
        for e in self.els:
            if e["textLen"] > 0 and not e["isIcon"] and e["fs"] > 0:
                w[round(e["fs"] * 2) / 2] += e["textLen"]
        if not w:
            return 16.0
        top = max(w.values())
        cands = [fs for fs, n in w.items() if n >= top * 0.6]
        return float(min(cands)) if cands else float(w.most_common(1)[0][0])

    # -- P7 Abstandsreihe: Padding, Margin, Gap, Radius
    def check_spacing(self):
        tol = self.cfg["tolerance"]["series"]
        props = [("pt", "padding-top"), ("pr", "padding-right"), ("pb", "padding-bottom"), ("pl", "padding-left"),
                 ("mt", "margin-top"), ("mr", "margin-right"), ("mb", "margin-bottom"), ("ml", "margin-left"),
                 ("rowGap", "row-gap"), ("colGap", "column-gap")]
        for e in self.els:
            inline = e["display"] == "inline"
            for key, prop in props:
                v = e.get(key) or 0
                if v < self.cfg["spacing"]["min"]:
                    continue
                if inline and key in ("pt", "pb", "mt", "mb"):
                    continue  # vertikale Box-Masse wirken bei inline nicht
                if key.endswith("Gap") and e["children"] < 2:
                    continue
                m, dev = nearest(self.spacing, v)
                self.checked += 1
                if abs(dev) <= tol or abs(v - m) < 0.5:
                    self.on_series += 1
                    continue
                if key in ("pl", "pr") and (e.get("hasPseudo") or e.get("hasAbsChild")):
                    self.add("P7", "Abstand", e, prop, v, m, dev, "report", "Seitenpadding macht vermutlich Platz für Deko/Icon — nur prüfen")
                    continue
                self.add("P7", "Abstand", e, prop, v, m, dev, "patch")
            r = e.get("radius")
            if r and r >= 2:
                m, dev = nearest(self.spacing, r)
                self.checked += 1
                if abs(dev) <= tol or abs(r - m) < 0.5:
                    self.on_series += 1
                elif r < min(e["w"], e["h"]) / 2 - 0.5:  # Vollrundungen (Pillen) nicht anfassen
                    self.add("P7", "Radius", e, "border-radius", r, m, dev, "patch")

    # -- P9 Symmetrie und Kanon der Raender (Padding)
    def check_margins(self):
        tol = self.cfg["tolerance"]["symmetry"]
        for e in self.els:
            if (e["children"] == 0 and e["textLen"] == 0) or not e.get("hasBox"):
                continue  # Raender sind nur an sichtbaren Boxen Raender
            pl, pr, pt, pb = e["pl"], e["pr"], e["pt"], e["pb"]
            deliberate = e.get("hasPseudo") or e.get("hasAbsChild")
            # horizontal: links = rechts
            if max(pl, pr) >= 2 and abs(pl - pr) > max(1.0, tol * max(pl, pr)):
                m, _ = nearest(self.spacing, (pl + pr) / 2)
                if deliberate:
                    self.add("P9", "Rand-Symmetrie", e, "padding-left/right", pl, pr, (pl - pr) / max(pl, pr), "report",
                             f"links {fmt(pl)} ≠ rechts {fmt(pr)} — vermutlich Platz für Deko/Icon (Pseudo-Element oder absolutes Kind); nur prüfen")
                else:
                    self.add("P9", "Rand-Symmetrie", e, "padding-left", pl, m, (pl - m) / m, "patch", f"links {fmt(pl)} ≠ rechts {fmt(pr)} → beide {fmt(m)}")
                    self.add("P9", "Rand-Symmetrie", e, "padding-right", pr, m, (pr - m) / m, "patch", "")
            # vertikal: unten ≥ oben (Kanon: unten = oben·φ mit --canon)
            if max(pt, pb) >= 2 and e["display"] != "inline" and deliberate and pb < pt * (1 - tol):
                self.add("P9", "Rand-Kanon", e, "padding-bottom", pb, pt, (pb - pt) / pt, "report",
                         f"unten {fmt(pb)} < oben {fmt(pt)} — vermutlich Platz für Deko (Pseudo-Element oder absolutes Kind); nur prüfen")
            if max(pt, pb) >= 2 and e["display"] != "inline" and not deliberate:
                if pb < pt * (1 - tol):
                    m, _ = nearest(self.spacing, pt)
                    self.add("P9", "Rand-Kanon", e, "padding-bottom", pb, m, (pb - m) / m, "patch", f"unten {fmt(pb)} < oben {fmt(pt)} — unten mind. gleich oben (R5/R6)")
                elif self.canon and pt >= 4 and abs(pb / pt - PHI) > self.cfg["tolerance"]["ratio"]:
                    m, _ = nearest(self.spacing, pt * PHI)
                    self.add("P9", "Rand-Kanon", e, "padding-bottom", pb, m, (pb - m) / m, "patch", f"Kanon unten = oben·φ ({fmt(pt)}·1,618)")

    # -- P8 Innen : Aussen (Gap einer Gruppe vs. Abstand um die Gruppe)
    def check_inner_outer(self):
        tol = self.cfg["tolerance"]["innerOuter"]
        for e in self.els:
            g = max(e["rowGap"], e["colGap"])
            if g <= 0 or e["children"] < 2:
                continue
            outers = []
            pads = [p for p in (e["pt"], e["pr"], e["pb"], e["pl"]) if p > 0]
            if pads and e.get("hasBox"):
                outers.append(("padding", min(pads)))
            par = self.els[e["parent"]] if e["parent"] is not None and e["parent"] >= 0 else None
            if par:
                pg = max(par["rowGap"], par["colGap"])
                if pg > 0:
                    outers.append(("gap des Elternelements", pg))
            for src, outer in outers:
                self.checked += 1
                ratio = outer / g
                if ratio >= 1 - tol:
                    if abs(ratio - PHI) <= self.cfg["tolerance"]["ratio"]:
                        self.on_series += 1
                    continue
                m, _ = nearest(self.spacing, g * PHI)
                action = "patch" if (self.fix_all and src == "padding") else "report"
                prop = "padding (alle Seiten ≥)" if src == "padding" else "gap (Eltern)"
                self.add("P8", "Innen:Außen", e, prop, outer, m, (outer - m) / m, action,
                         f"innen (gap) {fmt(g)} > außen ({src}) {fmt(outer)} — Gruppen verschmelzen; Soll außen = innen·φ")

    # -- P4 Typo-Skala, P5 Zeilenhoehe, P6 Zeilenlaenge
    def check_type(self):
        ty, tol = self.cfg["type"], self.cfg["tolerance"]["type"]
        texts = [e for e in self.els if e["textLen"] > 0 and not e["isIcon"] and e["fs"] > 0 and not self.inherited_dup(e)]
        # Zielstufe je Schriftgroesse; Kollisionen (zwei Groessen -> eine Stufe) aufloesen.
        # Regeln (Versagensanalyse 2026-08-22 — die alte Auslese "kleinere rutscht tiefer" kaskadierte
        # 16→13→10→8 und drueckte Werte, die schon auf der Leiter lagen, unter die Rollen-Minima):
        # 1. Liegen beide Groessen unter einer lesbaren Hierarchiestufe (< 1.25x, Regel aus gc_typo),
        #    werden sie auf EINE Stufe zusammengelegt statt kuenstlich auseinandergerissen.
        # 2. Sonst weicht die kleinere eine Stufe nach unten — aber nie unter ihr Rollen-Minimum
        #    (aus gc_typo, via --typo); dann weicht stattdessen die groessere nach oben.
        sizes = sorted({round(e["fs"], 2) for e in texts})
        plan = {}
        for fs in sizes:
            n, frac = scale_pos(fs, self.type_base, ty["ratio"])
            plan[fs] = {"n": n, "frac": frac, "step": round(n)}
        floors = {}
        for e in texts:
            k = round(e["fs"], 2)
            floors[k] = max(floors.get(k, 0), self.typo_min.get(e["i"], 0))
        for i in range(len(sizes) - 1, 0, -1):
            hi, lo = sizes[i], sizes[i - 1]
            if plan[lo]["step"] < plan[hi]["step"] or abs(hi - lo) < 0.5:
                continue
            if hi / lo < 1.25:
                plan[lo]["step"] = plan[hi]["step"]
            else:
                down = round_to(self.type_base * ty["ratio"] ** (plan[hi]["step"] - 1), ty["round"])
                if down >= floors.get(lo, 0) or down >= lo:
                    plan[lo]["step"] = plan[hi]["step"] - 1
                else:
                    k = i
                    while k < len(sizes) and (k == i or plan[sizes[k]]["step"] <= plan[sizes[k - 1]]["step"]):
                        plan[sizes[k]]["step"] += 1
                        plan[sizes[k]]["frac"] = abs(plan[sizes[k]]["n"] - plan[sizes[k]]["step"])
                        k += 1
            plan[lo]["frac"] = abs(plan[lo]["n"] - plan[lo]["step"])
        for fs, p in plan.items():
            p["target"] = round_to(self.type_base * ty["ratio"] ** p["step"], ty["round"])
            self.checked += 1
            if p["frac"] <= tol or abs(p["target"] - fs) < 0.3:
                self.on_series += 1
        for e in texts:
            fs = e["fs"]
            p = plan[round(fs, 2)]
            if p["frac"] > tol and abs(p["target"] - fs) >= 0.3:
                self.add("P4", "Schrift", e, "font-size", fs, p["target"], (fs - p["target"]) / p["target"], "patch",
                         f"Stufe {p['n']:+.2f} statt {p['step']:+d} (Basis {fmt(self.type_base)}, Ratio {ty['ratio']:.3f})")
        for e in texts:
            fs = e["fs"]
            # P5 Zeilenhoehe
            if e["lh"] and e["textLen"] > 0:
                q = e["lh"] / fs
                heading = e["tag"] in ("h1", "h2", "h3", "h4", "h5", "h6") or fs >= self.type_base * self.cfg["lineHeight"]["headingFactor"]
                lo, hi = self.cfg["lineHeight"]["heading" if heading else "body"]
                self.checked += 1
                if lo - 0.02 <= q <= hi + 0.02:
                    self.on_series += 1
                else:
                    tq = lo if q < lo else hi
                    self.add("P5", "Zeilenhöhe", e, "line-height", round(q, 3), tq, (q - tq) / tq, "patch",
                             f"{'Titel' if heading else 'Text'}-Korridor {lo}–{hi}", unit="")
            # P6 Zeilenlaenge (nur lange Texte)
            if e["textLen"] >= 80 and e["w"] > 0:
                cpl = e["w"] / (0.5 * fs)
                if cpl > 75 or cpl < 45:
                    self.add("P6", "Zeilenlänge", e, "max-width", round(cpl), 66, (cpl - 66) / 66, "report",
                             f"≈{round(cpl)} Zeichen/Zeile (Soll 45–75) → max-width ≈ {fmt(round(33 * fs))}px", unit=" Zeichen")

    # -- Icons: Groesse im Verhaeltnis zur Nachbarschrift auf der Typo-Leiter
    def check_icons(self):
        ty, tol = self.cfg["type"], self.cfg["tolerance"]["type"]
        for e in self.els:
            if not e["isIcon"]:
                continue
            s = max(e["w"], e["h"])
            if s > self.cfg["icon"]["max"]:
                continue
            # Nachbartext: Geschwister oder Eltern mit Text
            ref = None
            par = self.els[e["parent"]] if e["parent"] is not None and e["parent"] >= 0 else None
            if par:
                sibs = [c for c in self.children[par["i"]] if c["i"] != e["i"] and c["allTextLen"] > 0]
                for sib in sibs:
                    ref = self.leaf_fs(sib)
                    if ref:
                        break
                if not ref and par["textLen"] > 0 and par["fs"] > 0:
                    ref = par["fs"]
            if not ref:
                ref = self.type_base
            self.checked += 1
            if abs(e["w"] - e["h"]) > 1.5 and e["tag"] in ("svg", "img"):
                self.add("R10", "Icon", e, "Seitenverhältnis", round(e["w"], 1), round(e["h"], 1), 0, "report",
                         f"Icon nicht quadratisch ({fmt(e['w'])}×{fmt(e['h'])})", unit="")
            n, frac = scale_pos(s, ref, ty["ratio"])
            target = round_to(ref * ty["ratio"] ** round(n), self.cfg["icon"]["round"])
            if frac <= tol or abs(target - s) < 0.5:
                self.on_series += 1
                continue
            rel = ty["ratio"] ** round(n)
            note = f"Icon {fmt(s)} zu Text {fmt(ref)} = {s / ref:.2f}; nächste Phi-Stufe {rel:.3f} → {fmt(target)}"
            if self.is_protected(s):
                self.add("R10", "Icon", e, "width/height", s, target, (s - target) / target, "geschuetzt", note)
            else:
                self.add("R10", "Icon", e, "width/height", s, target, (s - target) / target, "patch", note)

    # -- P2 Formate, P1 Teilungen (nur Bericht)
    def check_formats_splits(self):
        fm = self.cfg["formats"]
        scope = self.els[0]
        big = [e for e in self.els if e["w"] * e["h"] >= 0.08 * scope["w"] * scope["h"] and e["w"] >= 40 and e["h"] >= 40]
        for e in big:
            ratio = max(e["w"], e["h"]) / min(e["w"], e["h"])
            name, val = min(fm.items(), key=lambda kv: abs(math.log(ratio / kv[1])))
            dev = (ratio - val) / val
            if abs(dev) > self.cfg["tolerance"]["ratio"] and abs(dev) < 0.12:
                other = e["w"] / val if e["w"] >= e["h"] else e["w"] * val
                self.add("P2", "Format", e, "Seitenverhältnis", round(ratio, 3), round(val, 3), dev, "report",
                         f"nahe {name}; bei fixer Breite {fmt(e['w'])} → Höhe {fmt(round(other))}", unit="")
        # Teilungen: Container mit genau zwei substanziellen Kindern
        for e in self.els:
            kids = [c for c in self.children[e["i"]] if c["w"] * c["h"] >= 0.15 * e["w"] * e["h"]]
            if len(kids) != 2:
                continue
            horiz = abs(kids[0]["y"] - kids[1]["y"]) < 2
            a, b = sorted((k["w"] if horiz else k["h"] for k in kids), reverse=True)
            if b <= 0:
                continue
            ratio = a / b
            dev = (ratio - PHI) / PHI
            if abs(dev) <= self.cfg["tolerance"]["ratio"]:
                self.add("P1", "Teilung", e, "Teilung " + ("B" if horiz else "H"), round(ratio, 3), round(PHI, 3), dev, "info",
                         "liegt auf φ (≤3 %) — nicht anfassen", unit="")
            elif abs(dev) < 0.15:
                total = a + b
                self.add("P1", "Teilung", e, "Teilung " + ("B" if horiz else "H"), round(ratio, 3), round(PHI, 3), dev, "report",
                         f"nahe φ: {fmt(a)}/{fmt(b)} → {fmt(round(total * 0.618))}/{fmt(round(total * 0.382))} (Produktentscheidung, nicht automatisch)", unit="")

    # -- Aussenrand: Abstand des Aufbaus zum Viewport-Rand (R5/R6, P9) — liegt ausserhalb des Scopes, daher nur Bericht
    def check_outer(self):
        sc, vp = self.d["scope"], self.d["viewport"]
        if sc["sel"] == "body":
            return
        left, right, top = sc["x"], vp["w"] - sc["x"] - sc["w"], sc["y"]
        scope = self.els[0]
        tol = self.cfg["tolerance"]["symmetry"]
        if max(left, right) >= 2 and abs(left - right) > max(1.0, tol * max(left, right)):
            m, _ = nearest(self.spacing, (left + right) / 2)
            self.add("P9", "Außenrand", scope, "Rand links/rechts", left, right, (left - right) / max(left, right), "report",
                     f"Aufbau sitzt nicht mittig im Viewport → beide {fmt(m)}")
        for name, v in (("Rand links", left), ("Rand rechts", right), ("Rand oben", top)):
            if v < self.cfg["spacing"]["min"]:
                continue
            m, dev = nearest(self.spacing, v)
            self.checked += 1
            if abs(dev) <= self.cfg["tolerance"]["series"] or abs(v - m) < 0.5:
                self.on_series += 1
            else:
                self.add("P7", "Außenrand", scope, name, v, m, dev, "report", "Abstand zum Viewport-Rand (Elternelement des Scopes)")

    def run(self):
        self.check_outer()
        self.check_spacing()
        self.check_margins()
        self.check_inner_outer()
        self.check_type()
        self.check_icons()
        self.check_formats_splits()
        # P9 (Symmetrie/Kanon) schlaegt P7 (Einzel-Snap) auf derselben Eigenschaft
        p9 = {(f["sel"], f["prop"]) for f in self.findings if f["rule"] == "P9" and f["action"] == "patch"}
        self.findings = [f for f in self.findings if not (f["rule"] == "P7" and (f["sel"], f["prop"]) in p9)]
        return self.findings


# ---------------------------------------------------------------- Ausgabe

def build_patch(findings, important):
    by_sel = defaultdict(dict)
    notes = defaultdict(list)
    for f in findings:
        if f["action"] != "patch":
            continue
        prop = f["prop"]
        if prop == "width/height":
            by_sel[f["sel"]]["width"] = f"{fmt(f['soll'])}px"
            by_sel[f["sel"]]["height"] = f"{fmt(f['soll'])}px"
        elif prop == "line-height":
            by_sel[f["sel"]]["line-height"] = fmt(f["soll"])
        elif prop.startswith("padding (alle"):
            for side in ("top", "right", "bottom", "left"):
                by_sel[f["sel"]].setdefault(f"padding-{side}", f"{fmt(f['soll'])}px")
        elif prop in ("gap (Eltern)",):
            continue
        else:
            by_sel[f["sel"]][prop] = f"{fmt(f['soll'])}px"
        notes[f["sel"]].append(f"{f['rule']} {f['prop']}: {fmt(f['ist']) if isinstance(f['ist'], (int, float)) else f['ist']} → {fmt(f['soll']) if isinstance(f['soll'], (int, float)) else f['soll']}")
    imp = " !important" if important else ""
    lines = ["/* goldencut — Korrekturwerte. Werte in die Quelle/Tokens uebernehmen; Selektoren sind Messpfade. */"]
    for sel, props in by_sel.items():
        lines.append("")
        lines.append("/* " + "; ".join(notes[sel]) + " */")
        lines.append(sel + " {")
        for p, v in props.items():
            lines.append(f"  {p}: {v}{imp};")
        lines.append("}")
    return "\n".join(lines) + "\n", len(by_sel)


def build_report(data, an, findings, cfg):
    ty = cfg["type"]
    total = an.checked
    on = an.on_series
    idx = round(100 * on / total) if total else 0
    patches = [f for f in findings if f["action"] == "patch"]
    reports = [f for f in findings if f["action"] in ("report", "geschuetzt")]
    infos = [f for f in findings if f["action"] == "info"]

    L = []
    L.append(f"# goldencut — {data.get('name', 'Messung')}")
    L.append("")
    L.append(f"Ziel: `{data.get('target', '')}`  ·  Scope: `{data['scope']['sel']}` ({fmt(data['scope']['w'])}×{fmt(data['scope']['h'])} px, Viewport {data['viewport']['w']}×{data['viewport']['h']})  ·  {len(data['elements'])} Elemente")
    L.append("")
    L.append("## Zielreihe")
    L.append("")
    L.append(f"- Abstände: Ratio {cfg['spacing']['ratio']:.3f}, Basen {cfg['spacing']['bases']} → {' · '.join(fmt(v) for v in an.spacing if v <= 144)}")
    L.append(f"- Schrift/Icons: Ratio {ty['ratio']:.3f}, Basis {fmt(an.type_base)} → {' · '.join(fmt(v) for v in an.type_series if v <= 72)}")
    L.append(f"- Toleranzen: Reihe ±{int(cfg['tolerance']['series'] * 100)} %, Skala |Δn| ≤ {cfg['tolerance']['type']}, Verhältnis ±{int(cfg['tolerance']['ratio'] * 100)} %  ·  geschützt: {cfg['protect']}")
    L.append("")
    L.append("## Reihen-Treue (Harmonie-Index)")
    L.append("")
    L.append(f"**{idx} %** — {on} von {total} geprüften Maßen liegen auf der Zielreihe. {len(patches)} Korrekturen, {len(reports)} Hinweise. "
             "Die Zahl misst Einzelmaße auf der Reihe — nicht Gruppen, nicht Lücken, nicht das Auge; dafür stehen Ordnung/Ruhe/Balance (layout-report) und Lesbarkeit (typo-report). "
             "Immer alle fünf zusammen lesen.")
    L.append("")

    def table(rows, title):
        if not rows:
            return
        L.append(f"## {title}")
        L.append("")
        L.append("| Regel | Element | Eigenschaft | Ist | Soll | Abw. | Hinweis |")
        L.append("|---|---|---|---|---|---|---|")
        for f in rows:
            ist = fmt(f["ist"]) if isinstance(f["ist"], (int, float)) else f["ist"]
            soll = fmt(f["soll"]) if isinstance(f["soll"], (int, float)) else f["soll"]
            u = f["unit"] if f["unit"] != "px" else " px"
            dev = f"{f['dev']:+.1f} %" if isinstance(f["dev"], (int, float)) else ""
            L.append(f"| {f['rule']} | {f['label']} | {f['prop']} | {ist}{u} | {soll}{u} | {dev} | {f['note']} |")
        L.append("")

    order = ["Abstand", "Radius", "Rand-Symmetrie", "Rand-Kanon", "Innen:Außen", "Schrift", "Zeilenhöhe", "Icon"]
    for cat in order:
        table([f for f in patches if f["cat"] == cat], f"Korrektur — {cat}")
    table(reports, "Hinweise (nicht automatisch geändert)")
    table(infos, "Schon auf φ (Bias-Guard: nur ≤ 3 % gemeldet)")

    L.append("## Lesart")
    L.append("")
    L.append("Korrekturen sind Snaps bestehender Maße auf die Zielreihe — keine neuen Elemente, keine Layoutänderungen. "
             "Teilungen und Formate stehen nur als Hinweis, weil sie Produktentscheidungen sind. "
             "Ein hoher Index heißt „konsistent“, nicht „schön“: Phi ist hier Konsistenzsystem, kein Schönheitsgesetz (regeln.md §5). "
             "Reihenfolge beim Anwenden: Schrift → Lücken → Polster → Kachel — Kachelmaße zuletzt, sonst wird das Innenleben verschoben (Probedurchlauf 2026-08-22).")
    return "\n".join(L) + "\n", idx


def load_cfg(path, args):
    cfg = json.loads(json.dumps(DEFAULT_CFG))
    if path:
        user = json.loads(Path(path).read_text(encoding="utf-8"))
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    if args.type_base:
        cfg["type"]["base"] = args.type_base
    if args.type_ratio:
        cfg["type"]["ratio"] = args.type_ratio
    if args.spacing_bases:
        cfg["spacing"]["bases"] = [float(x) for x in args.spacing_bases.split(",")]
    if args.spacing_ratio:
        cfg["spacing"]["ratio"] = args.spacing_ratio
    if args.grid:
        cfg["spacing"]["round"] = args.grid
    if args.protect is not None:
        cfg["protect"] = [] if args.protect.lower() == "none" else [float(x) for x in args.protect.split(",")]
    return cfg


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("measure", help="measure.json aus gc_measure")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--type-base", type=float, default=None)
    ap.add_argument("--type-ratio", type=float, default=None, help="1.272 (√φ, Default) oder 1.618 (φ)")
    ap.add_argument("--spacing-bases", default=None, help="z.B. 8,16 (Default) oder 4")
    ap.add_argument("--spacing-ratio", type=float, default=None)
    ap.add_argument("--grid", type=float, default=None, help="Rundung der Abstandsreihe, z.B. 4 fuer 4-px-Raster")
    ap.add_argument("--protect", default=None, help="Komma-Liste geschuetzter Werte oder 'none'")
    ap.add_argument("--typo", default=None, help="typo.json aus gc_typo — Rollen-Minima als Boden fuer Abwaerts-Snaps")
    ap.add_argument("--canon", action="store_true", help="Satzspiegel-Kanon: padding-bottom = top·φ erzwingen")
    ap.add_argument("--fix-all", action="store_true", help="auch Innen:Außen-Verstoesse patchen")
    ap.add_argument("--suffix", default="", help="Dateinamen-Suffix (z.B. -after)")
    args = ap.parse_args()

    data = json.loads(Path(args.measure).read_text(encoding="utf-8"))
    cfg = load_cfg(args.config, args)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    typo_min = {}
    if args.typo and Path(args.typo).exists():
        typo = json.loads(Path(args.typo).read_text(encoding="utf-8"))
        typo_min = {t["i"]: t.get("minPx", 0) for t in typo.get("texts", [])}
    an = Analyzer(data, cfg, canon=args.canon, fix_all=args.fix_all, typo_min=typo_min)
    findings = an.run()
    report, idx = build_report(data, an, findings, cfg)
    patch, n_sel = build_patch(findings, important=False)
    override, _ = build_patch(findings, important=True)

    (out / f"report{args.suffix}.md").write_text(report, encoding="utf-8")
    (out / f"patch{args.suffix}.css").write_text(patch, encoding="utf-8")
    (out / f"patch{args.suffix}.override.css").write_text(override, encoding="utf-8")
    (out / f"corrections{args.suffix}.json").write_text(json.dumps({
        "index": idx, "checked": an.checked, "onSeries": an.on_series,
        "typeBase": an.type_base, "spacingSeries": an.spacing, "typeSeries": an.type_series,
        "findings": findings}, ensure_ascii=False, indent=1), encoding="utf-8")

    n_patch = sum(1 for f in findings if f["action"] == "patch")
    print(f"Reihen-Treue (Harmonie-Index) {idx} % ({an.on_series}/{an.checked}) · {n_patch} Korrekturen auf {n_sel} Selektoren · {sum(1 for f in findings if f['action'] in ('report', 'geschuetzt'))} Hinweise -> {out / ('report' + args.suffix + '.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
