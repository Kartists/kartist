# grafik_paketle.py — veri/grafik_ham/{sid}.jsonl → worker/public/grafik/{sid}.json
# Servis formatı: {"<num>": {"u":[[YYYYAA,cent]..], "g":[..], "x":[..]}, ...}
import json, os

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAM = os.path.join(KOK, 'veri', 'grafik_ham')
CIKTI = os.path.join(KOK, 'worker', 'public', 'grafik')
os.makedirs(CIKTI, exist_ok=True)

toplam = 0
for f in sorted(os.listdir(HAM)):
    if not f.endswith('.jsonl'): continue
    sid = f[:-6]
    paket = {}
    for satir in open(os.path.join(HAM, f), encoding='utf-8'):
        try:
            d = json.loads(satir)
        except json.JSONDecodeError:
            continue
        if d.get('u') or d.get('x'):
            paket[str(d['num'])] = {'u': d['u'], 'g': d['g'], 'x': d['x']}
    if paket:
        json.dump(paket, open(os.path.join(CIKTI, sid + '.json'), 'w'), separators=(',', ':'))
        toplam += len(paket)
print(f'[paketle] {toplam} kart grafiği, {len(os.listdir(CIKTI))} set dosyası')
