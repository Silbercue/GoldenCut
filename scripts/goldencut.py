#!/usr/bin/env python3
"""goldencut — Einstieg: vermessen → pruefen → korrigieren → beweisen.

  goldencut.py run <url|datei> --scope CSS --out DIR [Mess-/Analyse-Optionen]
      Messung (before) → Analyse (report.md, patch.css) → Verify: Patch injizieren,
      neu messen (after) → Analyse nachher → Beweisbild proof.png.

  goldencut.py measure ...   nur gc_measure
  goldencut.py analyze ...   nur gc_analyze
  goldencut.py apply --html DATEI --patch patch.css [--remove]
      schreibt den Patch als <style id="goldencut-patch"> in eine statische HTML-Datei
      (OD-Sheets, Prototypen). Fuer Apps: Werte aus patch.css in die Quelle/Tokens uebernehmen.

Alle unbekannten Optionen werden an gc_measure (Viewport, --cdp, --wait, --scale)
bzw. gc_analyze (--type-ratio, --spacing-bases, --grid, --protect, --canon, --fix-all, --config) durchgereicht.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEASURE_OPTS = {"--width": 1, "--height": 1, "--scale": 1, "--cdp": 1, "--wait": 1}
ANALYZE_OPTS = {"--config": 1, "--type-base": 1, "--type-ratio": 1, "--spacing-bases": 1, "--spacing-ratio": 1,
                "--grid": 1, "--protect": 1, "--canon": 0, "--fix-all": 0}
STYLE_ID = "goldencut-patch"


def split_opts(argv):
    """Trennt Positional, --scope/--out/--title und die Passthrough-Optionen."""
    pos, common, meas, ana = [], {}, [], []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--scope", "--out", "--title", "--html", "--patch"):
            common[a] = argv[i + 1]; i += 2
        elif a == "--remove":
            common[a] = True; i += 1
        elif a in MEASURE_OPTS:
            meas += [a] + argv[i + 1:i + 1 + MEASURE_OPTS[a]]; i += 1 + MEASURE_OPTS[a]
        elif a in ANALYZE_OPTS:
            ana += [a] + argv[i + 1:i + 1 + ANALYZE_OPTS[a]]; i += 1 + ANALYZE_OPTS[a]
        elif a.startswith("--"):
            print(f"Unbekannte Option: {a}", file=sys.stderr); sys.exit(2)
        else:
            pos.append(a); i += 1
    return pos, common, meas, ana


def sh(args):
    r = subprocess.run([sys.executable] + [str(a) for a in args], text=True, capture_output=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr, file=sys.stderr)
        sys.exit(r.returncode)
    return r.stdout.strip()


def cmd_run(argv):
    pos, common, meas, ana = split_opts(argv)
    if len(pos) != 1 or "--out" not in common:
        print("run <url|datei> --out DIR [--scope CSS] ...", file=sys.stderr); return 2
    target, out = pos[0], Path(common["--out"])
    out.mkdir(parents=True, exist_ok=True)
    scope = ["--scope", common["--scope"]] if "--scope" in common else []

    print("1/4 Messung …", flush=True)
    print("   " + sh([HERE / "gc_measure.py", target, "--out", out, "--name", "before"] + scope + meas))
    print("2/4 Analyse …", flush=True)
    print("   " + sh([HERE / "gc_analyze.py", out / "before.json", "--out", out] + ana))
    before = json.loads((out / "corrections.json").read_text(encoding="utf-8"))
    n_patch = sum(1 for f in before["findings"] if f["action"] == "patch")
    if n_patch == 0:
        print("   Keine Korrekturen — Aufbau liegt schon auf der Zielreihe. Kein Verify noetig.")
        return 0
    print("3/4 Verify: Patch injizieren und neu messen …", flush=True)
    print("   " + sh([HERE / "gc_measure.py", target, "--out", out, "--name", "after",
                      "--inject", out / "patch.override.css"] + scope + meas))
    # Basis der Typo-Leiter aus der Vorher-Analyse festhalten, damit der Nachher-Vergleich dieselbe Reihe nutzt
    ana_after = ana + ([] if "--type-base" in ana else ["--type-base", before["typeBase"]])
    print("   " + sh([HERE / "gc_analyze.py", out / "after.json", "--out", out, "--suffix=-after"] + ana_after))
    after = json.loads((out / "corrections-after.json").read_text(encoding="utf-8"))
    print("4/4 Beweisbild …", flush=True)
    title = common.get("--title") or (common.get("--scope") or "goldencut")
    print("   " + sh([HERE / "gc_compose.py", out / "before.png", out / "after.png", out / "proof.png",
                      "--title", title, "--index-before", before["index"], "--index-after", after["index"]]))
    rest = [f for f in after["findings"] if f["action"] == "patch"]
    print(f"\nHarmonie-Index {before['index']} % → {after['index']} %  ·  {n_patch} Korrekturen angewendet, {len(rest)} verbleiben"
          + (" (Reihenfolge-/Vererbungseffekte — siehe report-after.md)" if rest else ""))
    print(f"Report: {out / 'report.md'}  ·  Patch: {out / 'patch.css'}  ·  Beweis: {out / 'proof.png'}")
    return 0


def cmd_apply(argv):
    _, common, _, _ = split_opts(argv)
    html = Path(common.get("--html", ""))
    if not html.exists():
        print("apply --html DATEI --patch patch.css [--remove]", file=sys.stderr); return 2
    text = html.read_text(encoding="utf-8")
    # Einfuegen und Entfernen sind exakt invers: Block direkt vor </head>, ohne zusaetzliche Leerzeilen
    block_rx = re.compile(rf'<style id="{STYLE_ID}">.*?</style>\n', re.S)
    text = block_rx.sub("", text)
    if not common.get("--remove"):
        patch = Path(common["--patch"])
        override = patch.with_name(patch.stem + ".override.css")
        if patch.name == "patch.css" and override.exists():
            patch = override  # !important noetig, damit spezifischere Quellregeln den Patch nicht schlagen
        css = patch.read_text(encoding="utf-8")
        block = f'<style id="{STYLE_ID}">\n{css}</style>\n'
        if "</head>" in text:
            text = text.replace("</head>", block + "</head>", 1)
        else:
            text = block + text
    html.write_text(text, encoding="utf-8")
    print(("entfernt: " if common.get("--remove") else "eingefuegt: ") + f'<style id="{STYLE_ID}"> in {html}')
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); return 0
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "run":
        return cmd_run(rest)
    if cmd == "measure":
        return subprocess.call([sys.executable, str(HERE / "gc_measure.py")] + rest)
    if cmd == "analyze":
        return subprocess.call([sys.executable, str(HERE / "gc_analyze.py")] + rest)
    if cmd == "apply":
        return cmd_apply(rest)
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
