# eub_refresh.py — "En Ucuzu Bul" verisini gece tazeler.
# index.html içindeki EUB_DATA bloğunu bulur, her teklifin fiyat+stok bilgisini
# mağaza sayfasının JSON-LD'sinden yeniler, ana sayfadaki 6 mini satırı günceller.
# Bir URL başarısız olursa ESKİ değer korunur.
import json, os, re, sys, time, urllib.request

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(KOK, 'worker', 'public', 'index.html')
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'}
AYLAR = ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık']

# Ana sayfa mini satırları: (etiket, set, tür)
MINI = [
    ('Chaos Rising ETB',    'Chaos Rising',         'Elite Trainer Box'),
    ('151 Booster Bundle',  '151',                  'Booster Bundle'),
    ('Prismatic Evol. ETB', 'Prismatic Evolutions', 'Elite Trainer Box'),
    ('Destined Rivals Box', 'Destined Rivals',      'Booster Box'),
    ('Journey Together ETB','Journey Together',     'Elite Trainer Box'),
    ('Mega Evolution Box',  'Mega Evolution',       'Booster Box'),
]

def log(*a): print('[eub]', *a, flush=True)

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode('utf-8', errors='ignore')

def jsonld_fiyat(html):
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
        if '"price"' in block or '"Offer"' in block:
            m = re.search(r'"price"\s*:\s*"?([\d.]+)', block)
            avail = re.search(r'(InStock|OutOfStock|SoldOut|Discontinued|PreOrder|BackOrder)', block)
            if m:
                stok = (avail.group(1) if avail else 'InStock') in ('InStock', 'PreOrder', 'BackOrder')
                return round(float(m.group(1))), stok
    # fallback: og/product meta veya itemprop (ör. Simurg Oyun)
    m = (re.search(r'<meta[^>]+(?:product:price:amount|og:price:amount)[^>]+content="([\d.]+)"', html)
         or re.search(r'itemprop="price"[^>]*content="([\d.]+)"', html))
    if m:
        stok = 'OutOfStock' not in html[:20000] and 'SoldOut' not in html[:20000]
        return round(float(m.group(1))), stok
    return None, None

def fmt(p): return '₺' + f'{p:,}'.replace(',', '.')

BEKLE = float(sys.argv[1]) if len(sys.argv) > 1 else 1.6

def main():
    h = open(INDEX, encoding='utf-8').read()
    i = h.find('var EUB_DATA = ')
    assert i > -1, 'EUB_DATA bulunamadı'
    b = i + len('var EUB_DATA = ')
    data, sonu = json.JSONDecoder().raw_decode(h[b:])
    ok = hata = degisen = 0
    for p in data['products']:
        for o in p['offers']:
            try:
                fiyat, stok = jsonld_fiyat(fetch(o['u']))
                if fiyat:
                    if fiyat != o['p'] or stok != o.get('stock'): degisen += 1
                    o['p'], o['stock'] = fiyat, stok
                    ok += 1
                else:
                    o['stock'] = None; hata += 1
            except Exception:
                o['stock'] = None; hata += 1
            time.sleep(BEKLE)
    for p in data['products']:
        p['offers'].sort(key=lambda o: (0 if o.get('stock') != False else 1, o['p']))
    t = time.localtime()
    data['updated'] = f'{t.tm_mday} {AYLAR[t.tm_mon-1]} {t.tm_year}'
    log(f'{ok} teklif tazelendi, {hata} başarısız (eski değer korundu), {degisen} değişti')
    yeni = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    h = h[:b] + yeni + h[b + sonu:]
    # tek seferlik taşıma: veride karşılığı olmayan eski satır etiketi
    h = h.replace('<span>Surging Sparks Box</span>', '<span>Mega Evolution Box</span>')
    # mini satırlar
    urun = {(p['set'], p['type']): p for p in data['products']}
    for etiket, s, tur in MINI:
        p = urun.get((s, tur))
        if not p: continue
        ucuz = min((o['p'] for o in p['offers'] if o.get('stock')), default=None)
        if ucuz is None: continue
        rx = re.compile(r'(<div class="mg-mini-row"><span>)' + re.escape(etiket) + r'(</span><b class="up">)[^<]*(</b></div>)')
        if rx.search(h):
            h = rx.sub(lambda m: m.group(1) + etiket + m.group(2) + fmt(ucuz) + m.group(3), h)
    open(INDEX, 'w', encoding='utf-8').write(h)
    log('index EUB_DATA + mini satırlar yazıldı')
    # yedek kopya (repo geçmişi = zaman serisi)
    json.dump(data, open(os.path.join(KOK, 'veri', 'eub_son.json'), 'w'), ensure_ascii=False)

if __name__ == '__main__':
    main()
