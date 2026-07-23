# pipeline.py — gece güncelleme hattı
# Akış: kur çek → pc_data + eslesme → TL fiyatlar → worker CARDS / index CARD_DATA /
#        119 set sayfası yeniden yaz → borsa.json + psa.json üret → sağlamalar.
# Eksik/başarısız veri ESKİ değeri korur; hiçbir kart silinmez/eklenmez.
# Kullanım: repo kökünden  python3 araclar/pipeline.py
import json, os, re, sys, time, gzip, subprocess, urllib.request

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(KOK, 'worker')
VERI = os.path.join(KOK, 'veri')
PC = os.path.join(VERI, 'pc_data')
WORKER_JS = os.path.join(W, 'src', 'worker.js')
INDEX = os.path.join(W, 'public', 'index.html')

def log(*a): print('[pipeline]', *a, flush=True)

# ── 1. KUR ────────────────────────────────────────────────────────────────
def kur_cek():
    kaynaklar = [
        ('frankfurter', 'https://api.frankfurter.app/latest?from=USD&to=TRY',
         lambda d: d['rates']['TRY']),
        ('er-api', 'https://open.er-api.com/v6/latest/USD',
         lambda d: d['rates']['TRY']),
    ]
    for ad, url, sec in kaynaklar:
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                kur = float(sec(json.loads(r.read())))
            if 5 < kur < 500:
                json.dump({'USDTRY': kur, 'tarih': time.strftime('%a, %d %b %Y %H:%M:%S +0000', time.gmtime()), 'kaynak': ad},
                          open(os.path.join(VERI, 'kur.json'), 'w'))
                log(f'kur ({ad}): {kur}')
                return kur
        except Exception as e:
            log(f'kur {ad} hata: {e}')
    eski = json.load(open(os.path.join(VERI, 'kur.json')))
    log(f"kur çekilemedi, eski kur kullanılıyor: {eski['USDTRY']}")
    return float(eski['USDTRY'])

# ── TL kuralları ──────────────────────────────────────────────────────────
def tl_kaydet(usd, kur):
    """Veriye yazılan TL: ≥20 tam sayı, altı 1 ondalık."""
    if usd is None: return None
    t = usd * kur
    return int(round(t)) if t >= 20 else round(t, 1)

def tl_goster(tl):
    """Set sayfalarındaki görünüm: 3.503 / 374 / 47 / 10,3"""
    if tl is None: return ''
    if tl >= 1000: return f'{int(round(tl)):,}'.replace(',', '.')
    if tl >= 20: return str(int(round(tl)))
    s = f'{tl:.1f}'.replace('.', ',')
    return s

# ── 2. PC verisini oku, kart → yeni değerler haritası ────────────────────
def fiyat_haritasi(kur):
    eslesme = json.load(open(os.path.join(VERI, 'eslesme.json')))
    dosyalar = {}
    def pc(f):
        if f not in dosyalar:
            yol = os.path.join(PC, f + '.json')
            if os.path.exists(yol):
                d = json.load(open(yol))
                dosyalar[f] = {p['n']: p for p in d}
            else:
                dosyalar[f] = None
        return dosyalar[f]
    yeni = {}   # "sid|name|num" -> {'tl','p2tl','p3tl','dp'}
    eksik_dosya, eksik_urun = set(), 0
    for key, e in eslesme.items():
        prods = pc(e['f'])
        if prods is None:
            eksik_dosya.add(e['f']); continue
        p = prods.get(e['pn'])
        if p is None:
            eksik_urun += 1; continue
        yeni[key] = {
            'tl': tl_kaydet(p.get('p'), kur),
            'p2tl': tl_kaydet(p.get('p2'), kur),
            'p3tl': tl_kaydet(p.get('p3'), kur),
            'dp': (round(p['dp'], 1) if isinstance(p.get('dp'), (int, float)) else None),
        }
    if eksik_dosya: log('UYARI eksik pc_data dosyaları (eski fiyat korunur):', sorted(eksik_dosya))
    if eksik_urun: log(f'UYARI {eksik_urun} üründe isim bulunamadı (eski fiyat korunur)')
    log(f'fiyat haritası: {len(yeni)} kart')
    return yeni

