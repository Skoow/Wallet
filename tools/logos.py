#!/usr/bin/env python3
"""Analyse une fois pour toutes les logos (financialmodelingprep) de toutes les actions de data/tickers.json.

Écrit data/logos.json : { "SYMBOLE_FMP": code } pour les logos qui demandent un traitement :
  "c" = logo clair (blanc sur transparent) -> la page met un fond sombre
  "m" = logo en toutes lettres (illisible en petit) -> la page affiche l'initiale
  "x" = pas de logo chez ce fournisseur -> la page passe directement à la source suivante
Les logos normaux ne sont pas listés. Le calcul est le même que celui de la page (48 x 48 pixels),
mais fait ici : certains navigateurs (Safari, Brave, Firefox anti-pistage) empêchent de lire les pixels.

Usage : python3 tools/logos.py [--max N]
"""
import io, json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow manquant : pip install pillow")

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUFFIXE = {"US": "", "TSX": ".TO", "EPA": ".PA", "AMS": ".AS", "EBR": ".BR", "ELIS": ".LS", "XETRA": ".DE",
           "LSE": ".L", "SWX": ".SW", "MIL": ".MI", "BME": ".MC", "STO": ".ST", "OSL": ".OL", "HEL": ".HE", "CPH": ".CO"}
UA = "tothemoon-logos/1.0"


def symbole(ticker, bourse):
    if bourse not in SUFFIXE:
        return None
    return str(ticker).upper().replace(".", "-").replace(" ", "-") + SUFFIXE[bourse]


def classer(data):
    """Même règle que la page : renvoie 'c', 'm' ou '' (normal)."""
    im = Image.open(io.BytesIO(data)).convert("RGBA").resize((48, 48), Image.BILINEAR)
    n = 48
    px = list(im.getdata()) if not hasattr(im, "get_flattened_data") else list(im.get_flattened_data())
    r0, g0, b0, a0 = px[0]
    bg = (r0, g0, b0) if a0 > 200 else None
    op = 0
    lum = 0.0
    x0, x1, y0, y1 = n, -1, n, -1
    for i, (r, g, b, a) in enumerate(px):
        if a <= 40:
            continue
        if bg and abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) < 60:
            continue
        op += 1
        lum += (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
        x, y = i % n, i // n
        x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
    if op <= 8:
        return ""
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    if bw / bh > 2.3 or bh < n * 0.2:
        return "m"
    if not bg and lum / op > 0.86:
        return "c"
    return ""


def analyser(sym):
    url = "https://financialmodelingprep.com/image-stock/" + urllib.parse.quote(sym) + ".png"
    for essai in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
            if len(data) < 60:
                return sym, "x"
            im = Image.open(io.BytesIO(data))
            w, h = im.size
            if w <= 8 or h <= 8 or not (0.45 <= w / max(1, h) <= 2.2):
                return sym, "x"   # la page refuse aussi ces images
            return sym, classer(data)
        except urllib.error.HTTPError as e:
            if e.code in (404, 403, 400):
                return sym, "x"
            time.sleep(1 + essai * 2)
        except Exception:
            time.sleep(1 + essai * 2)
    return sym, None   # inconnu : la page fera comme avant


def main():
    import urllib.parse  # noqa: F401
    mx = None
    if "--max" in sys.argv:
        mx = int(sys.argv[sys.argv.index("--max") + 1])
    tickers = json.load(open(os.path.join(RACINE, "data", "tickers.json")))
    syms = []
    for t in tickers:
        s = symbole(t[0], t[2])
        if s and s not in syms:
            syms.append(s)
    # actions du portefeuille conseillé et de l'univers d'abord
    for f in ("univers.json",):
        try:
            for u in json.load(open(os.path.join(RACINE, "data", f))):
                tk = u.get("ticker")
                if tk:
                    s = symbole(tk, "TSX" if u.get("pays") == "Canada" else "US")
                    if s and s not in syms:
                        syms.insert(0, s)
        except Exception:
            pass
    if mx:
        syms = syms[:mx]
    out_path = os.path.join(RACINE, "data", "logos.json")
    try:
        ancien = json.load(open(out_path))
    except Exception:
        ancien = {}
    res = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=24) as ex:
        for k, (sym, code) in enumerate(ex.map(analyser, syms), 1):
            if code is None:
                code = ancien.get(sym, "")
            if code:
                res[sym] = code
            if k % 1000 == 0:
                print(f"{k}/{len(syms)} en {time.time() - t0:.0f} s", flush=True)
    if mx:  # passage partiel : on garde le reste de l'ancien fichier
        for s, c in ancien.items():
            if s not in syms:
                res[s] = c
    res = dict(sorted(res.items()))
    with open(out_path, "w") as f:
        json.dump(res, f, separators=(",", ":"))
    n = {c: sum(1 for v in res.values() if v == c) for c in "cmx"}
    print(f"logos : {len(syms)} analysés · clairs {n['c']} · en toutes lettres {n['m']} · absents {n['x']}")


if __name__ == "__main__":
    import urllib.parse
    main()
