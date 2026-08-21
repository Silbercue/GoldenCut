---
name: goldencut
description: Vermisst einen UI-Aufbau (URL, HTML-Datei, laufende App) im echten Browser und ueberfuehrt ihn nach dem Goldenen Schnitt in optische Harmonie — Abstaende, Raender, Schriftgroessen, Zeilenhoehen, Icon-Groessen und Radien werden gegen EINE Phi-Zielreihe geprueft (√φ-Typo-Leiter, φ-Abstandsreihe) und als KONKRETE Korrekturwerte (patch.css) mit Vorher/Nachher-Beweisbild geliefert. Keine Kritik, sondern Transformation. Aktiviere bei "goldener schnitt", "golden ratio", "goldencut", "phi", "harmonisieren", "harmonisch machen", "beruhigen", "ui beruhigen", "ausgleichen", "abstaende angleichen", "raender pruefen", "abstand zum rand", "schriftgroessen auf eine leiter", "typo-leiter", "icons angleichen", "proportionen pruefen", "kachel harmonisieren", "layout aufraeumen", "optisch ruhiger", "fibonacci abstaende", "modular scale".
---

# goldencut — UI nach dem Goldenen Schnitt beruhigen

Der Skill vermisst einen Aufbau im Browser, prueft jedes Mass gegen eine Phi-Zielreihe und liefert
die korrigierten Werte. Er **kritisiert nicht**, er **ueberfuehrt**: Ist → Soll, als CSS, mit Beweisbild.

## Grundsaetze

1. **Eine Zielreihe, alles darauf.** Harmonisch ist ein Aufbau, wenn Abstaende, Schriftgroessen, Icons und Radien
   auf derselben Reihe liegen — nicht, wenn einzelne Verhaeltnisse zufaellig 1,6 ergeben (Bias-Guard, enge Toleranz).
2. **Nur Masse bestehender Elemente aendern.** Keine neuen Elemente, kein Text, keine Umordnung.
   Teilungen (62/38), Formate und Innen:Aussen-Verstoesse stehen als Hinweis mit konkreten Zahlen — das sind
   Produktentscheidungen, die der User trifft.
3. **Phi ist Konsistenzsystem, kein Schoenheitsgesetz.** Die Wahrnehmungsforschung seit Fechner findet bestenfalls
   eine schwache, fragile Vorliebe fuer Rechtecke im Bereich 1,4–1,8, keine Spitze bei 1,618; fuer UI-Layouts gibt
   es keine Studie. Der Harmonie-Index misst Konsistenz, nicht Schoenheit — so auch kommunizieren.
   (Ausfuehrliches Regelwerk mit Quellen: `reference/regeln.md`, lokal, nicht Teil des Repos.)
4. **Browser ist die Wahrheit.** Gemessen werden computed styles, nicht Quellcode, Tailwind-Klassen oder Tokens.

## Ablauf

```bash
SKILL=~/.claude/skills/goldencut
python3 $SKILL/scripts/goldencut.py run <url|datei.html> --scope "<css-selektor>" --out <ordner> --title "<name>"
```

1. **Scope und Viewport bestimmen.** Scope = der Aufbau, um den es geht (Kachel, Screen, Karte), als eindeutiger
   Selektor. Bei Dateien mit mehreren Varianten exakt eine treffen (z. B. `.v2src:not(.v3src)`).
   Viewport-Default 390×844 (iPhone); iPad quer `--width 1194 --height 834`; Desktop `--width 1440 --height 900`.
   Laufende App hinter Login: `--cdp http://127.0.0.1:9222` (dockt an das offene Chrome an).
2. **`run` ausfuehren.** Macht vier Schritte: Messung (before.json/png) → Analyse (report.md, patch.css,
   patch.override.css, corrections.json) → Verify (Patch injiziert, neu gemessen, report-after.md) → proof.png
   (vorher | nachher | Differenz).
3. **proof.png ansehen — Pflicht.** Pruefen, ob Umbrueche, Ueberlaeufe oder verschobene Deko entstanden sind.
   Wenn ja: betroffene Korrektur in patch.css streichen oder Wert schuetzen (`--protect`), erneut `run`.
4. **Anwenden.**
   - Statische HTML-Datei (OD-Sheet, Prototyp): `goldencut.py apply --html <datei> --patch <out>/patch.css`
     fuegt `<style id="goldencut-patch">` ein; `--remove` nimmt ihn wieder raus. Besser: Werte direkt in den
     CSS-Block der Variante uebernehmen.
   - App/Framework: Werte aus patch.css in Tokens/Quelle uebertragen (em/rem umrechnen: Soll-px ÷ Basis).
     Danach `run` erneut gegen die App als Nachweis.
