# sosyal_gorsel.py — "Günün Yükselenleri" paylaşım görseli (1080×1350)
# Girdi: worker/public/borsa.json  →  Çıktı: worker/public/sosyal/bugun.png
#                                      + veri/sosyal_arsiv/YYYY-AA-GG.png
import json, os, io, time, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FNT = os.path.join(KOK, 'fonts')
PUB = os.path.join(KOK, 'worker', 'public')

# Marka paleti
BG, BG1 = (13, 20, 46), (20, 27, 58)
CYAN, KREM, MERCAN = (62, 240, 238), (250, 242, 219), (255, 125, 126)
KOYU = (8, 12, 30)

def font(dosya, boyut, wght=None, ital=None):
    f = ImageFont.truetype(os.path.join(FNT, dosya), boyut)
    if wght is not None:
        try:
            eks = [ital, wght] if ital is not None else [wght]
            f.set_variation_by_axes(eks)
        except Exception:
            pass
    return f

def gradyan_yazi(draw_hedef, xy, metin, fnt, renkler, anchor='la'):
    """Logo paletli (cyan→krem→mercan) yatay gradyan yazı + koyu kontur."""
    tmp = Image.new('L', draw_hedef.size, 0)
    d = ImageDraw.Draw(tmp)
    d.text(xy, metin, font=fnt, fill=255, anchor=anchor,
           stroke_width=max(2, fnt.size // 14), stroke_fill=255)
    grad = Image.new('RGB', draw_hedef.size, renkler[0])
    gd = ImageDraw.Draw(grad)
    bbox = d.textbbox(xy, metin, font=fnt, anchor=anchor)
    x0, x1 = bbox[0], bbox[2]
    for x in range(max(0, int(x0)), min(grad.width, int(x1) + 1)):
        t = (x - x0) / max(1, (x1 - x0))
        if t < .5:
            a, b, tt = renkler[0], renkler[1], t * 2
        else:
            a, b, tt = renkler[1], renkler[2], (t - .5) * 2
        c = tuple(int(a[i] + (b[i] - a[i]) * tt) for i in range(3))
        gd.line([(x, int(bbox[1]) - 4), (x, int(bbox[3]) + 4)], fill=c)
    # kontur (arkaya koyu)
    kd = ImageDraw.Draw(draw_hedef)
    kd.text((xy[0] + 4, xy[1] + 5), metin, font=fnt, fill=KOYU, anchor=anchor,
            stroke_width=max(2, fnt.size // 14), stroke_fill=KOYU)
    draw_hedef.paste(grad, (0, 0), tmp)

def kart_gorseli(sid, num, w, h):
    try:
        url = f'https://images.pokemontcg.io/{sid}/{num}.png'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            im = Image.open(io.BytesIO(r.read())).convert('RGBA')
        im.thumbnail((w, h), Image.LANCZOS)
        return im
    except Exception:
        ph = Image.new('RGBA', (w, h), BG1 + (255,))
        d = ImageDraw.Draw(ph)
        d.rounded_rectangle([2, 2, w - 3, h - 3], 12, outline=CYAN, width=3)
        d.text((w // 2, h // 2), '?', font=font('Baloo2.ttf', h // 2, 800), fill=CYAN, anchor='mm')
        return ph

def yuvarlat(im, r):
    maske = Image.new('L', im.size, 0)
    ImageDraw.Draw(maske).rounded_rectangle([0, 0, im.width, im.height], r, fill=255)
    im.putalpha(maske)
    return im

def main():
    borsa = json.load(open(os.path.join(PUB, 'borsa.json')))
    kartlar = borsa.get('yukselen', [])[:5]
    if len(kartlar) < 3:   # gün sakinse eşiği gevşet: en değerli artanlar
        kartlar = (borsa.get('yukselen', []) + borsa.get('dusen', []))[:5]

    W, H = 1080, 1350
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    # zemin dokusu: köşe halkaları
    for cx, cy, r, renk in [(-80, -80, 340, BG1), (W + 60, H - 140, 420, BG1)]:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=renk, width=26)

    # başlık
    gradyan_yazi(img, (W // 2, 78), 'KARTİST', font('Baloo2.ttf', 96, 800),
                 [CYAN, KREM, MERCAN], anchor='ma')
    d = ImageDraw.Draw(img)
    d.text((W // 2, 208), 'GÜNÜN YÜKSELENLERİ', font=font('Quicksand.ttf', 44, 700),
           fill=KREM, anchor='ma')
    t = time.localtime()
    aylar = ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık']
    d.text((W // 2, 264), f'{t.tm_mday} {aylar[t.tm_mon-1]} {t.tm_year}',
           font=font('Nunito.ttf', 30, 600), fill=(250, 242, 219, 160), anchor='ma')

    # satırlar (sticker kutu stili)
    y0, sh, ara = 330, 178, 16
    f_ad = font('Baloo2.ttf', 40, 700)
    f_set = font('Nunito.ttf', 27, 600)
    f_tl = font('JetBrainsMono.ttf', 42, 700)
    f_pct = font('JetBrainsMono.ttf', 34, 700)
    f_sira = font('Baloo2.ttf', 46, 800)
    for i, k in enumerate(kartlar):
        y = y0 + i * (sh + ara)
        # gölge + kutu
        d.rounded_rectangle([40 + 6, y + 7, W - 40 + 6, y + sh + 7], 26, fill=KOYU)
        d.rounded_rectangle([40, y, W - 40, y + sh], 26, fill=BG1, outline=KOYU, width=4)
        # sıra rozeti
        d.ellipse([64, y + sh // 2 - 34, 132, y + sh // 2 + 34], fill=CYAN, outline=KOYU, width=4)
        d.text((98, y + sh // 2), str(i + 1), font=f_sira, fill=KOYU, anchor='mm')
        # kart görseli
        kg = kart_gorseli(k['sid'], k['num'], 108, sh - 26)
        kg = yuvarlat(kg, 10)
        img.paste(kg, (152, y + (sh - kg.height) // 2), kg)
        # metinler
        ad = k['n'] if len(k['n']) <= 22 else k['n'][:21] + '…'
        d.text((286, y + 38), ad, font=f_ad, fill=KREM, anchor='lm')
        d.text((286, y + 84), f"{k['set']} · #{k['num']}", font=f_set,
               fill=(250, 242, 219, 150), anchor='lm')
        tlm = f"{int(round(k['tl'])):,}".replace(',', '.') + ' ₺'
        d.text((286, y + 136), tlm, font=f_tl, fill=CYAN, anchor='lm')
        # yüzde rozeti
        artiyor = k['dp'] >= 0
        renk = CYAN if artiyor else MERCAN
        ok = '▲' if artiyor else '▼'
        pct = f"{ok} %{abs(k['dp']):.1f}".replace('.', ',')
        pw = d.textlength(pct, font=f_pct) + 44
        d.rounded_rectangle([W - 70 - pw, y + sh // 2 - 34, W - 70, y + sh // 2 + 34],
                            18, fill=KOYU, outline=renk, width=3)
        d.text((W - 70 - pw / 2, y + sh // 2), pct, font=f_pct, fill=renk, anchor='mm')

    # alt bant
    d.rounded_rectangle([40, H - 96, W - 40, H - 34], 20, fill=BG1, outline=KOYU, width=4)
    d.text((W // 2, H - 65), 'güncel fiyatlar · kartist.com.tr', font=font('Quicksand.ttf', 32, 700),
           fill=KREM, anchor='mm')

    os.makedirs(os.path.join(PUB, 'sosyal'), exist_ok=True)
    os.makedirs(os.path.join(KOK, 'veri', 'sosyal_arsiv'), exist_ok=True)
    img.save(os.path.join(PUB, 'sosyal', 'bugun.png'))
    img.save(os.path.join(KOK, 'veri', 'sosyal_arsiv', time.strftime('%Y-%m-%d') + '.png'))
    print('[sosyal] görsel yazıldı: sosyal/bugun.png')

if __name__ == '__main__':
    main()
