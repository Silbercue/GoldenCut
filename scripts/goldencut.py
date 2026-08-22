#!/usr/bin/env python3
"""goldencut — Einstieg: vermessen → pruefen → korrigieren → beweisen.

  goldencut.py run <url|datei> --scope CSS [--out DIR] [Mess-/Analyse-Optionen]
      --out weglassen = Temp-Ordner ($TMPDIR/goldencut/...). Nie in den Projekt-/OD-Ordner schreiben.
      Messung (before) → Analyse (report.md, patch.css) → Verify: Patch injizieren,
      neu messen (after) → Analyse nachher → Beweisbild proof.png.

  goldencut.py judge <url|datei> --scope CSS [--out DIR] [--distance MM] [Mess-Optionen]
      Schritt 1, nur URTEIL: Messung → Rollen → Lesbarkeits-Korridore → Hierarchie (gc_typo)
      → Ordnung & Aufteilung: Naehe-Ordnung, Ueberschrift, Polster↔Schrift, Rhythmus, Kanten,
      Stapel-Teilung, Kachelhoehen, optische Mitte, Balance (gc_layout).
      Schreibt typo-*.{md,json,png} + layout-*.{md,json,png}. Aendert nichts.

  goldencut.py layout <url|datei|before.json> [--scope CSS] [--out DIR]
      nur Ordnung & Aufteilung (Bauschritt 2), wahlweise auf einer vorhandenen Messung.

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
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEASURE_OPTS = {"--width": 1, "--height": 1, "--scale": 1, "--cdp": 1, "--wait": 1}
JUDGE_OPTS = {"--config": 1, "--distance": 1}
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
        elif a in ("--remove", "--force-out"):
            common[a] = True; i += 1
        elif a == "--distance":
            ana += [a, argv[i + 1]]; i += 2
        elif a in MEASURE_OPTS:
            meas += [a] + argv[i + 1:i + 1 + MEASURE_OPTS[a]]; i += 1 + MEASURE_OPTS[a]
        elif a in ANALYZE_OPTS:
            ana += [a] + argv[i + 1:i + 1 + ANALYZE_OPTS[a]]; i += 1 + ANALYZE_OPTS[a]
        elif a.startswith("--"):
            print(f"Unbekannte Option: {a}", file=sys.stderr); sys.exit(2)
        else:
            pos.append(a); i += 1
    return pos, common, meas, ana


def auto_config(target, ana):
    """Ohne --config: eine goldencut.config.json neben der Zieldatei suchen (und aufwaerts bis Home).
    So gelten projektweite Festlegungen — z. B. ein gemaltes Grundmass als Touch-Untergrenze —
    auch dann, wenn der Aufruf sie nicht ausdruecklich mitgibt."""
    if "--config" in ana or target.startswith("http"):
        return ana
    start = Path(target).resolve().parent if Path(target).exists() else Path.cwd()
    home = Path.home().resolve()
    for d in [start, *start.parents]:
        c = d / "goldencut.config.json"
        if c.is_file():
            print(f"   Config: {c}", flush=True)
            return ana + ["--config", str(c)]
        if d == home:
            break
    return ana


def resolve_out(common, target, cmd):
    """Arbeitsordner. Ohne --out: Temp-Ordner ausserhalb des Projekts (Messdaten sind Wegwerfware).
    Mit --out: darf NICHT neben der Zieldatei oder in einem OD-Projekt liegen — Open Design zeigt jede
    Datei dort als Artefakt, und Git nimmt sie mit."""
    if "--out" in common:
        out = Path(common["--out"]).resolve()
        tgt = Path(target)
        bad = "/.od/projects/" in str(out) + "/"
        if tgt.exists() and out.is_relative_to(tgt.resolve().parent):
            bad = True
        if bad and not common.get("--force-out"):
            print(f"--out {out} liegt im Design-/OD-Projektordner. Messdaten gehoeren nicht dorthin: "
                  f"--out weglassen (Temp) oder einen Ordner ausserhalb nehmen (--force-out erzwingt).", file=sys.stderr)
            sys.exit(2)
        return out
    slug = re.sub(r"[^a-z0-9]+", "-", Path(target).stem.lower() if not target.startswith("http") else re.sub(r"^https?://", "", target).lower()).strip("-")[:40]
    scope = re.sub(r"[^a-z0-9]+", "-", common.get("--scope", "").lower()).strip("-")[:30]
    out = Path(tempfile.gettempdir()) / "goldencut" / f"{slug}{'-' + scope if scope else ''}-{cmd}-{time.strftime('%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def sh(args):
    r = subprocess.run([sys.executable] + [str(a) for a in args], text=True, capture_output=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr, file=sys.stderr)
        sys.exit(r.returncode)
    return r.stdout.strip()


def five(out, suffix=""):
    """Die fuenf Zahlen eines Laufs aus den JSONs einsammeln: Reihen-Treue (gc_analyze), Lesbarkeit (gc_typo),
    Ordnung/Ruhe/Balance (gc_layout). Fehlende Teile bleiben None."""
    def load(name):
        f = out / f"{name}{suffix}.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    c, t, l = load("corrections"), load("typo"), load("layout")
    sc = (l or {}).get("scores") or {}
    return {"reihe": c["index"] if c else None, "lesbarkeit": t["score"] if t else None,
            "ordnung": sc.get("ordnung"), "ordnungRoh": sc.get("ordnungRoh"), "gate": sc.get("gate"),
            "ruhe": sc.get("ruhe"), "balance": sc.get("balance")}


def five_line(z, z2=None):
    """„Zahlen: Reihen-Treue 69 · Lesbarkeit 50 · Ordnung 32 · Ruhe 67 · Balance 84 %“ — immer GEMEINSAM, nie eine allein.
    Mit z2: vorher → nachher je Zahl."""
    def v(x):
        return "–" if x is None else str(x)
    def ordnung(zz):
        a = v(zz.get("ordnung"))
        if zz.get("gate"):
            a += f" (Gate, roh {v(zz.get('ordnungRoh'))})" if zz.get("ordnungRoh") != zz.get("ordnung") else " (Gate)"
        return a
    parts = []
    for key, name in (("reihe", "Reihen-Treue"), ("lesbarkeit", "Lesbarkeit"), ("ordnung", "Ordnung"), ("ruhe", "Ruhe"), ("balance", "Balance")):
        a = ordnung(z) if key == "ordnung" else v(z.get(key))
        if z2 is not None:
            b = ordnung(z2) if key == "ordnung" else v(z2.get(key))
            parts.append(f"{name} {a} → {b}")
        else:
            parts.append(f"{name} {a}")
    return "Zahlen: " + " · ".join(parts) + " %"


def cmd_run(argv):
    pos, common, meas, ana = split_opts(argv)
    if len(pos) != 1:
        print("run <url|datei> [--out DIR] [--scope CSS] ...", file=sys.stderr); return 2
    target = pos[0]; out = resolve_out(common, target, "run")
    ana = auto_config(target, ana)
    out.mkdir(parents=True, exist_ok=True)
    scope = ["--scope", common["--scope"]] if "--scope" in common else []

    print("1/4 Messung …", flush=True)
    print("   " + sh([HERE / "gc_measure.py", target, "--out", out, "--name", "before"] + scope + meas))
    print("2/4 Analyse …", flush=True)
    cfg_opts = [x for i, x in enumerate(ana) if x == "--config" or (i > 0 and ana[i - 1] == "--config")]
    judge_opts = [x for i, x in enumerate(ana) if x in JUDGE_OPTS or (i > 0 and ana[i - 1] in JUDGE_OPTS)]
    # Typo zuerst: die Rollen-Minima aus dem Typo-Urteil sind der Boden fuer Abwaerts-Snaps in der Analyse
    sh([HERE / "gc_typo.py", out / "before.json", "--out", out] + judge_opts)
    print("   " + sh([HERE / "gc_analyze.py", out / "before.json", "--out", out, "--typo", out / "typo.json"] + ana))
    before = json.loads((out / "corrections.json").read_text(encoding="utf-8"))
    # Die anderen vier Zahlen gehoeren dazu — die Reihen-Treue allein sagt nichts ueber Ordnung oder Gruppen
    sh([HERE / "gc_layout.py", out / "before.json", "--out", out] + cfg_opts)
    z_before = five(out)
    print("   " + five_line(z_before))
    n_patch = sum(1 for f in before["findings"] if f["action"] == "patch")
    if n_patch == 0:
        (out / "summary.json").write_text(json.dumps({"before": z_before, "after": None, "warnings": []}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("   Keine Korrekturen — Aufbau liegt schon auf der Zielreihe. Kein Verify noetig.")
        return 0
    print("3/4 Verify: Patch injizieren und neu messen …", flush=True)
    print("   " + sh([HERE / "gc_measure.py", target, "--out", out, "--name", "after",
                      "--inject", out / "patch.override.css"] + scope + meas))
    # Basis der Typo-Leiter aus der Vorher-Analyse festhalten, damit der Nachher-Vergleich dieselbe Reihe nutzt
    ana_after = ana + ([] if "--type-base" in ana else ["--type-base", before["typeBase"]])
    sh([HERE / "gc_typo.py", out / "after.json", "--out", out, "--suffix=-after"] + judge_opts)
    print("   " + sh([HERE / "gc_analyze.py", out / "after.json", "--out", out, "--suffix=-after", "--typo", out / "typo-after.json"] + ana_after))
    after = json.loads((out / "corrections-after.json").read_text(encoding="utf-8"))
    sh([HERE / "gc_layout.py", out / "after.json", "--out", out, "--suffix=-after"] + cfg_opts)
    z_after = five(out, "-after")
    print("4/4 Beweisbild …", flush=True)
    title = common.get("--title") or (common.get("--scope") or "goldencut")
    print("   " + sh([HERE / "gc_compose.py", out / "before.png", out / "after.png", out / "proof.png",
                      "--title", title, "--index-before", before["index"], "--index-after", after["index"],
                      "--zahlen", five_line(z_before, z_after)]))
    rest = [f for f in after["findings"] if f["action"] == "patch"]
    print(f"\nReihen-Treue (Harmonie-Index) {before['index']} % → {after['index']} %  ·  {n_patch} Korrekturen angewendet, {len(rest)} verbleiben"
          + (" (Reihenfolge-/Vererbungseffekte — siehe report-after.md)" if rest else ""))
    print(five_line(z_before, z_after))
    warn = []
    for key, name in (("ordnung", "Ordnung"), ("lesbarkeit", "Lesbarkeit"), ("ruhe", "Ruhe")):
        a, b = z_before.get(key), z_after.get(key)
        if a is not None and b is not None and b < a:
            warn.append(f"{name} {a} → {b}")
    if z_after.get("gate") and not z_before.get("gate"):
        warn.append("Geschwister-Gate neu ausgeloest")
    if warn:
        print("WARNUNG: der Patch verschlechtert " + ", ".join(warn) + " — die Reihe ist das Letzte, nicht das Erste. "
              "Patch NICHT blind uebernehmen: layout-report-after.md lesen, die verursachenden Korrekturen streichen (--protect) "
              "oder zuerst Gruppen/Luecken/Polster von Hand ordnen (Reihenfolge Schrift → Luecken → Polster → Kachel).")
    (out / "summary.json").write_text(json.dumps({"before": z_before, "after": z_after, "warnings": warn}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Report: {out / 'report.md'}  ·  Patch: {out / 'patch.css'}  ·  Beweis: {out / 'proof.png'}  ·  Layout nachher: {out / 'layout-report-after.md'}")
    return 0


def cmd_judge(argv):
    pos, common, meas, ana = split_opts(argv)
    if len(pos) != 1:
        print("judge <url|datei> [--out DIR] [--scope CSS] [--distance MM]", file=sys.stderr); return 2
    target = pos[0]; out = resolve_out(common, target, "judge")
    ana = auto_config(target, ana)
    out.mkdir(parents=True, exist_ok=True)
    scope = ["--scope", common["--scope"]] if "--scope" in common else []
    judge_opts = [x for i, x in enumerate(ana) if x in JUDGE_OPTS or (i > 0 and ana[i - 1] in JUDGE_OPTS)]
    print("1/4 Messung …", flush=True)
    print("   " + sh([HERE / "gc_measure.py", target, "--out", out, "--name", "before"] + scope + meas))
    print("2/4 Typo-Urteil …", flush=True)
    print(sh([HERE / "gc_typo.py", out / "before.json", "--out", out] + judge_opts))
    print("3/4 Ordnung & Aufteilung …")
    cfg_opts = [x for i, x in enumerate(ana) if x == "--config" or (i > 0 and ana[i - 1] == "--config")]
    print(sh([HERE / "gc_layout.py", out / "before.json", "--out", out] + cfg_opts))
    print("4/4 Reihen-Treue … (nur Urteil — report/patch.css im Ordner sind Ansichtsmaterial, nichts wird angewendet)")
    ana_only = [x for i, x in enumerate(ana) if x != "--distance" and not (i > 0 and ana[i - 1] == "--distance")]
    sh([HERE / "gc_analyze.py", out / "before.json", "--out", out, "--typo", out / "typo.json"] + ana_only)
    z = five(out)
    print(five_line(z))
    (out / "summary.json").write_text(json.dumps({"before": z, "after": None, "warnings": []}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def cmd_layout(argv):
    """Nur Ordnung & Aufteilung (Bauschritt 2) auf einer vorhandenen Messung oder einem Ziel."""
    pos, common, meas, ana = split_opts(argv)
    if len(pos) != 1:
        print("layout <url|datei|before.json> [--out DIR] [--scope CSS] [--config …]", file=sys.stderr); return 2
    target = pos[0]
    cfg_opts = [x for i, x in enumerate(ana) if x == "--config" or (i > 0 and ana[i - 1] == "--config")]
    if target.endswith(".json"):
        out = Path(common["--out"]) if "--out" in common else Path(target).parent
        print(sh([HERE / "gc_layout.py", target, "--out", out] + cfg_opts)); return 0
    out = resolve_out(common, target, "layout")
    scope = ["--scope", common["--scope"]] if "--scope" in common else []
    print("1/2 Messung …")
    print("   " + sh([HERE / "gc_measure.py", target, "--out", out, "--name", "before"] + scope + meas))
    print("2/2 Ordnung & Aufteilung …")
    print(sh([HERE / "gc_layout.py", out / "before.json", "--out", out] + cfg_opts))
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
    if cmd == "judge":
        return cmd_judge(rest)
    if cmd == "layout":
        return cmd_layout(rest)
    if cmd == "measure":
        return subprocess.call([sys.executable, str(HERE / "gc_measure.py")] + rest)
    if cmd == "analyze":
        return subprocess.call([sys.executable, str(HERE / "gc_analyze.py")] + rest)
    if cmd == "apply":
        return cmd_apply(rest)
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
