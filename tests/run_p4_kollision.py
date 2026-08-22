#!/usr/bin/env python3
"""P4-Kollisionsaufloesung ohne Browser: die alte Auslese "kleinere rutscht tiefer" kaskadierte
16→13→10→8 und drueckte Werte unter die Rollen-Minima (Versagensanalyse 2026-08-22).
Prueft die drei Regeln: Zusammenlegen unter 1.25x, Boden aus gc_typo, Ausweichen nach oben."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from gc_analyze import DEFAULT_CFG, Analyzer  # noqa: E402
import copy  # noqa: E402


def el(i, fs, text="x" * 40, tag="p"):
    return {"i": i, "sel": f"#e{i}", "tag": tag, "text": text, "textLen": len(text), "fs": fs,
            "fw": 400, "isIcon": False, "parent": None, "lh": None, "w": 300, "h": 20,
            "pt": 0, "pr": 0, "pb": 0, "pl": 0, "mt": 0, "mr": 0, "mb": 0, "ml": 0,
            "rowGap": 0, "colGap": 0, "radius": 0, "display": "block", "children": 0,
            "x": 0, "y": 0, "cls": "", "depth": 1, "hasBox": False}


def analyzer(sizes, typo_min=None, base=13.0):
    cfg = copy.deepcopy(DEFAULT_CFG)
    cfg["type"]["base"] = base
    data = {"elements": [el(i, fs) for i, fs in enumerate(sizes)], "scope": {"w": 390, "h": 800}}
    an = Analyzer(data, cfg, typo_min=typo_min or {})
    an.check_type()
    return {f["ist"]: f["soll"] for f in an.findings if f["rule"] == "P4"}


fails = []


def check(name, ok):
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        fails.append(name)


# 1. Knaeuel 15/16 (< 1.25x) wird auf EINE Stufe zusammengelegt (16.5), nicht auseinandergerissen
snaps = analyzer([8, 13, 15, 16, 23, 31])
check("Knaeuel 15/16 verschmilzt nach oben auf 16.5", snaps.get(15) == 16.5 and snaps.get(16) == 16.5)
# 2. Keine Abwaerts-Kaskade: 13 liegt auf der Leiter und bleibt; 8 wird nicht auf die Stufe darunter gedrueckt
check("13 (auf der Leiter) bleibt unangetastet", 13 not in snaps)
check("8 wird nicht abwaerts gesnappt", snaps.get(8) is None or snaps[8] >= 8)
# 3. Echte Hierarchie (>= 1.25x), beide runden auf Stufe 1: die kleinere weicht nach unten wie bisher
snaps = analyzer([14.7, 18.5])
check("echte Stufe darf nach unten ausweichen", snaps.get(14.7) == 13 and snaps.get(18.5) == 16.5)
# 4. Boden aus gc_typo (Element 0 = 14.7 braucht mind. 14): Abwaerts-Snap auf 13 verboten,
#    dann weicht die groessere nach oben und die kleinere folgt aufwaerts auf die freie Stufe
snaps = analyzer([14.7, 18.5], typo_min={0: 14})
check("Boden verbietet Abwaerts-Snap, groessere weicht nach oben",
      snaps.get(14.7) == 16.5 and snaps.get(18.5) == 21)

print()
if fails:
    print(f"{len(fails)} von 5 Erwartungen verletzt"); sys.exit(1)
print("5/5 Erwartungen erfuellt")
