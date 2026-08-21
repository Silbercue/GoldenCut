# GoldenCut

Claude-Code-Skill, der einen UI-Aufbau im Browser vermisst und nach dem Goldenen Schnitt in optische Harmonie
ueberfuehrt: Abstaende, Raender, Schriftgroessen, Zeilenhoehen, Icon-Groessen und Radien werden gegen eine
Phi-Zielreihe geprueft und als konkrete Korrekturwerte (patch.css) mit Vorher/Nachher-Beweisbild geliefert.

Kein Kritik-Tool. Es sagt nicht „wirkt unruhig", es sagt „padding-top 7 → 8, gap 12 → 13, h1 26 → 29".

## Schnellstart

```bash
python3 scripts/goldencut.py run datei.html --scope ".meine-kachel" --out /tmp/gc --title "Kachel"
# → /tmp/gc/report.md, patch.css, proof.png   (Index vorher → nachher)
python3 scripts/goldencut.py apply --html datei.html --patch /tmp/gc/patch.css   # statische HTML
```

Voraussetzungen: Python 3 mit `playwright` (+ `playwright install chromium`), `Pillow`, `numpy`.

## Als Skill einbinden

```bash
ln -s "$(pwd)" ~/.claude/skills/goldencut
```

Die `SKILL.md` im Repo-Root ist die Skill-Definition (Trigger: „goldener schnitt", „harmonisieren", „beruhigen", „goldencut" …).

## Aufbau

| Pfad | Inhalt |
|---|---|
| `SKILL.md` | Skill-Definition: Ablauf, Defaults, Pruefungen, Fallen |
| `scripts/goldencut.py` | Einstieg: `run` · `measure` · `analyze` · `apply` |
| `scripts/gc_measure.py` | DOM-Messung (Playwright): computed styles, Boxen, Icons, Screenshot |
| `scripts/gc_analyze.py` | Regelwerk → Korrekturen, Report, Patch, Harmonie-Index |
| `scripts/gc_compose.py` | Beweisbild vorher · nachher · Differenz |
| `goldencut.config.example.json` | Vorlage fuer eine projektweite Zielreihe |
| `reference/`, `examples/` | lokal, nicht im Repo: Regelwerk mit Quellen, Referenzlaeufe |

## Zielreihe (Default)

- Schrift und Icons: √φ = 1,272 ab der haeufigsten Textgroesse (z. B. 14 → 11 · 14 · 18 · 22,5 · 29 · 36,5)
- Abstaende und Radien: φ ab 8 und 16, verschraenkt: 2 · 3 · 4 · 5 · 6 · 8 · 10 · 13 · 16 · 21 · 26 · 34 · 42 · 55 · 68 · 89
- Toleranzen eng (±5 % Reihe, ±3 % Verhaeltnis), damit nicht alles „golden" ist (Bias-Guard)
- Raender: links = rechts, unten ≥ oben — nur an sichtbaren Boxen; absichtliche Asymmetrie (Platz fuer Deko) wird erkannt und nur gemeldet

Warum so und nicht anders — Kurzfassung der Recherche: Phi ist als Konsistenzsystem brauchbar, als
Schoenheitsgesetz nicht belegt (Fechner 1876, Green 1995, Markowsky 1992, NN/G 2021); der Wert liegt darin,
**eine** Reihe durchzuhalten. Kein grosses Design-System nutzt Fibonacci-Abstaende; Material, Carbon und Atlassian
arbeiten mit 4/8-px-Rastern — eine Phi-Reihe ist eine bewusste Entscheidung, keine Best Practice.
Typo-Leiter nach Tim Browns Modular Scale, Zeilenlaenge nach Bringhurst, Rand-Kanon nach Tschichold/Van de Graaf.

## Referenzlauf

Vokabel-Hub einer Lern-App (iPhone-Viewport): Harmonie-Index 55 % → 89 %, 29 Korrekturen, 0 verbleibend, Layout
intakt. Eine von Hand nach Phi gebaute Variante derselben Seite kam ohne Schrift-Korrektur durch — die automatisch
erkannte Typo-Basis (13,75 · √φ) entsprach der handgebauten Leiter.

## Lizenz

MIT — siehe [LICENSE](LICENSE). © 2026 Julian Friedrich
