# likidite_tara.py — TEK SEFERLİK likidite taraması (kaldığı yerden sürer)
# Her kartın PriceCharting sayfasından raw (used) ve PSA10 (graded) satış hacmini okur.
# Kural: raw VE psa10 yılda >=2 satış → likit (1). Değilse gürültü (0).
# Çıktı: veri/likidite/ham.jsonl  (satır: {"slug":.., "raw":"1 sale per week", "psa10":"1 sale per year", "likit":0})
# Durum: veri/likidite/durum.json  — bitince veri/likidite/TAMAM yazılır.
# Kullanım: python3 araclar/likidite_tara.py [saniye_bütçesi]
import json, os, re, sys, time, urllib.request, urllib.error

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIK = os.path.join(KOK, 'veri', 'likidite')
os.makedirs(CIK, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
DELAY = 2.6

def log(*a): print('[likidite]', *a, flush=True)

if os.path.exists(os.path.join(CIK, 'TAMAM')):
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

durum_yol = os.path.join(CIK, 'durum.json')
durum = set(json.load(open(durum_yol))) if os.path.exists(durum_yol) else set()

def konsollar(f):
    pc = mapping[f]['pc']
    return pc if isinstance(pc, list) else [pc]

def cek(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode('utf-8', 'ignore')

def hacim_coz(html, tab):
    """sales_volume satırından belirli fiyat tipinin hacim metnini çıkar."""
    m = re.search(r'<tr class="sales_volume">(.*?)</tr>', html, re.DOTALL)
    if not m:
        return ''
    h = dict(re.findall(r'data-show-tab="([^"]+)".*?<a href="#">([^<]+)</a>', m.group(1), re.DOTALL))
    return h.get(tab, '').strip()

def likit_mi(vol):
    """yılda >=2 satış mı? per day/week/month → evet. 'N sales per year' → N>=2. rare/boş/1 → hayır."""
    if not vol:
        return False
    if 'per day' in vol or 'per week' in vol or 'per month' in vol:
        return True
    m = re.match(r'(\d+)\s+sales?\s+per\s+year', vol)
    if m:
        return int(m.group(1)) >= 2
    return False

def durum_kaydet():
    json.dump(sorted(durum), open(durum_yol, 'w'))

islenen = hata = likit_say = 0
try:
    for slug, v in CARDS.items():
        if slug in durum:
            continue
        if time.time() - t0 > sure:
            log('süre doldu'); break
        key = f'{v[4]}|{v[0]}|{v[1]}'
        e = eslesme.get(key)
        uri = pcuri.get((e['f'], e['pn'])) if e else None
        if not uri:
            durum.add(slug); continue   # PC'de yok → likit değil sayılır (kayıt yazılmaz)

        # --- sayfayı getir: geçici ağ hatalarında ASLA çökme, kaldığın yerden devam et ---
        html = None
        bulunamadi = True   # her konsolda temiz 404 → kart gerçekten yok (kalıcı, likit değil)
        for kons in konsollar(e['f']):
            url = f'https://www.pricecharting.com/game/{urllib.request.quote(kons)}/{urllib.request.quote(uri)}'
            for deneme in range(3):                     # aynı konsolu geçici hatada 3 kez dene
                try:
                    html = cek(url)
                    break
                except urllib.error.HTTPError as ex:
                    if ex.code == 404:
                        break                           # bu konsolda yok → sıradaki konsola geç
                    bulunamadi = False                  # 429 / 5xx: geçici sunucu durumu
                    time.sleep(30 if ex.code == 429 else 5)
                except Exception:                       # timeout / bağlantı kopması / DNS: geçici
                    bulunamadi = False
                    time.sleep(5)
            if html is not None:
                break
        time.sleep(DELAY)
        if html is None:
            if bulunamadi:
                durum.add(slug)                         # gerçekten hiçbir konsolda yok → işaretle, bir daha bakma
            else:
                hata += 1                               # geçici hata → İŞARETLEME; sonraki koşuda tekrar denenir
            continue

        raw_v = hacim_coz(html, 'completed-auctions-used')
        psa_v = hacim_coz(html, 'completed-auctions-graded')
        likit = 1 if (likit_mi(raw_v) and likit_mi(psa_v)) else 0
        if likit:
            likit_say += 1
        satir = {'slug': slug, 'raw': raw_v, 'psa10': psa_v, 'likit': likit}
        with open(os.path.join(CIK, 'ham.jsonl'), 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(satir, ensure_ascii=False, separators=(',', ':')) + '\n')
        durum.add(slug)
        islenen += 1
        if islenen % 50 == 0:
            durum_kaydet()
            log(f'{len(durum)}/{len(CARDS)} (bu koşu {islenen}, likit {likit_say}, hata {hata})')
finally:
    durum_kaydet()

if len(durum) >= len(CARDS):
    open(os.path.join(CIK, 'TAMAM'), 'w').write(time.strftime('%F %T'))
    log('LİKİDİTE TARAMASI TAMAMLANDI 🎉')
log(f'bitti: {len(durum)}/{len(CARDS)} işlendi (bu koşu {islenen}, likit {likit_say}, hata {hata})')
