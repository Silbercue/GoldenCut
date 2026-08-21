#!/usr/bin/env python3
"""gc_measure — vermisst einen UI-Aufbau im DOM (Playwright/Chromium).

Liest fuer jedes sichtbare Element im Scope die gerenderten Werte
(Padding, Margin, Gap, Schriftgroesse, Zeilenhoehe, Box, Radius, Icon-Merkmale)
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
      interactive: ['a','button','input','select','textarea'].includes(tag) || el.getAttribute('role') === 'button',
    };
    index.set(el, rec.i);
    out.push(rec);
  }
  return {
    scope: { sel: scopeSel || 'body', x: r2(sr.left + scrollX), y: r2(sr.top + scrollY), w: r2(sr.width), h: r2(sr.height) },
    viewport: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio },
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