# ── 3. worker.js CARDS ────────────────────────────────────────────────────
def worker_guncelle(yeni):
    src = open(WORKER_JS, encoding='utf-8').read()
    m = re.search(r'const CARDS = (\{.*?\});\n', src)
    cards = json.loads(m.group(1))
    degisen = 0
    for slug, v in cards.items():
        key = f'{v[4]}|{v[0]}|{v[1]}'
        y = yeni.get(key)
        # 8: PSA10 TL, 9: Grade9 TL, 10: değişim %
        while len(v) < 11: v.append(None)
        if y:
            if y['tl'] is not None and y['tl'] != v[2]:
                v[2] = y['tl']; degisen += 1
            v[8], v[9], v[10] = y['p2tl'], y['p3tl'], y['dp']
    blok = 'const CARDS = ' + json.dumps(cards, ensure_ascii=False, separators=(',', ':')) + ';\n'
    src = src[:m.start()] + blok + src[m.end():]
    open(WORKER_JS, 'w', encoding='utf-8').write(src)
    log(f'worker CARDS: {degisen} fiyat değişti, {len(cards)} kart')
    return cards, degisen

# ── 4. index.html CARD_DATA ───────────────────────────────────────────────
BASLIK = "const CARD_DATA = JSON.parse('"
def index_guncelle(yeni):
    h = open(INDEX, encoding='utf-8').read()
    i = h.find(BASLIK)
    assert i > -1, 'CARD_DATA bulunamadı'
    b = i + len(BASLIK)
    j = h.find("');", b)
    raw = h[b:j].replace('\\\\', '\x00').replace("\\'", "'").replace('\x00', '\\')
    cd = json.loads(raw)
    degisen = 0
    for sid, rars in cd.items():
        for rar, kartlar in rars.items():
            for c in kartlar:
                y = yeni.get(f"{sid}|{c['n']}|{c['num']}")
                if y and y['tl'] is not None and y['tl'] != c['p']:
                    c['p'] = y['tl']; degisen += 1
    dump = json.dumps(cd, ensure_ascii=False, separators=(',', ':'))
    dump = dump.replace('\\', '\\\\').replace("'", "\\'")
    h = h[:b] + dump + h[j:]
    open(INDEX, 'w', encoding='utf-8').write(h)
    json.dump(cd, open(os.path.join(VERI, 'card_data_TL.json'), 'w'), ensure_ascii=False)
    log(f'index CARD_DATA: {degisen} fiyat değişti')
    return cd

