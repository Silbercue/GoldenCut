#!/usr/bin/env python3
"""gc_measure — vermisst einen UI-Aufbau im DOM (Playwright/Chromium).

Liest fuer jedes sichtbare Element im Scope die gerenderten Werte
(Padding, Margin, Gap, Schriftgroesse, Zeilenhoehe, Box, Radius, Icon-Merkmale,
Schriftmetriken x-Hoehe/Versalhoehe/Stamm per Canvas, Zeilenzahl, Kontrast, Tiefe)
und schreibt measure.json + shot.png. Der Browser ist die einzige Quelle
der Wahrheit — nicht der Quellcode.

Aufruf:
  gc_measure.py <url|datei.html> --out DIR [--scope CSS] [--width 390]
                [--height 844] [--scale 2] [--inject patch.css]
                [--cdp http://127.0.0.1:9222] [--wait 300] [--name before]
"""

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

JS_WALK = r"""
(args) => {
  const { scopeSel } = args;
  const scope = scopeSel ? document.querySelector(scopeSel) : document.body;
  if (!scope) return { error: 'scope nicht gefunden: ' + scopeSel };
  const px = v => { const n = parseFloat(v); return Number.isFinite(n) ? n : 0; };
  const r2 = n => Math.round(n * 100) / 100;
  const ICON_RX = /(^|[\s_-])(icon|ico|glyph|lucide|feather|fa-|material-icons|material-symbols|symbol|chevron|arrow|dot|bullet|avatar|badge)/i;
  const SKIP = new Set(['SCRIPT','STYLE','NOSCRIPT','TEMPLATE','BR','WBR','HEAD','META','LINK','TITLE']);

  function uniqueSel(el) {
    if (el.id && document.querySelectorAll('#' + CSS.escape(el.id)).length === 1) return '#' + CSS.escape(el.id);
    const parts = []; let cur = el;
    while (cur && cur !== document.documentElement) {
      let part = cur.tagName.toLowerCase();
      if (cur.id) { part = '#' + CSS.escape(cur.id); }
      else {
        const cls = [...cur.classList].filter(c => !/^(active|hover|focus|selected|open|is-|js-|has-)/.test(c)).slice(0, 2);
        part += cls.map(c => '.' + CSS.escape(c)).join('');
        const parent = cur.parentElement;
        if (parent && parent !== document.documentElement) {
          const same = [...parent.children].filter(s => s.tagName === cur.tagName && s.className === cur.className);
          if (same.length > 1) part += ':nth-child(' + ([...parent.children].indexOf(cur) + 1) + ')';
        }
      }
      parts.unshift(part);
      const sel = parts.join(' > ');
      try { if (document.querySelectorAll(sel).length === 1) return sel; } catch (e) {}
      if (cur.id) break;
      cur = cur.parentElement;
    }
    return parts.join(' > ');
  }


  // --- Schriftmetriken per Canvas: x-Hoehe, Versalhoehe, Stammbreite, mittlere Zeichenbreite (je Font-Key einmal)
  const fontCache = new Map();
  function fontMetrics(cs) {
    const key = `${cs.fontStyle}|${cs.fontWeight}|${cs.fontFamily}`;
    if (fontCache.has(key)) return key;
    const size = 200;
    const c = document.createElement('canvas'); c.width = 600; c.height = 320;
    const ctx = c.getContext('2d', { willReadFrequently: true });
    const fontSpec = `${cs.fontStyle} ${cs.fontWeight} ${size}px ${cs.fontFamily}`;
    ctx.font = fontSpec; ctx.textBaseline = 'alphabetic';
    const asc = ch => { const m = ctx.measureText(ch); return (m.actualBoundingBoxAscent || 0) / size; };
    const xh = asc('x'), cap = asc('H'), digit = asc('0');
    const adv = ctx.measureText('abcdefghijklmnopqrstuvwxyz').width / 26 / size;
    // Schrift-Ascent/-Descent (hhea/OS2): bestimmen die Lage der Grundlinie im Zeilenkasten
    // (Grundlinie = Zeilenoben + halber Durchschuss + ascent). Massen-Konvention in gc_layout.
    const mH = ctx.measureText('H');
    const fasc = (mH.fontBoundingBoxAscent || 0) / size, fdesc = (mH.fontBoundingBoxDescent || 0) / size;
    // Stammbreite: 'l' zeichnen, Zeile auf halber Versalhoehe abtasten, laengster Tintenlauf
    ctx.clearRect(0, 0, 600, 320); ctx.fillStyle = '#000'; ctx.fillText('l', 100, 280);
    const row = 280 - Math.round(cap * size * 0.5);
    const img = ctx.getImageData(0, Math.max(0, row), 600, 1).data;
    const runs = []; let cur = 0;
    for (let i = 0; i < 600; i++) { if (img[i * 4 + 3] > 128) cur++; else if (cur) { runs.push(cur); cur = 0; } }
    if (cur) runs.push(cur);
    const stem = runs.length ? Math.max(...runs) / size : null;
    // Nur die erste Familie pruefen: mit dem ganzen Stack liefert check() false, sobald ein Fallback nicht installiert ist
    const first = cs.fontFamily.split(',')[0].trim();
    let loaded = null; try { loaded = document.fonts.check(`${cs.fontStyle} ${cs.fontWeight} 16px ${first}`); } catch (e) {}
    fontCache.set(key, { key, family: cs.fontFamily.split(',')[0].replace(/["']/g, ''), weight: cs.fontWeight, style: cs.fontStyle,
      xHeight: r2(xh), capHeight: r2(cap), digitHeight: r2(digit), ascent: fasc ? Math.round(fasc * 1000) / 1000 : null, descent: fdesc ? Math.round(fdesc * 1000) / 1000 : null,
      stem: stem === null ? null : Math.round(stem * 1000) / 1000, advance: r2(adv), loaded });
    return key;
  }
  // --- Zeilen eines Elements (nur direkte Textknoten): Anzahl, breiteste Zeile, Summe der Zeilenbreiten
  function textLines(el) {
    const range = document.createRange(); const rects = [];
    for (const n of el.childNodes) {
      if (n.nodeType !== 3 || !n.textContent.trim()) continue;
      range.selectNodeContents(n);
      for (const r of range.getClientRects()) if (r.width > 0 && r.height > 0) rects.push({ top: r.top, left: r.left, right: r.right, h: r.height });
    }
    if (!rects.length) return null;
    rects.sort((a, b) => a.top - b.top);
    const lines = [];
    for (const r of rects) {
      const L = lines[lines.length - 1];
      if (L && Math.abs(L.top - r.top) < Math.max(2, r.h * 0.3)) { L.left = Math.min(L.left, r.left); L.right = Math.max(L.right, r.right); }
      else lines.push({ top: r.top, left: r.left, right: r.right });
    }
    const widths = lines.map(l => l.right - l.left);
    return { lines: lines.length, maxW: r2(Math.max(...widths)), sumW: r2(widths.reduce((a, b) => a + b, 0)), firstTop: r2(lines[0].top), firstLeft: r2(lines[0].left) };
  }
  // --- effektiver Hintergrund (naechster Vorfahr mit deckender Farbe) + WCAG-Kontrast
  function parseRGBA(s) { const m = s && s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(',').map(parseFloat); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; }
  function lum(c) { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); }
  function effectiveBg(el) {
    let cur = el, viaImage = false;
    while (cur && cur !== document.documentElement.parentNode) {
      const s = getComputedStyle(cur);
      if (s.backgroundImage && s.backgroundImage !== 'none') viaImage = true;
      // gemalte Flaechen liegen oft in ::before/::after oder in einem absolut positionierten <img>/<canvas>/<svg>
      for (const ps of ['::before', '::after']) { const q = getComputedStyle(cur, ps); if (q.content && q.content !== 'none' && (q.backgroundImage !== 'none' || q.backgroundColor !== 'rgba(0, 0, 0, 0)')) viaImage = true; }
      if (!viaImage && [...cur.children].some(ch => { const t = ch.tagName.toLowerCase(); if (!['img','canvas','svg','picture','video'].includes(t)) return false; const cp = getComputedStyle(ch); const cr = ch.getBoundingClientRect(); return cp.position === 'absolute' && cr.width >= cur.getBoundingClientRect().width * 0.8; })) viaImage = true;
      const c = parseRGBA(s.backgroundColor);
      if (c && c.a >= 0.5) return { c, viaImage };
      cur = cur.parentElement;
    }
    return { c: { r: 255, g: 255, b: 255, a: 1 }, viaImage };
  }
  function contrast(fg, bg) { const a = lum(fg), b = lum(bg); return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05); }

  const sr = scope.getBoundingClientRect();
  const list = [scope, ...scope.querySelectorAll('*')];
  const out = []; const index = new Map();

  for (const el of list) {
    if (SKIP.has(el.tagName)) continue;
    // SVG-Innereien ueberspringen: das <svg> selbst ist das Icon
    if (el.namespaceURI === 'http://www.w3.org/2000/svg' && el.tagName.toLowerCase() !== 'svg') continue;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (cs.display === 'none' || cs.visibility === 'hidden' || px(cs.opacity) === 0) continue;
    if (r.width <= 0 || r.height <= 0) continue;
    // Elemente ausserhalb des Scopes (z.B. fixed) weglassen
    if (r.right < sr.left - 1 || r.left > sr.right + 1 || r.bottom < sr.top - 1 || r.top > sr.bottom + 1) continue;

    const directText = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').replace(/\s+/g, ' ').trim();
    const allText = (el.textContent || '').replace(/\s+/g, ' ').trim();
    const tag = el.tagName.toLowerCase();
    const cls = [...el.classList].join(' ');
    const hasBgImg = cs.backgroundImage !== 'none' || (cs.maskImage && cs.maskImage !== 'none') || (cs.webkitMaskImage && cs.webkitMaskImage !== 'none');
    const square = Math.abs(r.width - r.height) <= 1.5;
    const small = r.width <= 64 && r.height <= 64;
    // Icon: <svg>/<img> klein; sonst nur QUADRATISCH + ohne Text + (Icon-Klasse | Bild/Maske | Punkt)
    let isIcon = false;
    if (tag === 'svg' || tag === 'img') isIcon = small;
    else if (!allText && small && square && (ICON_RX.test(cls) || hasBgImg || (r.width <= 16 && (cs.borderRadius.includes('%') || px(cs.borderRadius) >= r.width / 2)))) isIcon = true;
    else if (ICON_RX.test(cls) && small && square && allText.length <= 2) isIcon = true;
    // Sichtbare Box? Nur dann sind Raender als Raender wahrnehmbar (P8/P9)
    const bgc = cs.backgroundColor;
    const bgVisible = bgc && !/rgba\(\s*\d+,\s*\d+,\s*\d+,\s*0\s*\)/.test(bgc) && bgc !== 'transparent';
    const hasBorder = px(cs.borderTopWidth) + px(cs.borderRightWidth) + px(cs.borderBottomWidth) + px(cs.borderLeftWidth) > 0 && cs.borderTopStyle !== 'none';
    const hasBox = bgVisible || hasBorder || cs.boxShadow !== 'none' || cs.backgroundImage !== 'none';
    // Absichtliche Asymmetrie? Pseudo-Elemente oder absolut positionierte Kinder deuten auf Platz fuer Deko/Icon
    const pb_ = getComputedStyle(el, '::before').content, pa_ = getComputedStyle(el, '::after').content;
    const hasPseudo = (pb_ && pb_ !== 'none' && pb_ !== 'normal') || (pa_ && pa_ !== 'none' && pa_ !== 'normal');
    const hasAbsChild = [...el.children].some(c => { const p = getComputedStyle(c).position; return p === 'absolute' || p === 'fixed'; });

    const lh = cs.lineHeight === 'normal' ? null : px(cs.lineHeight);
    const rowGap = cs.rowGap === 'normal' ? 0 : px(cs.rowGap);
    const colGap = cs.columnGap === 'normal' ? 0 : px(cs.columnGap);
    const br = cs.borderRadius;
    const radius = (br.includes('%') || br.split(' ').length > 1) ? null : px(br);

    // Schritt-1-Messungen
    const tl = directText ? textLines(el) : null;
    let ctr = null, lod = null; const bgInfo = effectiveBg(el);
    if (directText) { const fg = parseRGBA(cs.color); if (fg) { ctr = Math.round(contrast(fg, bgInfo.c) * 100) / 100; lod = lum(fg) > lum(bgInfo.c); } }
    let depth = 0, boxDepth = 0, inInteractive = false, anc = el.parentElement;
    while (anc && anc !== scope.parentElement) {
      depth++;
      const rid = index.get(anc);
      if (rid !== undefined) { const pr = out[rid]; if (pr.hasBox) boxDepth++; if (pr.interactive) inInteractive = true; }
      anc = anc.parentElement;
    }
    const rec = {
      i: out.length,
      parent: el === scope ? -1 : (index.has(el.parentElement) ? index.get(el.parentElement) : null),
      sel: uniqueSel(el), tag, cls,
      text: directText.slice(0, 40), textLen: directText.length, allTextLen: allText.length,
      children: el.children.length,
      x: r2(r.left - sr.left), y: r2(r.top - sr.top), w: r2(r.width), h: r2(r.height),
      absX: r2(r.left + scrollX), absY: r2(r.top + scrollY),
      pt: px(cs.paddingTop), pr: px(cs.paddingRight), pb: px(cs.paddingBottom), pl: px(cs.paddingLeft),
      mt: px(cs.marginTop), mr: px(cs.marginRight), mb: px(cs.marginBottom), ml: px(cs.marginLeft),
      bt: px(cs.borderTopWidth), brw: px(cs.borderRightWidth), bb: px(cs.borderBottomWidth), bl: px(cs.borderLeftWidth),
      rowGap, colGap, display: cs.display, flexDir: cs.flexDirection,
      fs: r2(px(cs.fontSize)), lh: lh === null ? null : r2(lh), fw: cs.fontWeight,
      ff: cs.fontFamily.split(',')[0].replace(/["']/g, ''),
      ls: cs.letterSpacing === 'normal' ? 0 : px(cs.letterSpacing),
      radius, isIcon, hasBox, hasPseudo, hasAbsChild, position: cs.position,
      // gemalte Flaechen (9-Slice, Bild): die sichtbare Kante kann innerhalb der CSS-Box liegen (gc_layout K1)
      bgImage: cs.backgroundImage !== 'none', borderImage: !!(cs.borderImageSource && cs.borderImageSource !== 'none'),
      interactive: ['a','button','input','select','textarea'].includes(tag) || el.getAttribute('role') === 'button',
      // Schritt 1 (Typo-Urteil): Metriken, Zeilen, Kontrast, Tiefe
      fontKey: directText ? fontMetrics(cs) : null,
      fontStyle: cs.fontStyle, textTransform: cs.textTransform, color: cs.color,
      lines: tl ? tl.lines : 0, lineMaxW: tl ? tl.maxW : 0, lineSumW: tl ? tl.sumW : 0,
      textTop: tl ? r2(tl.firstTop - sr.top) : null, textLeft: tl ? r2(tl.firstLeft - sr.left) : null,
      contrast: ctr, lightOnDark: lod, bgViaImage: bgInfo.viaImage,
      depth, boxDepth, inInteractive,
    };
    index.set(el, rec.i);
    out.push(rec);
  }
  return {
    scope: { sel: scopeSel || 'body', x: r2(sr.left + scrollX), y: r2(sr.top + scrollY), w: r2(sr.width), h: r2(sr.height) },
    viewport: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio },
    fonts: Object.fromEntries(fontCache),
    elements: out,
  };
}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="URL oder Pfad zu einer HTML-Datei")
    ap.add_argument("--out", required=True, help="Ausgabeordner")
    ap.add_argument("--scope", default=None, help="CSS-Selektor des zu vermessenden Aufbaus (Default: body)")
    ap.add_argument("--width", type=int, default=390)
    ap.add_argument("--height", type=int, default=844)
    ap.add_argument("--scale", type=float, default=2.0, help="Device-Scale-Factor fuer den Screenshot")
    ap.add_argument("--inject", default=None, help="CSS-Datei, die vor der Messung injiziert wird (Verify)")
    ap.add_argument("--cdp", default=None, help="An laufendes Chrome andocken (z.B. http://127.0.0.1:9222)")
    ap.add_argument("--wait", type=int, default=300, help="Zusatzwartezeit in ms nach Load")
    ap.add_argument("--name", default="before", help="Dateipraefix (before/after)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    target = args.target
    if not target.startswith(("http://", "https://", "file://")):
        p = Path(target).expanduser().resolve()
        if not p.exists():
            print(f"FEHLER: Datei nicht gefunden: {p}", file=sys.stderr)
            return 1
        target = p.as_uri()

    with sync_playwright() as pw:
        browser = None
        if args.cdp:
            browser = pw.chromium.connect_over_cdp(args.cdp)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.new_page()
            page.set_viewport_size({"width": args.width, "height": args.height})
        else:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": args.width, "height": args.height},
                                      device_scale_factor=args.scale)
            page = ctx.new_page()
        page.goto(target, wait_until="load")
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        page.evaluate("document.fonts && document.fonts.ready")
        if args.inject:
            page.add_style_tag(content=Path(args.inject).read_text(encoding="utf-8"))
        page.wait_for_timeout(args.wait)

        data = page.evaluate(JS_WALK, {"scopeSel": args.scope})
        if "error" in data:
            print("FEHLER:", data["error"], file=sys.stderr)
            return 1
        data["target"] = args.target
        data["name"] = args.name
        data["measuredAt"] = time.strftime("%Y-%m-%d %H:%M:%S")

        shot = out / f"{args.name}.png"
        if args.scope:
            page.locator(args.scope).first.screenshot(path=str(shot))
        else:
            page.screenshot(path=str(shot), full_page=True)
        data["shot"] = str(shot)
        (out / f"{args.name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

        if args.cdp:
            page.close()
        else:
            browser.close()

    print(f"{len(data['elements'])} Elemente, Scope {data['scope']['w']}x{data['scope']['h']} px -> {out / (args.name + '.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