5. **Berichten (kurz).** Index vorher → nachher, die drei bis fuenf wichtigsten Korrekturen in Worten
   („Stat-Kacheln: Padding oben 7 → 8, Abstand 12 → 13, Ziffer-Margin 11 → 10"). Bild mitsenden. Keine Tabellenwaende.
   **Fragen an den User menschlich stellen, nicht technisch** (User-Feedback 2026-08-21): Was sieht man, was
   aendert sich, was ist der Haken — in Alltagssprache, kurz und auf den Punkt. Also nicht „Punkte 9,2 → 8,5
   uebernehmen, Balken-Padding wegen BG6-Abgleich schuetzen?", sondern „Die Punkte werden ein Hauch kleiner und
   der Kopf rechts etwas enger — das passt. Die Balkenraender lasse ich, die kommen aus der gemalten Vorlage.
   Einverstanden?" Zahlen nur, wenn sie fuer die Entscheidung noetig sind; Regelnummern, Selektoren und
   Eigenschaftsnamen gehoeren in den Report, nicht in die Frage.

## Zielreihe und Defaults

| Was | Default | Herleitung |
|---|---|---|
| Typo-Leiter | Ratio √φ = 1,272, Basis = haeufigste Textgroesse (auto) | R7: φ ist fuer Mobile zu grob, √φ liefert jede zweite Stufe exakt φ |
| Abstandsreihe | Ratio φ ab 8 **und** 16 (zwei verschraenkte Reihen): 2 3 4 5 6 8 10 13 16 21 26 34 42 55 68 89 | R9/R11: Modulor-Prinzip, dicht genug fuer UI |
| Icons | Groesse = Nachbartext · √φⁿ (n ganzzahlig), z. B. 14 → 11 / 14 / 18 / 22,5 | R10 |
| Zeilenhoehe | Text 1,2–1,62, Titel 1,0–1,25 | R8: φ nur als Obergrenze |
| Raender | links = rechts; unten ≥ oben; `--canon`: unten = oben·φ | R5/R6 — nur an sichtbaren Boxen |
| Toleranzen | Reihe ±5 %, Skala \|Δn\| ≤ 0,1, Verhaeltnis ±3 % | §6, Markowsky ±2 % |
| Schutz | 44 (Touch-Target), 24 (Standard-Icon) — nur fuer Icon-Groessen | offene Frage 3 aus regeln.md |

Optionen: `--type-ratio 1.618` (reine φ-Leiter), `--type-base 16`, `--spacing-bases 4` oder `8`, `--grid 4`
(Reihe auf 4-px-Raster gerundet: 8 12 20 32 56 88 — Kompromiss aus R9), `--canon`, `--fix-all` (auch
Innen:Aussen patchen), `--protect none`, `--config goldencut.config.json` (projektweite Festlegung,
Vorlage: `goldencut.config.example.json`).

Wenn das Projekt schon eine Reihe hat (Tokens, Design-System), diese als Config eintragen statt die
Defaults zu nehmen — zwei Systeme mischen ist der groesste Fehler (§5.0).

## Was geprueft wird

| # | Pruefung | Aktion |
|---|---|---|
| P7 | Padding, Margin, Gap, Radius auf der Abstandsreihe | patch |
| P9 | Rand-Symmetrie links = rechts, unten ≥ oben (sichtbare Boxen) | patch; bei Pseudo-Element/absolutem Kind nur Hinweis (Platz fuer Deko) |
| P9 | Aussenrand des Scopes zum Viewport | Hinweis |
| P4 | Schriftgroessen auf der Typo-Leiter, Hierarchiestufen bleiben erhalten | patch |
| P5 | Zeilenhoehe im Korridor | patch |
| P6 | Zeilenlaenge 45–75 Zeichen | Hinweis (max-width-Vorschlag) |
| R10 | Icon-Groesse relativ zum Nachbartext | patch (ausser geschuetzt) |
| P8 | Innen (gap) < Aussen (padding / Eltern-gap), Soll aussen = innen·φ | Hinweis, `--fix-all` patcht |
| P1 | Zweiteilungen nahe φ | Hinweis mit Soll-Massen; „schon auf φ" nur bei ≤ 3 % |
| P2 | Formate grosser Flaechen (1:1, 4:3, 3:2, √2, φ, 16:9) | Hinweis |

## Fallen

- **Selektoren sind Messpfade**, keine Quell-Selektoren. In der Quelle den passenden Token/Block aendern.
- **em/rem-Werte** erscheinen als krumme px (13,75 / 8,3). Der Patch setzt px; in der Quelle die Einheit behalten und umrechnen.
- **Absichtliche Asymmetrie** (Pille mit Flagge, Button mit Illustration) erkennt der Skill an Pseudo-Elementen oder
  absoluten Kindern und meldet sie nur. Ohne diese Marker wird symmetrisiert — proof.png pruefen.
- **Responsive:** Phi haelt nur am gemessenen Breakpoint (Twitter-2010-Grenze). Pro Breakpoint ein `run`.
- **Nur DOM.** Reine Screenshots/Bilder ohne DOM werden nicht vermessen — dafuer fehlen Schriftgroessen und Boxen.
- **Fonts:** Webfonts brauchen Netz; lokale Dateien mit `@font-face` funktionieren. Abweichende Fallback-Schrift
  veraendert Breiten, nicht die gemessenen CSS-Werte.
- Der Nachher-Lauf nutzt dieselbe Typo-Basis wie der Vorher-Lauf (wird automatisch uebergeben).

## Dateien

- `scripts/goldencut.py` — Einstieg (`run`, `measure`, `analyze`, `apply`)
- `scripts/gc_measure.py` — DOM-Messung via Playwright (computed styles, Boxen, Icon-Erkennung, Screenshot)
- `scripts/gc_analyze.py` — Regelwerk → Korrekturen, Report, Patch, Harmonie-Index
- `scripts/gc_compose.py` — Beweisbild vorher | nachher | Differenz
- `goldencut.config.example.json` — Vorlage fuer eine projektweite Zielreihe
- `reference/`, `examples/` — lokal (gitignored): Regelwerk mit Quellen (R1–R13, K1–K5, Prueftabelle P1–P12) und Referenzlaeufe

Voraussetzungen: `python3` mit `playwright` (Chromium installiert), `Pillow`, `numpy`.