# ── 5. 119 statik set sayfası ────────────────────────────────────────────
def set_sayfalari(cards):
    src = open(WORKER_JS, encoding='utf-8').read()
    sets = json.loads(re.search(r'const SETS = (\{.*?\});\n', src).group(1))
    slug_tl = {slug: v[2] for slug, v in cards.items()}
    # set-slug -> en değerli kart
    enler = {}
    for slug, v in cards.items():
        st = v[5]
        if v[2] is not None and (st not in enler or v[2] > enler[st][1]):
            enler[st] = (v[0], v[2])
    rx_cl = re.compile(r'(href="https://kartist\.com\.tr/kart/([a-z0-9\-]+)"(?:(?!</a>).)*?<span class="cl-price">)([^<]*)( ₺)', re.DOTALL)
    rx_ct = re.compile(r'(<td class="ct-name"><a href="https://kartist\.com\.tr/kart/([a-z0-9\-]+)">(?:(?!</tr>).)*?<td class="ct-price">)([^<]*)( ₺)', re.DOTALL)
    rx_en = re.compile(r'En değerli: .*? [\d.,]+ ₺')
    rx_chase = re.compile(r'(class="chase">⭐ En değerli kart: ).*?( [\d.,]+ ₺)(</div>)')
    # r12: "En Değerli Kartlar" tablosunu her gece YENİDEN ÜRET.
    # (Eskiden sadece fiyat rakamları yamalanıyordu; kart seçimi sayfa ilk
    #  üretildiği günden kalma ve yanlıştı — 119 sayfanın 107'si hatalıydı.)
    rx_tbody = re.compile(r'(<table class="ctable"><thead>.*?</thead><tbody>)(.*?)(</tbody></table>)', re.DOTALL)
    set_kartlari = {}
    for _sl, _v in cards.items():
        set_kartlari.setdefault(_v[5], []).append((_sl, _v[0], _v[1], _v[2]))

    def en_satirlar(kartlar, n=6):
        ust = sorted(kartlar, key=lambda x: -(x[3] or 0))[:n]
        pr = []
        for cslug, ad, num, tl in ust:
            adx = str(ad).replace('&', '&amp;').replace('<', '&lt;')
            fy = (tl_goster(tl) + ' ₺') if tl is not None else '—'
            pr.append('<tr><td class="ct-name"><a href="https://kartist.com.tr/kart/' + cslug + '">'
                      + adx + '</a></td><td class="ct-num">#' + str(num) + '</td>'
                      + '<td class="ct-price">' + fy + '</td></tr>')
        return ''.join(pr)

    say = 0
    for st in sets:
        yol = os.path.join(W, 'public', st + '.html')
        if not os.path.exists(yol): continue
        s = open(yol, encoding='utf-8').read()
        def rep(m):
            tl = slug_tl.get(m.group(2))
            return m.group(1) + (tl_goster(tl) if tl is not None else m.group(3)) + m.group(4)
        s2 = rx_cl.sub(rep, s)
        s2 = rx_ct.sub(rep, s2)
        if st in set_kartlari:
            s2 = rx_tbody.sub(lambda m: m.group(1) + en_satirlar(set_kartlari[st]) + m.group(3), s2, count=1)
        if st in enler:
            ad, tl = enler[st]
            s2 = rx_en.sub(lambda m, a=ad, t=tl: f'En değerli: {a} {tl_goster(t)} ₺', s2)
            s2 = rx_chase.sub(lambda m: m.group(1) + ad + ' ' + tl_goster(tl) + m.group(3), s2)
        if s2 != s:
            open(yol, 'w', encoding='utf-8').write(s2); say += 1
    log(f'set sayfaları: {say} dosya güncellendi')

# ── 6. Türevler: borsa.json + psa.json ───────────────────────────────────
def turevler(cards):
    liste = []
    for slug, v in cards.items():
        if v[2] is None or len(v) < 11 or v[10] is None: continue
        liste.append({'slug': slug, 'n': v[0], 'num': v[1], 'tl': v[2],
                      'sid': v[4], 'set': v[6], 'dp': v[10]})
    aday = [x for x in liste if x['tl'] >= 250 and 1.0 <= abs(x['dp']) <= 150]  # >%150 = yeniden fiyatlanma gürültüsü
    yuk = sorted(aday, key=lambda x: (-x['dp'], -x['tl']))[:20]
    dus = sorted(aday, key=lambda x: (x['dp'], -x['tl']))[:20]
    borsa = {'tarih': time.strftime('%Y-%m-%d'), 'yukselen': yuk, 'dusen': dus}
    json.dump(borsa, open(os.path.join(W, 'public', 'borsa.json'), 'w'), ensure_ascii=False)
    log(f"borsa.json: aday {len(aday)}, yükselen ilk: "
        f"{yuk[0]['n'] if yuk else '-'} %{yuk[0]['dp'] if yuk else 0}")
    # PSA aracı verisi: PSA10 fiyatı olan, anlamlı büyüklükte VE likit kartlar.
    # Likidite: veri/likidite/ham.jsonl (raw VE psa10 yılda >=2 satış → likit:1).
    # Dosya yoksa/boşsa filtre uygulanmaz (eski davranış korunur).
    likit = set()
    lyol = os.path.join(VERI, 'likidite', 'ham.jsonl')
    if os.path.exists(lyol):
        for satir in open(lyol, encoding='utf-8'):
            try:
                o = json.loads(satir)
            except ValueError:
                continue
            if o.get('likit') == 1:
                likit.add(o['slug'])
    if likit: log(f'likidite filtresi: {len(likit)} likit kart')
    psa = []
    for slug, v in cards.items():
        if len(v) < 11 or v[8] is None or v[2] is None: continue
        if v[8] < 1000: continue
        if likit and slug not in likit: continue
        psa.append([slug, v[0], v[1], v[4], v[6], v[2], v[8], v[9]])
    psa.sort(key=lambda r: -(r[6] - r[5]))
    psa = psa[:6000]
    json.dump({'tarih': time.strftime('%Y-%m-%d'), 'kartlar': psa},
              open(os.path.join(W, 'public', 'psa.json'), 'w'), ensure_ascii=False)
    log(f'psa.json: {len(psa)} kart')
    return borsa, psa


