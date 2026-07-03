# pc_scrape2.py — PriceCharting console API'sinden TAM veri çekimi (v2)
# Kaydedilen alanlar: p (ungraded), p2 (PSA10), p3 (Grade9), d ($ değişim, işaretli),
# dp (% değişim, işaretli), u (productUri), kart (isCard)
# Kullanım: python3 pc_scrape2.py [saniye_bütçesi] [çıktı_klasörü]
import json, urllib.request, urllib.error, time, os, sys

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
mapping = json.load(open(os.path.join(KOK, 'veri', 'pc_mapping.json')))
DELAY = 2.8
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(KOK, 'veri', 'pc_data')
os.makedirs(OUT, exist_ok=True)

def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:
                time.sleep(25 + i * 10); continue
            raise
        except Exception:
            if i < tries - 1:
                time.sleep(6 + i * 6); continue
            raise
    return None

def fiyat(s):
    s = (s or '').strip()
    if not s.startswith('$'): return None
    try: return float(s.replace('$', '').replace(',', ''))
    except ValueError: return None

def fetch_console(pc_slug):
    items, cursor = [], 0
    while True:
        d = get(f'https://www.pricecharting.com/console/{urllib.request.quote(pc_slug)}?format=json&cursor={cursor}&sort=model-number')
        prods = d.get('products', [])
        if not prods: break
        for p in prods:
            sign = -1 if str(p.get('priceChangeSign', '')).strip() in ('-', 'negative', 'down') else 1
            dch_raw = p.get('priceChange', None)
            if isinstance(dch_raw, (int, float)):
                dch = dch_raw / 100.0          # cent → dolar
            else:
                dch = fiyat(dch_raw)
            dpc = p.get('priceChangePercentage', '')
            try:
                dpc = float(str(dpc).replace('%', '').replace(',', '')) if str(dpc).strip() else None
            except ValueError:
                dpc = None
            items.append({
                'n': p.get('productName', ''),
                'p': fiyat(p.get('price1', '')),
                'p2': fiyat(p.get('price2', '')),
                'p3': fiyat(p.get('price3', '')),
                'd': (dch * sign) if dch is not None else None,
                'dp': (dpc * sign) if dpc is not None else None,
                'u': p.get('productUri', '') or '',
                'kart': bool(p.get('isCard')),
            })
        if len(prods) < 150: break
        cursor += 150
        time.sleep(DELAY)
    return items

if __name__ == '__main__':
    sure = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
    t0 = time.time()
    tamam = sum(1 for s in mapping if os.path.exists(f'{OUT}/{s}.json'))
    for site, info in mapping.items():
        out = f'{OUT}/{site}.json'
        if os.path.exists(out): continue
        if time.time() - t0 > sure:
            print('SÜRE DOLDU'); break
        slugs = info['pc'] if isinstance(info['pc'], list) else [info['pc']]
        try:
            allitems = []
            for s in slugs:
                allitems += fetch_console(s); time.sleep(DELAY)
            json.dump(allitems, open(out, 'w'), ensure_ascii=False)
            tamam += 1
            print(f'✓ {site}: {len(allitems)}', flush=True)
        except Exception as e:
            print(f'✗ {site}: {str(e)[:80]}', flush=True)
            time.sleep(10)
        time.sleep(DELAY)
    print(f'DURUM: {tamam}/{len(mapping)}')
