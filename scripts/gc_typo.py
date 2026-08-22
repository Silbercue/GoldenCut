#!/usr/bin/env python3
"""gc_typo — Schritt 1 des Austarierens: URTEIL ueber Schriftgroessen, ohne etwas zu aendern.

Prueft jeden Text einer Messung (gc_measure, before.json) gegen die Korridore der Lesbarkeit
(reference/schriftgroessen-abstaende.md, Pruefkette T1–T6) und die Unterscheidbarkeit der
Hierarchie (T4):

  T1 Sehwinkel der x-Hoehe am Leseabstand   (hart ≥ 0,2°, Komfort je Rolle; +10 % hell auf dunkel / Light-Schnitt / schwacher Kontrast)
  T2 Rolle → Mindestgroesse in px            (Nebentext/Label ≥ 11, Lesetext ≥ 14)
  T3 Zeilenlaenge                            (mehrzeilig: 45–75 Zeichen, < 35 eng)
  T4 Hierarchie                              (Stufen ≥ 1,25× oder Gewicht/Farbe; ≤ 5 Groessen; Kennzahl dominant)
  T5 Zeilenhoehe nach Rolle                  (Lesetext 1,25–1,5, Titel 1,0–1,25)
  T6 Laufweite                               (≥ 34 px negativ, ≤ 12 px / Versalien positiv — nur Hinweis)

Ausgabe: typo-report.md, typo.json, typo-overlay.png (Urteil auf dem Screenshot) und eine
Klartext-Zusammenfassung auf stdout. Kein Patch — erst sehen, ob das Urteil mit dem Auge
uebereinstimmt, dann korrigieren lassen.

Aufruf:
  gc_typo.py before.json --out DIR [--config goldencut.config.json] [--distance 450] [--suffix -after]
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gc_roles import ROLE_DE, assign_roles  # noqa: E402

PX_MM = 25.4 / 96  # CSS-px in mm
PHI = (1 + 5 ** 0.5) / 2

DEFAULT = {
    "distanceMm": "auto",
    "floorDeg": 0.20,
    "comfortDeg": {"body": 0.27, "consult": 0.22, "label": 0.22, "action": 0.24, "subtitle": 0.27, "title": 0.30, "number": 0.35},
    "minPx": {"consult": 11, "label": 11, "action": 12, "body": 14, "subtitle": 14, "title": 16, "number": 16},
    "lightOnDark": 1.10, "lightWeight": 1.10, "lowContrast": 1.10,
    "cpl": [45, 75], "cplSoft": 35,
    # Zeilenhoehe: phi (1,618) ist die Obergrenze fuer Lesetext (R8, wie P5 in run). Pearson: q waechst mit der
    # Zeilenbreite und erreicht phi erst bei der goldenen Zeilenlaenge (cplPhi) — das Soll steht als Hinweis.
    "lineHeight": {"body": [1.2, 1.618], "consult": [1.2, 1.618], "label": [1.0, 1.618], "action": [1.0, 1.618],
                   "subtitle": [1.1, 1.3], "title": [1.0, 1.25], "number": [0.9, 1.2]},
    "lhMin": 1.2, "cplPhi": 75,
    "hierarchyMin": 1.25, "maxSizes": 5, "numberDominance": 2.0,
    "touch": 44,
}


def fmt(v):
    if v is None:
        return "–"
    if abs(v - round(v)) < 0.005:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def auto_distance(vw):
    # Grobe Zuordnung ueber die Viewport-Breite; --distance ueberschreibt. iPad quer (1024–1366) zaehlt als Tablet.
    if vw <= 500:
        return 300, "Handy"
    if vw <= 1366:
        return 450, "Tablet"
    if vw <= 1600:
        return 550, "Laptop"
    return 700, "Desktop"


def angle_deg(px):
    return None if px is None else math.degrees(math.atan(px * PX_MM / DIST[0]))


def px_for_angle(deg, xh):
    return DIST[0] * math.tan(math.radians(deg)) / xh / PX_MM


DIST = (300, "Handy")


# ------------------------------------------------------------------ Pruefungen

def judge_texts(data, texts, cfg):
    fonts = data.get("fonts", {})
    out = []
    for e in texts:
        fm = fonts.get(e.get("fontKey") or "", {})
        xh = fm.get("xHeight") or 0.5
        cap = fm.get("capHeight") or 0.7
        role = e["role"]
        fs = e["fs"]
        xpx = fs * xh
        ang = angle_deg(xpx)
        # Faktoren, die mehr Groesse verlangen
        factors, why = 1.0, []
        if e.get("lightOnDark"):
            factors *= cfg["lightOnDark"]; why.append("hell auf dunkel")
        fw = int(e["fw"]) if str(e.get("fw", "400")).isdigit() else 400
        if fw < 400:
            factors *= cfg["lightWeight"]; why.append("Light-Schnitt")
        ctr = e.get("contrastMax")
        if ctr is not None and ctr < 1.5:
            e["bgUncertain"] = True  # so wenig Kontrast gestaltet niemand — der Grund ist nicht sichtbar (gemalt, Verlauf, Overlay)
        ctr_known = ctr is not None and not e.get("bgUncertain")
        if ctr_known and ctr < 4.5:
            factors *= cfg["lowContrast"]; why.append(f"Kontrast {ctr:.1f}:1")
        floor = cfg["floorDeg"] * factors
        comfort = cfg["comfortDeg"].get(role, 0.25) * factors
        min_px = cfg["minPx"].get(role, 11)
        issues, level, target_px = [], "ok", None
        if ang < floor:
            level = "hart"
            target_px = math.ceil(px_for_angle(floor, xh) * 2) / 2
            issues.append(f"x-Höhe nur {ang:.2f}° (Boden {floor:.2f}°) → mind. {fmt(target_px)} px")
        elif fs < min_px:
            level = "hart"
            target_px = min_px
            issues.append(f"unter Mindestgröße {min_px} px für {ROLE_DE[role]}")
        elif ang < comfort:
            level = "knapp"
            target_px = math.ceil(px_for_angle(comfort, xh) * 2) / 2
            issues.append(f"x-Höhe {ang:.2f}° unter Komfort {comfort:.2f}° für {ROLE_DE[role]} → {fmt(target_px)} px wären bequem")
        if why and level != "ok":
            issues[-1] += " (" + ", ".join(why) + ")"
        # T3 Zeilenlaenge
        cpl = None
        if (e.get("lines") or 0) >= 2 and e.get("lineSumW") and e["textLen"]:
            char_w = e["lineSumW"] / e["textLen"]
            cpl = e["lineMaxW"] / char_w if char_w > 0 else None
            if cpl:
                lo, hi = cfg["cpl"]
                if cpl > hi:
                    issues.append(f"≈{cpl:.0f} Zeichen/Zeile — zu lang (Soll ≤ {hi}) → max-width ≈ {fmt(round(hi * char_w))} px")
                    level = level if level == "hart" else "knapp"
                elif cpl < cfg["cplSoft"]:
                    issues.append(f"≈{cpl:.0f} Zeichen/Zeile — eng (Soll ≥ {lo})")
                    level = level if level == "hart" else "knapp"
                elif cpl < lo:
                    issues.append(f"≈{cpl:.0f} Zeichen/Zeile — knapp unter {lo}, für UI-Karten vertretbar")
        # T5 Zeilenhoehe
        q, target_lh, lh_hint = None, None, None
        if e.get("lh") and fs > 0:
            q = e["lh"] / fs
            lo, hi = cfg["lineHeight"].get(role, [1.0, 1.618])
            multi = (e.get("lines") or 0) >= 2
            if not multi:
                pass  # Einzeiler: Zeilenhoehe ist Boxhoehe, kein Lesekorridor (Abstand regelt Schritt 2)
            elif q < lo - 0.02 or q > hi + 0.02:
                target_lh = round(min(max(q, lo), hi), 2)
                issues.append(f"Zeilenhöhe {q:.2f} außerhalb {lo}–{fmt(round(hi, 2))} für {ROLE_DE[role]}")
                level = level if level == "hart" else "knapp"
            elif cpl and role in ("body", "consult"):
                # Pearson (R8): q = q_min + (w / w_phi) · (phi − q_min); phi erst bei der goldenen Zeilenlaenge
                q_phi = cfg["lhMin"] + min(1.0, cpl / cfg["cplPhi"]) * (PHI - cfg["lhMin"])
                if abs(q - q_phi) > 0.1:
                    lh_hint = f"Zeilenhöhe {q:.2f} — nach Pearson bei {cpl:.0f} Zeichen/Zeile ≈ {q_phi:.2f} (φ erst ab {cfg['cplPhi']} Zeichen)"
        # T6 Laufweite (nur Hinweis)
        hints = []
        if lh_hint:
            hints.append(lh_hint)
        ls_em = (e.get("ls") or 0) / fs if fs else 0
        upper = e.get("textTransform") == "uppercase"
        if fs >= 34 and ls_em >= 0:
            hints.append("große Schrift ohne negative Laufweite (−0,01…−0,02 em üblich)")
        if fs <= 12 and upper and ls_em <= 0:
            hints.append("kleine Versalien ohne Sperrung (+0,03…+0,05 em üblich)")
        if e.get("bgUncertain"):
            hints.append("Kontrast nicht messbar (Hintergrundbild)")
        elif ctr_known and ctr < (3.0 if fs >= 24 else 4.5):
            hints.append(f"Kontrast {ctr:.1f}:1 unter WCAG ({'3' if fs >= 24 else '4,5'}:1)")
        if not fm.get("loaded", True):
            hints.append(f"Schrift „{fm.get('family', '?')}“ nicht geladen — Metriken vom Fallback")
        out.append({
            "i": e["i"], "sel": e["sel"], "tag": e["tag"], "text": e["text"], "role": role, "roleConf": e["roleConf"],
            "fs": fs, "fw": fw, "xHeight": xh, "capHeight": cap, "xPx": round(xpx, 2), "angle": round(ang, 3),
            "floor": round(floor, 3), "comfort": round(comfort, 3), "minPx": min_px,
            "lines": e.get("lines") or 1, "cpl": round(cpl) if cpl else None, "lh": round(q, 2) if q else None,
            "contrast": ctr, "bgUncertain": bool(e.get("bgUncertain")), "lightOnDark": bool(e.get("lightOnDark")),
            "level": level, "issues": issues, "hints": hints, "targetPx": target_px, "targetLh": target_lh,
            "box": [e["x"], e["y"], e["w"], e["h"]], "textBox": [e.get("textLeft"), e.get("textTop"), e.get("lineMaxW"), (e.get("lh") or fs * 1.2) * max(1, e.get("lines") or 1)],
        })
    return out


def judge_hierarchy(judged, base, cfg):
    """T4: Groessenstufen, Rollen, Unterscheidbarkeit."""
    sizes = {}
    for j in judged:
        key = round(j["fs"] * 2) / 2
        s = sizes.setdefault(key, {"fs": key, "roles": set(), "weights": set(), "n": 0, "examples": []})
        s["roles"].add(j["role"]); s["weights"].add(j["fw"]); s["n"] += 1
        if len(s["examples"]) < 3:
            s["examples"].append(j["text"][:18])
    ladder = sorted(sizes.values(), key=lambda s: s["fs"])
    findings = []
    rank = {"consult": 0, "label": 0, "action": 0, "body": 1, "subtitle": 2, "title": 3, "number": 4}
    for a, b in zip(ladder, ladder[1:]):
        ratio = b["fs"] / a["fs"]
        if ratio >= cfg["hierarchyMin"]:
            continue
        ra, rb = max(rank[r] for r in a["roles"]), max(rank[r] for r in b["roles"])
        wdiff = max(b["weights"]) - max(a["weights"])
        if ra == rb:
            findings.append({"kind": "doppelt", "a": a, "b": b, "ratio": ratio,
                             "text": f"{fmt(a['fs'])} und {fmt(b['fs'])} px tragen dieselbe Rolle ({', '.join(ROLE_DE[r] for r in a['roles'] | b['roles'])}) — zwei Größen für eine Aufgabe; eine reicht"})
        elif wdiff < 200:
            findings.append({"kind": "unklar", "a": a, "b": b, "ratio": ratio,
                             "text": f"{fmt(a['fs'])} px ({', '.join(ROLE_DE[r] for r in a['roles'])}) und {fmt(b['fs'])} px ({', '.join(ROLE_DE[r] for r in b['roles'])}) liegen nur {ratio:.2f}× auseinander, ohne Gewichtsunterschied — als Hierarchie nicht lesbar (Soll ≥ {cfg['hierarchyMin']}× oder +200 Gewicht)"})
    if len(ladder) > cfg["maxSizes"]:
        findings.append({"kind": "viele", "text": f"{len(ladder)} verschiedene Schriftgrößen ({' · '.join(fmt(s['fs']) for s in ladder)}) — mehr als {cfg['maxSizes']}; Rollen-Varianten zusammenlegen"})
    nums = [j for j in judged if j["role"] == "number"]
    if nums:
        mn = min(j["fs"] for j in nums)
        if mn / base < cfg["numberDominance"]:
            findings.append({"kind": "zahl", "text": f"Kennzahl {fmt(mn)} px ist nur {mn / base:.2f}× Grundgröße {fmt(base)} — dominant wird sie ab {cfg['numberDominance']}× ({fmt(base * cfg['numberDominance'])} px)"})
    titles = [j for j in judged if j["role"] == "title"]
    for t in titles:
        if t["fs"] / base < cfg["hierarchyMin"] and t["fw"] < 600:
            findings.append({"kind": "titel", "text": f"Titel „{t['text'][:18]}“ {fmt(t['fs'])} px ist weder ≥ {cfg['hierarchyMin']}× Grundgröße noch fett — hebt sich nicht ab"})
    return ladder, findings


def touch_hints(data, cfg):
    hints = []
    for e in data["elements"]:
        if e.get("interactive") and e.get("allTextLen", 0) > 0 and min(e["w"], e["h"]) < cfg["touch"] - 0.5 and e["tag"] != "a":
            hints.append(f"{e['tag']}{'.' + e['cls'].split(' ')[0] if e['cls'] else ''} „{e['text'][:16]}“: {fmt(e['w'])}×{fmt(e['h'])} px — Touch-Ziel unter {cfg['touch']} px")
    return hints


# ------------------------------------------------------------------ Score, Klartext

def score(judged):
    if not judged:
        return 0
    pts = sum(1 if j["level"] == "ok" else 0.5 if j["level"] == "knapp" else 0 for j in judged)
    s = round(100 * pts / len(judged))
    if any(j["level"] == "hart" for j in judged):
        s = min(s, 50)
    return s


def changes(judged, touch):
    """Konkrete Aenderungen als Punkte: Ist → Soll, je Text eine Zeile. Leer = nichts zu tun."""
    L = []
    for j in judged:
        name = f"„{j['text'][:24]}“ ({ROLE_DE[j['role']]})"
        if j.get("targetPx") and j["targetPx"] > j["fs"]:
            L.append(f"{name}: Schriftgröße {fmt(j['fs'])} → {fmt(j['targetPx'])} px")
        if j.get("targetLh"):
            L.append(f"{name}: Zeilenhöhe {j['lh']} → {fmt(j['targetLh'])}")
        for iss in j["issues"]:
            if "max-width" in iss:
                L.append(f"{name}: {iss.split('→', 1)[1].strip()}")
    for t in touch:
        L.append(t.replace(" — Touch-Ziel unter ", " → mind. ").replace(" px", " px", 1))
    return L


def klartext(judged, ladder, hier, base, questions, sc, touch):
    L = []
    hart = [j for j in judged if j["level"] == "hart"]
    knapp = [j for j in judged if j["level"] == "knapp"]
    L.append(f"Lesbarkeit {sc} % — {len(judged)} Texte am {DIST[1]} ({DIST[0] / 10:.0f} cm), Grundgröße {fmt(base)} px, "
             f"{len(ladder)} Größen: {' · '.join(fmt(s['fs']) for s in ladder)}.")
    if hart:
        L.append("Zu klein: " + "; ".join(f"„{j['text'][:18]}“ {fmt(j['fs'])} px — {j['issues'][0]}" for j in hart[:3]) + ("; …" if len(hart) > 3 else ""))
    if knapp:
        L.append("Knapp: " + "; ".join(f"„{j['text'][:18]}“ {fmt(j['fs'])} px — {j['issues'][0]}" for j in knapp[:3]) + ("; …" if len(knapp) > 3 else ""))
    if not hart and not knapp:
        L.append("Alle Texte liegen im Korridor für ihre Rolle.")
    for h in hier[:3]:
        L.append("Hierarchie: " + h["text"])
    if questions:
        L.append("Unsicher: " + " ".join(questions))
    ch = changes(judged, touch)
    L.append("Änderungen:" if ch else "Änderungen: keine")
    for c in ch:
        L.append(f"- {c}")
    return L



# ------------------------------------------------------------------ Overlay

def overlay(shot, out_png, data, judged, sc):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    img = Image.open(shot).convert("RGBA")
    scale = img.width / data["scope"]["w"]
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", max(10, int(10 * scale)))
    except Exception:
        font = ImageFont.load_default()
    COL = {"hart": (220, 40, 40), "knapp": (240, 150, 20), "ok": (40, 160, 80)}
    for j in judged:
        x, y, w, h = j["box"]
        tb = j["textBox"]
        if tb[0] is not None and tb[2]:
            x, y, w, h = tb[0], tb[1], tb[2], tb[3]
        c = COL[j["level"]]
        r = [x * scale, y * scale, (x + w) * scale, (y + h) * scale]
        d.rectangle(r, outline=c + (255,), width=2 if j["level"] != "ok" else 1)
        if j["level"] != "ok":
            d.rectangle(r, fill=c + (36,))
        tag = f"{ROLE_DE[j['role']][:5]} {fmt(j['fs'])}px {j['angle']:.2f}°"
        tw = d.textlength(tag, font=font)
        ty = r[1] - font.size - 2 if r[1] - font.size - 2 > 0 else r[3] + 1
        d.rectangle([r[0], ty, r[0] + tw + 4, ty + font.size + 2], fill=c + (210,))
        d.text((r[0] + 2, ty + 1), tag, fill=(255, 255, 255, 255), font=font)
    # Legende unten
    pad = int(8 * scale)
    legend_h = font.size * 2 + pad * 2
    canvas = Image.new("RGBA", (img.width, img.height + legend_h), (255, 255, 255, 255))
    canvas.paste(Image.alpha_composite(img, lay), (0, 0))
    d2 = ImageDraw.Draw(canvas)
    y0 = img.height + pad
    d2.text((pad, y0), f"Lesbarkeit {sc} %  ·  {DIST[1]} {DIST[0] / 10:.0f} cm  ·  Kästen = x-Höhen-Sehwinkel je Text", fill=(0, 0, 0, 255), font=font)
    x = pad
    for name, c in (("zu klein", COL["hart"]), ("knapp", COL["knapp"]), ("im Korridor", COL["ok"])):
        d2.rectangle([x, y0 + font.size + 4, x + font.size, y0 + 2 * font.size + 4], fill=c + (255,))
        d2.text((x + font.size + 4, y0 + font.size + 3), name, fill=(0, 0, 0, 255), font=font)
        x += font.size + 4 + d2.textlength(name, font=font) + pad * 2
    canvas.convert("RGB").save(out_png)
    return out_png


# ------------------------------------------------------------------ Report

def report(data, judged, ladder, hier, base, questions, sc, touch):
    L = [f"# goldencut · Typo-Urteil — {data.get('name', 'Messung')}", ""]
    L.append(f"Ziel: `{data.get('target', '')}`  ·  Scope: `{data['scope']['sel']}` ({fmt(data['scope']['w'])}×{fmt(data['scope']['h'])} px, Viewport {data['viewport']['w']}×{data['viewport']['h']})  ·  Leseabstand {DIST[1]} {DIST[0]} mm  ·  Grundgröße {fmt(base)} px")
    L.append("")
    L.append("## Urteil")
    L.append("")
    for line in klartext(judged, ladder, hier, base, questions, sc, touch):
        L.append("- " + line)
    L.append("")
    L.append("## Schriften")
    L.append("")
    L.append("| Familie | Gewicht | x-Höhe | Versalhöhe | Stamm/em | Ø Breite | geladen |")
    L.append("|---|---|---|---|---|---|---|")
    seen = set()
    for f in data.get("fonts", {}).values():
        if (f["family"], f["weight"], f["style"]) in seen:
            continue
        seen.add((f["family"], f["weight"], f["style"]))
        L.append(f"| {f['family']} | {f['weight']} | {f['xHeight']} | {f['capHeight']} | {f['stem']} | {f['advance']} | {'ja' if f['loaded'] else 'nein (Fallback)'} |")
    L.append("")
    L.append("## Texte (T1–T3, T5)")
    L.append("")
    L.append("| Urteil | Element | Rolle | px | x-Höhe px | Sehwinkel | Boden / Komfort | Zeilen | CPL | LH | Kontrast | Befund |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    mark = {"hart": "🔴", "knapp": "🟠", "ok": "🟢"}
    for j in judged:
        ctr = "Bild" if j["bgUncertain"] else (f"{j['contrast']:.1f}" if j["contrast"] else "–")
        conf = "" if j["roleConf"] >= 0.6 else " ?"
        L.append(f"| {mark[j['level']]} | {j['tag']} „{j['text'][:18]}“ | {ROLE_DE[j['role']]}{conf} | {fmt(j['fs'])} | {fmt(j['xPx'])} | {j['angle']:.2f}° | {j['floor']:.2f} / {j['comfort']:.2f} | {j['lines']} | {j['cpl'] or '–'} | {j['lh'] or '–'} | {ctr} | {'; '.join(j['issues'] + j['hints'])} |")
    L.append("")
    L.append("## Hierarchie (T4)")
    L.append("")
    L.append("| px | Rollen | Gewichte | Anzahl | Beispiele | Verhältnis zur nächsten |")
    L.append("|---|---|---|---|---|---|")
    for a, b in zip(ladder, ladder[1:] + [None]):
        ratio = f"{b['fs'] / a['fs']:.2f}×" if b else "–"
        L.append(f"| {fmt(a['fs'])} | {', '.join(ROLE_DE[r] for r in sorted(a['roles']))} | {', '.join(str(w) for w in sorted(a['weights']))} | {a['n']} | {', '.join(a['examples'])} | {ratio} |")
    L.append("")
    for h in hier:
        L.append(f"- {h['text']}")
    if not hier:
        L.append("- Stufen sind unterscheidbar, Anzahl im Rahmen.")
    L.append("")
    ch = changes(judged, touch)
    L.append("## Änderungen")
    L.append("")
    for c in (ch or ["keine — alle Texte liegen im Korridor"]):
        L.append(f"- {c}")
    L.append("")
    if touch:
        L.append("## Touch-Ziele")
        L.append("")
        for t in touch:
            L.append(f"- {t}")
        L.append("")
    if questions:
        L.append("## Rückfragen")
        L.append("")
        for q in questions:
            L.append(f"- {q}")
        L.append("")
    L.append("## Lesart")
    L.append("")
    L.append("Dieses Urteil ändert nichts. Boden = 0,2° x-Höhe (Legge & Bigelow 2011, kritische Schriftgröße), Komfort je Rolle "
             "(Print-Praxis 0,23°, UI-Praxis ≈ 0,4° auf dem Handy). Hell auf dunkel, Light-Schnitte und schwacher Kontrast verlangen +10 %. "
             "Zeilenhöhe: φ (1,618) ist die Obergrenze; das längenabhängige Pearson-Soll steht als Hinweis. "
             "Hierarchie gilt als lesbar ab 1,25× oder +200 Gewicht. Rollen sind Heuristik — bei „?“ nachfragen. "
             "Lesbarkeit = Anteil der Texte im Korridor (knapp zählt halb); ein harter Verstoß deckelt bei 50 %.")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ main

def main():
    global DIST
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("measure")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--distance", type=float, default=None, help="Leseabstand in mm (Default: aus Viewport-Breite)")
    ap.add_argument("--suffix", default="")
    args = ap.parse_args()

    data = json.loads(Path(args.measure).read_text(encoding="utf-8"))
    cfg = json.loads(json.dumps(DEFAULT))
    roles_override = {}
    if args.config:
        user = json.loads(Path(args.config).read_text(encoding="utf-8"))
        for k, v in (user.get("legibility") or {}).items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
        roles_override = user.get("roles") or {}
    if args.distance:
        DIST = (args.distance, "Abstand")
    elif cfg["distanceMm"] != "auto":
        DIST = (float(cfg["distanceMm"]), "Config")
    else:
        DIST = auto_distance(data["viewport"]["w"])

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    texts, base, questions = assign_roles(data, roles_override)
    judged = judge_texts(data, texts, cfg)
    ladder, hier = judge_hierarchy(judged, base, cfg)
    touch = touch_hints(data, cfg)
    sc = score(judged)
    for s in ladder:
        s["roles"], s["weights"] = sorted(s["roles"]), sorted(s["weights"])

    (out / f"typo-report{args.suffix}.md").write_text(report(data, judged, ladder, hier, base, questions, sc, touch), encoding="utf-8")
    (out / f"typo{args.suffix}.json").write_text(json.dumps({
        "score": sc, "distanceMm": DIST[0], "device": DIST[1], "base": base, "texts": judged, "ladder": ladder,
        "hierarchy": [h["text"] for h in hier], "questions": questions, "touch": touch, "changes": changes(judged, touch)}, ensure_ascii=False, indent=1), encoding="utf-8")
    png = None
    if data.get("shot") and Path(data["shot"]).exists():
        png = overlay(data["shot"], out / f"typo-overlay{args.suffix}.png", data, judged, sc)
    for line in klartext(judged, ladder, hier, base, questions, sc, touch):
        print(line)
    print(f"Report: {out / ('typo-report' + args.suffix + '.md')}" + (f"  ·  Overlay: {png}" if png else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
