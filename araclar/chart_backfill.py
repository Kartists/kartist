# chart_backfill.py — TEK SEFERLİK tarihsel fiyat backfill'i (kaldığı yerden sürer)
# Her kartın PriceCharting sayfasındaki chart_data'dan 3 seri alır:
#   used→ham(u), graded→Grade9(g), manualonly→PSA10(x); değerler CENT.
# Çıktı: veri/grafik_ham/{sid}.jsonl  (satır: {"k":"slug","num":..,"u":[[aayyy,cent]..],..})
# Durum: veri/grafik_ham/durum.json  — bitince veri/grafik_ham/TAMAM yazılır.
# Kullanım: python3 araclar/chart_backfill.py [saniye_bütçesi]
import json, os, re, sys, time, urllib.request, urllib.error

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAM = os.path.join(KOK, 'veri', 'grafik_ham')
os.makedirs(HAM, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
DELAY = 2.6

def log(*a): print('[backfill]', *a, flush=True)

if os.path.exists(os.path.join(HAM, 'TAMAM')):
    log('zaten tamamlanmış, çıkılıyor'); sys.exit(0)

sure = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
t0 = time.time()

src = open(os.path.join(KOK, 'worker', 'src', 'worker.js'), encoding='utf-8').read()
CARDS = json.loads(re.search(r'const CARDS = (\{.*?\});\n', src).group(1))
eslesme = json.load(open(os.path.join(KOK, 'veri', 'eslesme.json')))
mapping = json.load(open(os.path.join(KOK, 'veri', 'pc_mapping.json')))

# pc_data'daki productUri'ler (u alanı) — sayfa yolunu kurmak için
pcuri = {}
for f in set(e['f'] for e in eslesme.values()):
    yol = os.path.join(KOK, 'veri', 'pc_data', f + '.json')
    if os.path.exists(yol):
        for p in json.load(open(yol)):
            if p.get('u'):
                pcuri[(f, p['n'])] = p['u']

durum_yol = os.path.join(HAM, 'durum.json')
durum = set(json.load(open(durum_yol))) if os.path.exists(durum_yol) else set()

def konsollar(f):
    pc = mapping[f]['pc']
    return pc if isinstance(pc, list) else [pc]

def cek(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode('utf-8', 'ignore')

def aylik(seri):
    """[[epoch_ms,cent],..] → [[YYYYAA,cent],..] (0/None değerler atılır)"""
    out = []
    for t, v in (seri or []):
        if not v: continue
        tt = time.gmtime(t / 1000)
        out.append([tt.tm_year * 100 + tt.tm_mon, v])
    return out

def durum_kaydet():
    json.dump(sorted(durum), open(durum_yol, 'w'))

islenen = hata = 0
try:
    for slug, v in CARDS.items():
        if slug in durum: continue
        if time.time() - t0 > sure: log('süre doldu'); break
        key = f'{v[4]}|{v[0]}|{v[1]}'
        e = eslesme.get(key)
        uri = pcuri.get((e['f'], e['pn'])) if e else None
        if not uri:
            durum.add(slug); continue   # PC'de yok → grafiği olmayacak
        html = None
        for kons in konsollar(e['f']):
            try:
                html = cek(f'https://www.pricecharting.com/game/{urllib.request.quote(kons)}/{urllib.request.quote(uri)}')
                break
            except urllib.error.HTTPError as ex:
                if ex.code == 404: continue
                if ex.code == 429: time.sleep(28); continue
                raise
        time.sleep(DELAY)
        if html is None:
            hata += 1; durum.add(slug); continue
        m = re.search(r'chart_data\s*=\s*(\{.*?\});', html, re.DOTALL)
        if m:
            try:
                d = json.loads(m.group(1))
                satir = {'k': slug, 'num': v[1],
                         'u': aylik(d.get('used')), 'g': aylik(d.get('graded')),
                         'x': aylik(d.get('manualonly'))}
                with open(os.path.join(HAM, v[4] + '.jsonl'), 'a', encoding='utf-8') as fh:
                    fh.write(json.dumps(satir, ensure_ascii=False, separators=(',', ':')) + '\n')
            except Exception:
                hata += 1
        durum.add(slug)
        islenen += 1
        if islenen % 50 == 0:
            durum_kaydet(); log(f'{len(durum)}/{len(CARDS)} (bu koşu {islenen}, hata {hata})')
finally:
    durum_kaydet()

if len(durum) >= len(CARDS):
    open(os.path.join(HAM, 'TAMAM'), 'w').write(time.strftime('%F %T'))
    log('BACKFILL TAMAMLANDI 🎉')
log(f'bitti: {len(durum)}/{len(CARDS)} işlendi (bu koşu {islenen}, hata {hata})')
