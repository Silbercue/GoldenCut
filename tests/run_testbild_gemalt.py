#!/usr/bin/env python3
"""Herz-und-Nieren-Pruefung am GEMALTEN Testbild: judge auf tests/testbild-gemalt.html — der M1-Pfad
(sichtbare Kante per Tintenprofil) muss die bekannten Asset-Einzuege (tests/assets/soll.json, dort mit
der M1-Methodik am Asset selbst gemessen) auf ±1 px treffen, Grain/Wash duerfen keine Falschtreffer
ausloesen, und die eingebauten Verstoesse W1/W2 (siehe Kommentar im Testbild) muessen gefunden werden.
Dazu laeuft einmal der run-Pfad (Warnungs-Logik, summary.json mit den fuenf Zahlen vorher/nachher).

Aufruf:  python3 tests/run_testbild_gemalt.py          (schreibt in einen Temp-Ordner, nie ins Repo)
Exit 0 = alle Erwartungen erfuellt.
"""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
TOL = 1.0   # px — Restfehler zwischen Alpha-Messung am Asset und Tintenprofil im Browser-Screenshot


def near(v, soll):
    return v is not None and soll is not None and abs(v - soll) <= TOL


def main():
    out = Path(tempfile.gettempdir()) / "goldencut" / f"testbild-gemalt-{time.strftime('%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, str(SKILL / "scripts" / "goldencut.py"), "judge",
                        str(HERE / "testbild-gemalt.html"), "--scope", ".tbg", "--out", str(out), "--force-out"],
                       text=True, capture_output=True)
    if r.returncode != 0:
        print(r.stdout); print(r.stderr, file=sys.stderr)
        print("FAIL: judge bricht ab"); return 1
    lay = json.loads((out / "layout.json").read_text(encoding="utf-8"))
    typo = json.loads((out / "typo.json").read_text(encoding="utf-8"))
    soll = json.loads((HERE / "assets" / "soll.json").read_text(encoding="utf-8"))
    sn = soll["frame-note.png"]["einzug_gemessen"]
    ss = soll["frame-stat.png"]["einzug_gemessen"]
    F = lay["findings"]

    results = []

    def check(name, ok):
        results.append((name, ok))
        print(("PASS  " if ok else "FAIL  ") + name)

    # painted-Eintraege den Kacheln zuordnen: Element-Indizes und tiles sind beide in DOM-Reihenfolge
    tiles = lay["tiles"]
    painted = [lay["painted"].get(k) for k in sorted(lay["painted"], key=int)]
    check("M1: alle 6 gemalten Kacheln messbar (kein „nicht messbar“)",
          len(tiles) == 6 and len(painted) == 6
          and not any(f["rule"] == "M1" and "nicht messbar" in f["note"] for f in F))
    if len(painted) != 6:
        painted = [None] * 6
    p_stat = painted[0:3]; p_note = painted[3:5]; p_wash = painted[5]

    # --- P1: Notiz-Kacheln — Einzug wie im Asset gemessen (±1 px), inkl. der asymmetrischen Seiten
    for nr, p in enumerate(p_note, 1):
        check(f"P1 M1 note {nr}: oben/unten {sn['top']}/{sn['bottom']} ±{TOL}",
              p is not None and near(p["top"], sn["top"]) and near(p["bottom"], sn["bottom"]))
        check(f"P1 M1 note {nr}: links/rechts {sn['left']}/{sn['right']} ±{TOL} (Wobble-Asymmetrie)",
              p is not None and near(p["left"], sn["left"]) and near(p["right"], sn["right"]))

    # --- P2: Stat-Kacheln — mittlere hat alle 4 Seiten, Rand-Kacheln sind zur Scope-Kante hin blind
    check(f"P2 M1 stat Mitte: alle 4 Seiten {ss['top']} ±{TOL}",
          p_stat[1] is not None and all(near(p_stat[1][s], ss[s]) for s in ("top", "bottom", "left", "right")))
    check("P2 M1 stat links/rechts: Scope-Rand-Seite nicht messbar (None), Rest trifft",
          p_stat[0] is not None and p_stat[2] is not None
          and p_stat[0]["left"] is None and p_stat[2]["right"] is None
          and all(near(p_stat[0][s], ss[s]) for s in ("top", "bottom", "right"))
          and all(near(p_stat[2][s], ss[s]) for s in ("top", "bottom", "left")))

    # --- P3: Wash-Kachel randlos — Kante = Box, und der Grain erzeugt keinen falschen Einzug
    check("P3 M1 wash: sichtbare Kante deckt sich mit der CSS-Box (alle Messwerte < 1)",
          p_wash is not None and all(v < 1 for v in p_wash.values() if v is not None)
          and any(f["rule"] == "M1" and "deckt sich" in f["note"] and "wash" in f["sel"] for f in F))

    # --- W1/W2: eingebaute Verstoesse muessen gefunden werden
    def has(rule, level, label_part="", prop_part=""):
        return any(f["rule"] == rule and f["level"] == level
                   and label_part.lower() in f["label"].lower()
                   and prop_part.lower() in f["prop"].lower() for f in F)

    check("W1 G1: note--w1 Polster links (verstoß)", has("G1", "verstoß", "Ablage", "Polster links"))
    check("W1 Gate: Ordnung gedeckelt (gate=true, Ordnung <= 50)",
          bool(lay["scores"].get("gate")) and lay["scores"]["ordnung"] is not None and lay["scores"]["ordnung"] <= 50)
    check("W2 C1: Kachelabstand 6 < Innenluecke (verstoß an jeder Stat-Kachel)",
          sum(1 for f in F if f["rule"] == "C1" and f["level"] == "verstoß" and "stat" in f["sel"]) == 3)

    # --- Korrekt gebaute Teile: keine Falschmeldungen
    check("Korrekt Typo: Lesbarkeit 100 (Grain-Hintergruende kippen keine Korridore)", typo["score"] == 100)
    check("Gruppen erkannt: Kacheln .stat (3) und Kacheln .note (2)",
          any(g["label"].startswith("Kacheln .stat (3)") for g in lay["groups"])
          and any(g["label"].startswith("Kacheln .note (2)") for g in lay["groups"]))
    g1_wrong = [f for f in F if f["rule"] == "G1" and f["level"] in ("knapp", "verstoß") and f["prop"] != "Konsistenz"
                and "note--w1" not in f["sel"]]
    check("Korrekt Geschwister: G1-Abweichungen nur an note--w1 (Stat-Kacheln identisch)", not g1_wrong)

    # Keine unerwarteten Element-Verstoesse ausserhalb der Whitelist (Scope-Kennzahlen ausgenommen)
    EXPECTED = [("G1", "note--w1"), ("G1", "Notiz"), ("C1", "stat")]
    SCOPE_RULES = {"C4", "C5", "B1", "B3", "E1", "E2", "E3", "E4"}
    unexpected = [f for f in F if f["level"] == "verstoß" and f["rule"] not in SCOPE_RULES
                  and not f["prop"].startswith("Ebenen")
                  and not any(f["rule"] == ru and (m in f["sel"] or m in f["label"]) for ru, m in EXPECTED)]
    for f in unexpected:
        print("   unerwartet:", f["rule"], f["label"], f["prop"])
    check("Keine unerwarteten Element-Verstöße außerhalb der Whitelist", not unexpected)

    # --- run-Pfad: Warnungs-Logik laeuft, fuenf Zahlen vorher/nachher in summary.json
    out2 = out.parent / (out.name + "-run")
    r2 = subprocess.run([sys.executable, str(SKILL / "scripts" / "goldencut.py"), "run",
                         str(HERE / "testbild-gemalt.html"), "--scope", ".tbg", "--title", "testbild-gemalt",
                         "--out", str(out2), "--force-out"], text=True, capture_output=True)
    summ = out2 / "summary.json"
    ok_run = r2.returncode == 0 and summ.exists()
    if ok_run:
        s = json.loads(summ.read_text(encoding="utf-8"))
        five = ("reihe", "lesbarkeit", "ordnung", "ruhe", "balance")
        ok_run = (all(k in s.get("before", {}) for k in five) and all(k in s.get("after", {}) for k in five)
                  and isinstance(s.get("warnings"), list))
    check("run: laeuft durch, summary.json mit den fuenf Zahlen vorher/nachher + warnings", ok_run)
    if not ok_run and r2.returncode != 0:
        print(r2.stdout[-2000:]); print(r2.stderr[-2000:], file=sys.stderr)

    n_fail = sum(1 for _, ok in results if not ok)
    print(f"\n{len(results) - n_fail}/{len(results)} Erwartungen erfuellt  ·  Report: {out / 'layout-report.md'}  ·  Overlay: {out / 'layout-overlay.png'}")
    if n_fail:
        print("painted:", json.dumps(lay["painted"]), "\nZahlen:", json.dumps(lay["scores"]), " Typo:", typo["score"])
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
