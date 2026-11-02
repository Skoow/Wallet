"""Accès Yahoo Finance partagé par les scripts (cours, historiques, chiffres)."""
import json, time, http.cookiejar, urllib.request, urllib.parse

UA = 'Mozilla/5.0 (portefeuille web app)'  # un faux navigateur Chrome reçoit 429 de Yahoo
_cj = http.cookiejar.CookieJar()
_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))
_crumb = None


def _open(url, timeout=20):
    return _op.open(urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*'}), timeout=timeout)


def get(url, tries=3):
    err = None
    for i in range(tries):
        try:
            with _open(url) as r:
                return json.load(r)
        except Exception as e:
            err = e
            time.sleep(1.5 * (i + 1))
    raise err


def chart(sym, rng='5d', interval='1d'):
    """rng = '5d', '2y'... ou 'depuis2006' (dates explicites : avec range=max Yahoo espace les points)."""
    q = urllib.parse.quote(sym)
    per = f'period1=1136073600&period2={int(time.time())}' if rng == 'depuis2006' else f'range={rng}'
    for host in ('query1', 'query2'):
        try:
            j = get(f'https://{host}.finance.yahoo.com/v8/finance/chart/{q}?{per}&interval={interval}&events=split')
            return j['chart']['result'][0]
        except Exception:
            continue
    return None


def crumb():
    global _crumb
    if _crumb:
        return _crumb
    try:
        _open('https://fc.yahoo.com', 10).read()
    except Exception:
        pass  # le cookie arrive même avec une erreur 404
    for host in ('query1', 'query2'):
        try:
            with _open(f'https://{host}.finance.yahoo.com/v1/test/getcrumb') as r:
                c = r.read().decode().strip()
                if c and '<' not in c:
                    _crumb = c
                    return c
        except Exception:
            continue
    return None


def summary(sym, modules='financialData,defaultKeyStatistics,summaryDetail,calendarEvents,price'):
    c = crumb()
    if not c:
        return None
    q = urllib.parse.quote(sym)
    for host in ('query1', 'query2'):
        try:
            j = get(f'https://{host}.finance.yahoo.com/v10/finance/quoteSummary/{q}?modules={modules}&crumb={urllib.parse.quote(c)}')
            return j['quoteSummary']['result'][0]
        except Exception:
            continue
    return None


def quotes(syms):
    """Cours de plusieurs symboles d'un coup (50 par appel) : {sym: (cours, horodatage)}."""
    out = {}
    c = crumb()
    for i in range(0, len(syms), 50):
        part = syms[i:i + 50]
        q = urllib.parse.quote(','.join(part))
        j = None
        for host in ('query1', 'query2'):
            try:
                j = get(f'https://{host}.finance.yahoo.com/v7/finance/quote?symbols={q}&fields=regularMarketPrice,regularMarketTime' + (f'&crumb={urllib.parse.quote(c)}' if c else ''))
                break
            except Exception:
                continue
        for r in ((j or {}).get('quoteResponse') or {}).get('result') or []:
            if r.get('regularMarketPrice') and r.get('regularMarketTime'):
                out[r['symbol']] = (float(r['regularMarketPrice']), int(r['regularMarketTime']))
        time.sleep(0.3)
    return out
