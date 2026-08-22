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
5. **Der Skill urteilt nach Vorgaben und Mathematik — nie danach, was sich „aendern laesst".** (User-Grundsatz
   2026-08-21.) Ob ein Mass gemalt, hartkodiert, aus einer Vorlage abgeglichen oder von einem anderen Mass
   vorausgesetzt ist, spielt fuer das Urteil keine Rolle: Soll ist Soll. Die Entscheidung, ob einer Empfehlung
   gefolgt wird, trifft der User (bzw. das LLM, das die Gegebenheiten kennt) — **und zwar sichtbar**. Pflicht fuer
   das anwendende LLM: Jede Empfehlung, die es nicht umsetzt, dem User nennen, nach dem Motto
   „Eigentlich sollte X von A auf B, nach dem Goldenen Schnitt — geht nicht / lasse ich, weil es gemalt /
   hartkodiert / vorausgesetzt ist. Willst du es trotzdem?" Nie eine Empfehlung still fallen lassen, nie als
   „nicht verhandelbar" deklarieren, nie „gemalt" mit „unveraenderbar" verwechseln (9-Slice-Rahmen strecken,
   Schriften skalieren, Radien sind CSS — fest sind meist nur Rahmenecken und Abnahme-Entscheidungen).
6. **Zugehoerigkeit vor Reihe.** (Prinzip aus der Versagensanalyse des Probedurchlaufs, 2026-08-22.) Das Urteil
   arbeitet in dieser Reihenfolge: Zugehoerigkeit erkennen (gleiche Klasse/Rolle/Reihe → Gruppe) → **Konsistenz
   innerhalb der Gruppe als hartes Gate** (Geschwister haben identische Innenmasse; ein Verstoss deckelt die
   Ordnung bei 50 %) → Ordnung zwischen den Gruppen → erst zuletzt die Reihe. Beim Anwenden gilt dieselbe
   Ordnung als Werk-Reihenfolge: **Schrift → Luecken → Polster → Kachel** — Kachelmasse zuletzt, sonst verschiebt
   der Snap das Innenleben (genau so entstand im Probedurchlauf das um 3 px versetzte Label). `run` prueft das:
   verschlechtert der Patch die Ordnung, warnt er und der Patch wird nicht blind uebernommen.

## Ablauf

**Schritt 1 — erst urteilen (`judge`), dann korrigieren (`run`).** `judge` aendert nichts. Es urteilt in zwei Teilen:
**(a) Typo** — misst die echten Schriftmetriken (x-Hoehe, Versalhoehe, Stamm per Canvas), weist jedem Text eine Leseart
zu (Kennzahl, Titel, Zwischentitel, Lesetext, Nebentext, Label, Button-Text) und prueft Lesbarkeit und Hierarchie;
**(b) Ordnung & Aufteilung** (Bauschritt 2, `gc_layout.py`) — prueft ZUERST die Zugehoerigkeit (Grundsatz 6):
Geschwister gleicher Klasse in Reihe/Elternteil muessen identische Innenmasse haben (G1, hartes Gate — ein Verstoss
deckelt Ordnung bei 50 %), Ueberschriften gleicher Rolle sitzen in jeder Kachel gleich (G3), hell-auf-dunkel wirkt
groesser/fetter (G2, Hinweis). Dann die Beziehungen ZWISCHEN den Elementen: Naehe-Ordnung (innen < aussen je Ebene,
Soll eine φ-Stufe), Ueberschrift gehoert zum Folgenden (C2 oben = unten·φ…φ²; **C8 in der Kachel: Titel→Text ≤
Zeile→Zeile ≤ Text→naechster Block**, Soll Zeile/φ bzw. Zeile·φ), Polster an die Schrift gebunden (≥ x-Hoehe,
≈ Versalhoehe des groessten Texts — Grafik wie Balken/Icons eingeschlossen), Grafik am Kachelrand links = rechts =
unten (C9), konzentrische Radien, Chip-Hoehe als φ-Stufe der naechstgelegenen Kachel (B8, weich), gemalte Kante aus dem
Screenshot (M1, Hinweis: sichtbare Kante vs CSS-Box), Rhythmus, Ausrichtungskanten, Randkanon (unten ≥ oben; entfaellt bei
Kachel-mit-Endbalken zugunsten C9), Hauptteilung des Stapels an φ-Punkten (nie 50 %), optische Mitte 46 % bei
zentriert gebauten Kacheln, Ngo-Balance/Gleichgewicht/Dichte als Zahlen ohne Gate. Ergebnis sind **fuenf Zahlen,
immer GEMEINSAM genannt** (judge druckt sie als eine Zeile, `summary.json`): Reihen-Treue (ehrlicher Name des
Harmonie-Index: Anteil Einzelmasse auf der Reihe — konsistent, nicht schoen), Lesbarkeit (Typo), Ordnung, Ruhe,
Balance. Ein Aufbau kann 95 % Reihen-Treue bei 49 % Ordnung haben (Probedurchlauf V3); erst alle zusammen
sagen „Goldener Schnitt". Nie eine der fuenf allein berichten.

