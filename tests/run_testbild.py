#!/usr/bin/env python3
"""Herz-und-Nieren-Pruefung: judge auf tests/testbild.html — jeder eingebaute Verstoss (V1–V7, siehe
Kommentar im Testbild) muss gefunden werden, und auf den korrekt gebauten Teilen (.note, .pill--a/--b,
Stat-Kacheln 2+3, Typo) darf kein Verstoss gemeldet werden.

Aufruf:  python3 tests/run_testbild.py          (schreibt in einen Temp-Ordner, nie ins Repo)
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


def main():
    out = Path(tempfile.gettempdir()) / "goldencut" / f"testbild-{time.strftime('%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, str(SKILL / "scripts" / "goldencut.py"), "judge",
                        str(HERE / "testbild.html"), "--scope", ".tb", "--out", str(out), "--force-out"],
                       text=True, capture_output=True)
    if r.returncode != 0:
        print(r.stdout); print(r.stderr, file=sys.stderr)
        print("FAIL: judge bricht ab"); return 1
    lay = json.loads((out / "layout.json").read_text(encoding="utf-8"))
    typo = json.loads((out / "typo.json").read_text(encoding="utf-8"))
    F = lay["findings"]

    def has(rule, level, label_part="", prop_part=""):
        return any(f["rule"] == rule and f["level"] == level
                   and label_part.lower() in f["label"].lower()
                   and prop_part.lower() in f["prop"].lower() for f in F)

    results = []

    def check(name, ok):
        results.append((name, ok))
        print(("PASS  " if ok else "FAIL  ") + name)

    # --- Die eingebauten Verstoesse muessen gefunden werden
    check("V1 G1: Stat-Kachel 1 hat andere Innenluecke als die Geschwister (verstoß)",
          has("G1", "verstoß", "stat", "Lücke") or has("G1", "verstoß", "stat", "Polster unten"))
    check("V2 G1: Pille Gamma hat anderes Polster links (verstoß)",
          has("G1", "verstoß", "pill", "Polster links"))
    check("V1/V2 Gate: Ordnung gedeckelt (gate=true, Ordnung <= 50)",
          bool(lay["scores"].get("gate")) and lay["scores"]["ordnung"] is not None and lay["scores"]["ordnung"] <= 50)
    check("V3 C1: Kachelabstand kleiner als Innenluecke (verstoß an Stat-Kachel)",
          has("C1", "verstoß", "stat"))
    check("V4 C8: Titel „Karten“ zu weit vom Text (verstoß Titel→Text)",
          has("C8", "verstoß", "Karten", "Titel→Text"))
    check("V5 C8: Status klebt am Text (verstoß Text→Block)",
          any(f["rule"] == "C8" and f["level"] == "verstoß" and f["prop"].startswith("Text→") for f in F))
    check("V6 C9: Balken unten 2 statt 8 (verstoß Grafik-Rand)",
          has("C9", "verstoß", "", "Balken-Rand"))
    check("V6 C3: engste Stelle der Balken-Kachel unter x-Hoehe (verstoß)",
          any(f["rule"] == "C3" and f["level"] == "verstoß" and "Phasen" in f["label"] for f in F))
    check("V7 G3: Ueberschriften-Stellung links ungleich (verstoß)",
          has("G3", "verstoß", "", "Stellung links"))
    check("V7 G2: Polaritaets-Hinweis (hell auf dunkel) vorhanden",
          any(f["rule"] == "G2" for f in F))

    # --- Keine Falschmeldungen auf den korrekt gebauten Teilen
    bad_note = [f for f in F if f["level"] == "verstoß" and ("note" in f["sel"] or "Notiz" in f["label"] or "Ablage" in f["label"])]
    check("Korrekt .note: kein Verstoss auf den Notiz-Kacheln", not bad_note)
    # G1-Einzelabweichungen duerfen NUR an den praeparierten Mitgliedern haengen (exakt per Selektor adressiert)
    g1_wrong = [f for f in F if f["rule"] == "G1" and f["level"] in ("knapp", "verstoß") and f["prop"] != "Konsistenz"
                and "stat--v1" not in f["sel"] and "pill--v2" not in f["sel"]]
    check("Korrekt Geschwister: G1-Abweichungen nur an stat--v1 und pill--v2", not g1_wrong)
    check("Korrekt Typo: Lesbarkeit 100 (alle Korridore erfuellt)", typo["score"] == 100)
    groups = {g["label"]: g for g in lay["groups"]}
    check("Gruppen erkannt: Kacheln .stat (3), Chips .pill (3), Ueberschriften (2), Kacheln .note (2)",
          len([g for g in groups if g.startswith("Kacheln .stat")]) == 1
          and len([g for g in groups if g.startswith("Chips .pill")]) == 1
          and len([g for g in groups if g.startswith("Überschriften")]) == 1
          and len([g for g in groups if g.startswith("Kacheln .note")]) == 1)
    note_group = next((g for g in lay["groups"] if g["label"].startswith("Kacheln .note")), None)
    check("Korrekt .note-Gruppe: keine Abweichungen", note_group is not None and not note_group["issues"])

    # Keine UNERWARTETEN Element-Verstoesse: jede rote Meldung muss zu einem der eingebauten Fehler gehoeren.
    # (Scope-Urteile C4/B1/B3/E sind Kennzahlen des Gesamtstapels, keine Element-Falschmeldungen.)
    EXPECTED = [("G1", "stat--v1"), ("G1", "pill--v2"), ("G3", "Karten"), ("C8", "Karten"), ("C8", "desc"),
                ("C1", "stat"), ("C1", "cardtile"), ("C9", "bartile"), ("C3", "bartile"), ("C2", "Karten")]
    SCOPE_RULES = {"C4", "C5", "B1", "B3", "E1", "E2", "E3", "E4"}
    unexpected = [f for f in F if f["level"] == "verstoß" and f["prop"] != "Konsistenz" and f["rule"] not in SCOPE_RULES
                  and not f["prop"].startswith("Ebenen")   # C1-Ebenen = Scope-Zusammenfassung der Einzel-C1
                  and not any(f["rule"] == r and (m in f["sel"] or m in f["label"]) for r, m in EXPECTED)]
    for f in unexpected:
        print("   unerwartet:", f["rule"], f["label"], f["prop"])
    check("Keine unerwarteten Element-Verstöße außerhalb der Whitelist", not unexpected)

    n_fail = sum(1 for _, ok in results if not ok)
    print(f"\n{len(results) - n_fail}/{len(results)} Erwartungen erfuellt  ·  Report: {out / 'layout-report.md'}  ·  Overlay: {out / 'layout-overlay.png'}")
    if n_fail:
        print("Zahlen:", json.dumps(lay["scores"]), " Typo:", typo["score"])
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