# ── 6b. Kur sabitlerini siteye enjekte et ────────────────────────────────
def kur_enjekte(kur):
    ws = open(WORKER_JS, encoding='utf-8').read()
    ws2 = re.sub(r'const KUR = [\d.]+;', f'const KUR = {kur:.4g};', ws, count=1)
    if ws2 != ws: open(WORKER_JS, 'w', encoding='utf-8').write(ws2)
    hs = open(INDEX, encoding='utf-8').read()
    hs2 = re.sub(r'var KURF = [\d.]+;', f'var KURF = {kur:.4g};', hs, count=1)
    if hs2 != hs: open(INDEX, 'w', encoding='utf-8').write(hs2)
    log(f'kur enjekte edildi: {kur:.4g}')

# ── 6c. Ana sayfa kutu satırları (Borsa + PSA) ───────────────────────────
def kutu_guncelle(borsa, psa_kartlar):
    h = open(INDEX, encoding='utf-8').read()
    def yaz(kutu_id, satirlar):
        nonlocal h
        rx = re.compile(r'(<div class="mg-mini-rows" id="' + kutu_id + r'">).*?(</div>\s*<div class="mg-b-stat)', re.DOTALL)
        assert rx.search(h), kutu_id + ' bulunamadı'
        ic = '\n          ' + '\n          '.join(satirlar) + '\n        '
        h = rx.sub(lambda m: m.group(1) + ic + m.group(2), h, count=1)
    def kisa(ad, n=19):
        return ad if len(ad) <= n else ad[:n-1] + '…'
    bs = []
    for k in borsa['yukselen'][:3]:
        bs.append(f'<div class="mg-mini-row"><span>{kisa(k["n"])}</span><b class="up">▲ %' + f'{abs(k["dp"]):.1f}'.replace('.', ',') + '</b></div>')
    for k in borsa['dusen'][:3]:
        bs.append(f'<div class="mg-mini-row"><span>{kisa(k["n"])}</span><b class="roi-neg">▼ %' + f'{abs(k["dp"]):.1f}'.replace('.', ',') + '</b></div>')
    if bs: yaz('mg-borsa-rows', bs)
    ps = []
    for r in psa_kartlar[:6]:
        fark = r[6] - r[5]
        ps.append(f'<div class="mg-mini-row"><span>{kisa(r[1] + " #" + str(r[2]), 17)}</span><b class="up">+' + tl_goster(fark) + ' ₺</b></div>')
    if ps: yaz('mg-psa-rows', ps)
    open(INDEX, 'w', encoding='utf-8').write(h)
    log(f'ana sayfa kutuları: borsa {len(bs)}, psa {len(ps)} satır')