```bash
python3 $SKILL/scripts/goldencut.py judge <url|datei.html> --scope "<css-selektor>" [--distance 450]
# → typo-report.md (Tabelle je Text), typo.json, typo-overlay.png (Urteil auf dem Screenshot), Klartext auf stdout
#   + layout-report.md (Relationen, Aufteilung, Balance), layout.json, layout-overlay.png (Kacheln, Stapelabstaende,
#     Kanten, Schwerpunkt). Beide Reports haben einen Abschnitt „Änderungen": eine Zeile je Soll als Punkt
#     („/120“: Schriftgröße 10,8 → 11 px · Stat-Kachel: Inhalt 54 % → 46 %) — so an den User geben (Grundsatz 5).
python3 $SKILL/scripts/goldencut.py layout <url|datei.html|before.json> --scope "<css-selektor>"   # nur Teil (b)
```

Lesehilfe Teil (b) — **Massen-Konvention (D4, seit 2026-08-22):** Gemessen wird, was das Auge als Masse liest,
nicht die CSS-Box. Bei Text liegt die Grundlinie je Zeile bei Schriftkasten-Oberkante + Ascent (aus den
Schriftmetriken, pixelgeprueft). Eine **Luecke zwischen zwei Zeilen** geht von der Grundlinie zur Schriftmasse
der naechsten Zeile — x-Hoehe bei Gemischtschrift, Versal-/Ziffernhoehe bei reinen Versalien oder Ziffern
(Oberlaengen sind duenn, Unterlaengen auch; das „g" in „Aufgaben" ist KEINE Kante). **Polster** zum Kachelrand
gehen von der Inhaltskante: oben Versalkante (wenn die Zeile Versalien/Ziffern/Oberlaengen hat, sonst x-Hoehe),
unten letzte Grundlinie, bei Grafik die Elementkante. Das **dominante Element** (groesste Schrift) bestimmt die
Zeile; kleinere Elemente, die es ueberlappen (Nenner „/120", Legendenpunkte), verlaengern sie nicht. **Grafik ist
Inhalt:** Balken, Icons und Kaesten im Fluss zaehlen fuer Luecken, Polster, Randkanon und optische Mitte wie
Schrift. Eine Kachel ist jeder sichtbare Kasten ab 44 px Hoehe (und 2 % der Flaeche oder 120×44 px); kleinere
Kaesten mit Inhalt (Pillen, Knoepfe) sind „Chips" und zaehlen als ganze Masse; absolut positionierte Deko (Blatt in
der Ecke, Flagge, Erdball) zaehlt nicht zur Struktur. „innen" = groesste Luecke zwischen den Inhaltszeilen einer
Kachel, „aussen" = kleinster Abstand zu irgendeinem Nachbarn. Der Bericht listet je Kachel die Luecken-Folge
(„Aufgaben"→Text 18,5 · Zeile→Zeile 15,4 · Text→Status 11,1) — diese Zahlen dem User zeigen, sie sind das, was er sieht.
Warum das noetig war (Probedurchlauf 2026-08-22): die alte Versalbox-Messung lag bei eigener Zeilenhoehe bis 2 px
daneben, ein ad-hoc „Tinten-Scan" ueber die g-Unterlaenge in die andere Richtung — beide haben an der Aufgaben-Kachel
eine Korrektur ausgeloest, die das Auge als Verschlechterung sah. ⚪ im Report = Relation hier nicht anwendbar (wird genannt,
nie verschwiegen). Balance/Gleichgewicht/Dichte sind Zahlen ohne Gate — auf einem scrollenden Stapel schwach;
Ordnung und Ruhe sind die harten. Bekannte Grenze: Stapel-Analyse ist eindimensional — Spalten-Layouts pro Spalte
als Scope messen. Adversarial geprueft 2026-08-21 (3 unabhaengige Reviewer; Codex ohne Guthaben — Prompt liegt bei).

Gemessen wird der **Sehwinkel der x-Hoehe am Leseabstand** (aus dem Viewport: Handy 30 cm, Tablet 45, Laptop 55,
Desktop 70; `--distance` ueberschreibt): unter 0,2° ist ein Text physiologisch zu klein (rot), unter dem
Rollen-Komfort knapp (orange). Hell auf dunkel, Light-Schnitte und schwacher Kontrast verlangen +10 %. Dazu
Zeilenlaenge (mehrzeilig 45–75 Zeichen), Zeilenhoehe je Rolle (nur mehrzeilig; Lesetext 1,2 bis φ — φ ist Obergrenze,
das laengenabhaengige Pearson-Soll steht nur als Hinweis, User-Entscheid 2026-08-21), Hierarchie (Stufen ≥ 1,25×
oder +200 Gewicht, ≤ 5 Groessen, Kennzahl ≥ 2× Grundgroesse), Laufweite und Touch-Ziele als Hinweis.
**Overlay ansehen und mit dem Auge vergleichen, bevor `run` etwas aendert.** Rollen mit „?“ sind unsicher —
die Rueckfrage steht fertig formuliert im Report (eine pro Text, Alltagssprache); Antworten kommen als
`roles` in die Config. Herleitung: `reference/schriftgroessen-abstaende.md` (Pruefkette T1–T6), Zielbild:
`reference/skill-konzept-v2.md`. Bei gemalten Hintergruenden (Bild, Pseudo-Element) ist der Kontrast nicht
messbar und wird so gemeldet, nicht geraten.

**Schritt 2 ff. — korrigieren (`run`):** `run` misst vor und nach dem Patch auch Typo und Ordnung mit und druckt
alle fuenf Zahlen vorher → nachher. **Faellt Ordnung, Lesbarkeit oder Ruhe, warnt er** — dann Patch nicht blind
uebernehmen, sondern die verursachenden Korrekturen streichen/schuetzen oder zuerst von Hand in der Werk-Reihenfolge
Schrift → Luecken → Polster → Kachel ordnen (Grundsatz 6).

```bash
SKILL=~/.claude/skills/goldencut
python3 $SKILL/scripts/goldencut.py run <url|datei.html> --scope "<css-selektor>" --title "<name>"
```

**Arbeitsdateien (PFLICHT, seit 2026-08-21):** `--out` weglassen — der Skill schreibt dann in einen Temp-Ordner
(`$TMPDIR/goldencut/<ziel>-<scope>-<zeit>/`) und meldet die Pfade. Ein Lauf erzeugt 16–19 Dateien (Mess-JSONs,
Screenshots, Patches, Reports); die sind Wegwerfware und gehoeren **nie** neben das Design, nie in den OD-Projektordner
(`.od/projects/...`) und nie ins Repo — Open Design zeigt jede Datei dort als Artefakt, Git nimmt sie mit (Vorfall:
33 Dateien `_gc-v2*` im Bilderbuch-Projekt). Der Skill verweigert ein `--out` im Zielordner/OD-Projekt (`--force-out`
erzwingt). Dem User das Beweisbild direkt zeigen (Pfad/Bild), nichts kopieren. Soll ein Nachweis dauerhaft beim Design
bleiben, dann genau EINE Datei `<design>.goldencut-proof.png` — nie die Messdaten.

1. **Scope und Viewport bestimmen.** Scope = der Aufbau, um den es geht (Kachel, Screen, Karte), als eindeutiger
   Selektor. Bei Dateien mit mehreren Varianten exakt eine treffen (z. B. `.v2src:not(.v3src)`).
   Viewport-Default 390×844 (iPhone); iPad quer `--width 1194 --height 834`; Desktop `--width 1440 --height 900`.
   Laufende App hinter Login: `--cdp http://127.0.0.1:9222` (dockt an das offene Chrome an).
2. **`run` ausfuehren.** Macht vier Schritte: Messung (before.json/png) → Analyse (report.md, patch.css,
   patch.override.css, corrections.json) → Verify (Patch injiziert, neu gemessen, report-after.md) → proof.png
   (vorher | nachher | Differenz).
3. **proof.png ansehen — Pflicht.** Pruefen, ob Umbrueche, Ueberlaeufe oder verschobene Deko entstanden sind.
   Wenn ja: betroffene Korrektur in patch.css streichen oder Wert schuetzen (`--protect`), erneut `run`.
   Jede gestrichene oder geschuetzte Korrektur wandert in den Bericht unter „Nicht uebernommen" (Grundsatz 5).
4. **Anwenden.**
   - Statische HTML-Datei (OD-Sheet, Prototyp): `goldencut.py apply --html <datei> --patch <out>/patch.css`
     fuegt `<style id="goldencut-patch">` ein; `--remove` nimmt ihn wieder raus. Besser: Werte direkt in den
     CSS-Block der Variante uebernehmen.
   - App/Framework: Werte aus patch.css in Tokens/Quelle uebertragen (em/rem umrechnen: Soll-px ÷ Basis).
     Danach `run` erneut gegen die App als Nachweis.
5. **Berichten (kurz).** Die fuenf Zahlen vorher → nachher (`run` druckt die Zeile „Zahlen: …" und schreibt
   `summary.json` — nie nur die Reihen-Treue allein), die drei bis fuenf wichtigsten Korrekturen in Worten
   („Stat-Kacheln: Padding oben 7 → 8, Abstand 12 → 13, Ziffer-Margin 11 → 10"). Bild mitsenden. Keine Tabellenwaende.
   **Pflichtblock „Nicht uebernommen"** (Grundsatz 5): jede Empfehlung des Skills, die nicht umgesetzt wurde, als
   Punkt „Eigentlich sollte <Mass> von A auf B — lasse ich, weil <gemalt / hartkodiert / vorausgesetzt von …>.
   Willst du es trotzdem?" Der Block darf nie fehlen; wenn alles uebernommen wurde, steht das da.
   **Fragen an den User menschlich stellen, nicht technisch** (User-Feedback 2026-08-21): Was sieht man, was
   aendert sich, was ist der Haken — in Alltagssprache, kurz und auf den Punkt. Also nicht „Punkte 9,2 → 8,5
   uebernehmen, Balken-Padding wegen BG6-Abgleich schuetzen?", sondern „Die Punkte werden ein Hauch kleiner und
   der Kopf rechts etwas enger — das passt. Eigentlich sollten auch die Balkenraender auf 6 und 8, die Reihe
   verlangt das; ich habe sie gelassen, weil sie pixelgenau auf die gemalte Vorlage abgeglichen sind und die
   Kachelhoehe daran haengt. Willst du sie trotzdem?" Zahlen nur, wenn sie fuer die Entscheidung noetig sind;
   Regelnummern, Selektoren und Eigenschaftsnamen gehoeren in den Report, nicht in die Frage.

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
| Touch-Ziel | 44 px Default; **ein gemaltes Grundmass darf das ueberschreiben** (`legibility.touch` in der Config) | siehe unten |

**Projekt-Config wird automatisch gefunden.** Ohne `--config` sucht der Skill eine `goldencut.config.json`
neben der Zieldatei und aufwaerts bis zum Home-Verzeichnis. So gelten projektweite Festlegungen auch dann,
wenn der Aufruf sie nicht mitgibt.

**Touch-Ziel gegen gemaltes Grundmass.** Der Default 44 px (WCAG/Apple) ist ein Mindestmass fuer die
TASTFLAECHE, nicht fuer die Optik. Wenn ein Design eine gemalte Grundform hat, deren Hoehe abgenommen ist
(Pillen, Chips, runde Knoepfe), setzt diese die Untergrenze — `legibility.touch` in der Projekt-Config auf
diesen Wert stellen, dann meldet der Skill nur noch, was DARUNTER liegt. Die 44 px gehoeren dann in die
App-Umsetzung (Padding am Button, Optik per Pseudo-Element), nicht in das Design-Sheet. Belegter Fall:
im Bilderbuch-Design riss der auf 44 vergroesserte +-Knopf die Naehe-Ordnung an einer voellig anderen
Stelle auf (Ordnung 96 -> 84 %), weil er unter die 37er Pillen ragte und damit den kleinsten
Kachelabstand bestimmte.

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
| G1 | Geschwister (gleiche Klasse + Reihe/Elternteil): identische Innenmasse (`judge`) | Soll, hartes Gate (Ordnung ≤ 50 %) |
| G3 | Ueberschriften gleicher Rolle: gleiche Stellung in der Kachel (oben/links) (`judge`) | Soll, User entscheidet |
| G2 | Polaritaet: hell auf dunkel wirkt groesser/fetter (Irradiation) (`judge`) | Hinweis, kein Gate |
| C1 | Naehe-Ordnung: innen < aussen je Ebene, Soll aussen = innen·φ (`judge`) | Soll, User entscheidet |
| C2 | Ueberschrift: oben = unten·φ…φ² (`judge`) | Soll, User entscheidet |
| C8 | Titel-Bindung in der Kachel: Titel→Text ≤ Zeile→Zeile ≤ Text→Block (`judge`) | Soll, User entscheidet |
| C3 | Kachel-Polster ≥ x-Hoehe des Haupttexts, ≈ Versalhoehe des groessten — Grafik eingeschlossen (`judge`) | Soll, User entscheidet |
| C9 | Grafik am Kachelrand: links = rechts = unten (`judge`) | Soll, User entscheidet |
| B8 | Chip-Hoehe = Hoehe der naechstgelegenen Kachel / φⁿ, n ≥ 1 (`judge`) | weiche Relation, halbes Gewicht |
| M1 | Gemalte Kante: sichtbare Kante aus dem Screenshot vs CSS-Box (`judge`) | Hinweis mit Zahlen |
| B6 | Konzentrische Radien r_innen = r_aussen − Polster (`judge`) | Soll, User entscheidet |
| C4/C5 | Rhythmus (Vielfache der Grund-Zeilenhoehe), Ausrichtungskanten (`judge`) | Zahl „Ruhe" |
| B4 | Randkanon: Kachel-Polster unten ≥ oben, klassisch unten = oben·φ (`judge`) | Soll, User entscheidet |
| B1/B3 | Hauptteilung des Stapels an φ-Punkten 38,2/61,8 % (nie 50 %), optische Mitte 46 % nur bei zentriert gebauten Kacheln (`judge`) | Soll, User entscheidet |
| E1–E4 | Ngo-Balance, Gleichgewicht, Dichte 30–50 %, Wert-Entropie (`judge`) | Zahl „Balance"/„Ruhe" |

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
- **Gemalte Kante (M1):** misst nur Seiten, die 3 px Aussenprobe haben — Kacheln buendig am Scope-Rand
  liefern dort `null` („Probe außerhalb nicht möglich"), das ist kein Fehler. Grain/Wash-Flaechen mit
  lokalem Kontrast unter der Schwelle (60 Kanaldiff) loesen keine Fehlkante aus; validiert an echten
  gemalten Assets in `tests/testbild-gemalt.html` (M1 trifft den am Asset-Alpha gemessenen Einzug ±1 px,
  auch asymmetrische Wobble-Kanten).

## Dateien

- `scripts/goldencut.py` — Einstieg (`judge`, `layout`, `run`, `measure`, `analyze`, `apply`)
- `scripts/gc_roles.py` — Leseart je Text (Heuristik + Rueckfragen)
- `scripts/gc_typo.py` — Schritt-1-Urteil (a): Lesbarkeits-Korridore, Hierarchie, Overlay
- `scripts/gc_layout.py` — Schritt-1-Urteil (b), Bauschritt 2: Ordnungsrelationen, Aufteilung, Balance, Overlay
- `scripts/gc_measure.py` — DOM-Messung via Playwright (computed styles, Boxen, Icon-Erkennung, Screenshot)
- `scripts/gc_analyze.py` — Regelwerk → Korrekturen, Report, Patch, Reihen-Treue (Harmonie-Index)
- `scripts/gc_compose.py` — Beweisbild vorher | nachher | Differenz
- `goldencut.config.example.json` — Vorlage fuer eine projektweite Zielreihe
- `tests/` — Herz-und-Nieren-Pruefung: `testbild.html` + `run_testbild.py` (CSS-Flaechen, 16 Erwartungen)
  und `testbild-gemalt.html` + `run_testbild_gemalt.py` (echt gemalte Assets in `tests/assets/`,
  Soll-Einzuege in `assets/soll.json`; prueft M1, Grain-Robustheit und den run-Pfad, 16 Erwartungen)
- `reference/`, `examples/` — lokal (gitignored): Regelwerk (regeln.md), Grafiker-Kette (schriftgroessen-abstaende.md), Mathematik-Modell (mathematische-prinzipien-ui.md), Zielbild (skill-konzept-v2.md), Referenzlaeufe

Voraussetzungen: `python3` mit `playwright` (Chromium installiert), `Pillow`, `numpy`.