# --- 6d. Set tamamlama verisi: setler.json ---
def setler_uret(cards):
    from collections import defaultdict
    gruplar = defaultdict(list)
    meta = {}
    for slug, v in cards.items():
        ss = v[5]
        gruplar[ss].append((slug, v[0], v[1], v[3], v[2]))   # slug, ad, num, rarity, tl
        meta[ss] = (v[6], v[7], v[4])                          # setName, year, sid
    out = []
    for ss, kartlar in gruplar.items():
        ad, yil, sid = meta[ss]
        kartlar.sort(key=lambda x: -(x[4] or 0))              # pahali ustte
        out.append({'s': ss, 'a': ad, 'y': yil, 'i': sid,
                    'k': [[k[0], k[1], k[2], k[3], k[4]] for k in kartlar]})
    out.sort(key=lambda z: sum((x[4] or 0) for x in z['k']))  # ucuzdan pahaliya
    json.dump(out, open(os.path.join(W, 'public', 'setler.json'), 'w'),
              ensure_ascii=False, separators=(',', ':'))
    log(f'setler.json: {len(out)} set, {sum(len(z["k"]) for z in out)} kart')

    # ana sayfa "Set Tamamlama" kutusu: en ucuz tamamlanan 3 set
    # (out zaten ucuzdan pahalıya sıralı — kutu her gece kendi güncellensin)
    hh = open(INDEX, encoding='utf-8').read()
    rx_sk = re.compile(r'(<div class="mg-mini-rows" id="mg-setler-rows">).*?(</div><!--/setler-rows-->)', re.DOTALL)
    if rx_sk.search(hh):
        sat = []
        for z in out[:3]:
            ad = z['a'] if len(z['a']) <= 19 else z['a'][:18] + '…'
            tp = sum((x[4] or 0) for x in z['k'])
            sat.append(f'<div class="mg-mini-row"><span>{ad}</span>'
                       f'<b class="up">{tl_goster(tp)} ₺</b></div>')
        hh = rx_sk.sub(lambda m: m.group(1) + ''.join(sat) + m.group(2), hh, count=1)
        open(INDEX, 'w', encoding='utf-8').write(hh)
        log('set tamamlama kutusu: en ucuz 3 set yazıldı')

# ── 7. Sağlamalar ────────────────────────────────────────────────────────
def kontrol():
    r = subprocess.run(['node', '--check', WORKER_JS], capture_output=True, text=True)
    assert r.returncode == 0, 'worker.js SYNTAX HATASI: ' + r.stderr[:400]
    h = open(INDEX, encoding='utf-8').read()
    bloklar = list(re.finditer(r'<script>(.*?)</script>', h, re.DOTALL))
    assert len(bloklar) == 6, f'script blok sayısı değişti: {len(bloklar)}'
    for i, sm in enumerate(bloklar):
        r = subprocess.run(['node', '--check'], input=sm.group(1), capture_output=True, text=True)
        assert r.returncode == 0, f'index blok {i} SYNTAX HATASI: ' + r.stderr[:400]
    boyut = len(gzip.compress(open(WORKER_JS, 'rb').read()))
    assert boyut < 950_000, f'worker gzip limiti aşıyor: {boyut}'
    log(f'kontroller ✓ (worker gzip {boyut/1e6:.2f}MB)')

def main():
    kur = kur_cek()
    yeni = fiyat_haritasi(kur)
    assert len(yeni) > 15000, f'fiyat haritası çok küçük ({len(yeni)}), pc_data eksik olabilir — iptal'
    cards, degisen = worker_guncelle(yeni)
    index_guncelle(yeni)
    set_sayfalari(cards)
    borsa, psa = turevler(cards)
    kur_enjekte(kur)
    kutu_guncelle(borsa, psa)
    setler_uret(cards)
    kontrol()
    log(f'BİTTİ — {degisen} kart fiyatı güncellendi')

if __name__ == '__main__':
    main()
