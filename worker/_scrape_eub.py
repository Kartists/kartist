import urllib.request, re, json, time

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode('utf-8', errors='ignore')

def extract_jsonld(html):
    """JSON-LD'den fiyat + stok çek (9 mağaza için çalışıyor)"""
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    for block in blocks:
        if '"price"' in block or '"Offer"' in block:
            m = re.search(r'"price"\s*:\s*"?([\d.]+)', block)
            avail = re.search(r'(InStock|OutOfStock|SoldOut|Discontinued|PreOrder|BackOrder)', block)
            if m:
                price = float(m.group(1))
                stock = avail.group(1) if avail else 'InStock'
                in_stock = stock in ('InStock','PreOrder','BackOrder')
                return (round(price), in_stock)
    return (None, None)

def scrape(url):
    """Bir ürün URL'sinden fiyat + stok çek"""
    try:
        html = fetch(url)
        price, in_stock = extract_jsonld(html)
        if price:
            return {'price': price, 'inStock': in_stock, 'ok': True}
        return {'ok': False, 'reason': 'no_jsonld'}
    except Exception as e:
        return {'ok': False, 'reason': str(e)[:40]}

if __name__ == '__main__':
    # Mevcut EUB verisini yükle
    with open('eub_data.json', encoding='utf-8') as f:
        eub = json.load(f)

    total = sum(len(p['offers']) for p in eub['products'])
    print(f"Toplam {total} mağaza linki taranacak...\n")

    updated = 0
    failed = 0
    out_of_stock = 0
    price_changed = 0

    for prod in eub['products']:
        for offer in prod['offers']:
            result = scrape(offer['u'])
            if result['ok']:
                old_price = offer['p']
                new_price = result['price']
                if old_price != new_price:
                    price_changed += 1
                    print(f"  💰 {prod['set']} {prod['type']} @ {offer['s']}: ₺{old_price} → ₺{new_price}")
                offer['p'] = new_price
                offer['stock'] = result['inStock']
                if not result['inStock']:
                    out_of_stock += 1
                updated += 1
            else:
                # Çekilemedi - eski fiyatı koru, stok bilinmiyor işaretle
                offer['stock'] = None
                failed += 1
            time.sleep(0.6)  # nazik ol

    # Offer'ları fiyata göre sırala (stokta olanlar önce, sonra fiyat)
    for prod in eub['products']:
        prod['offers'].sort(key=lambda o: (0 if o.get('stock') != False else 1, o['p']))

    # Güncelleme tarihi
    from datetime import datetime
    months = ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık']
    now = datetime.now()
    eub['updated'] = f"{now.day} {months[now.month-1]} {now.year}"

    with open('eub_data_updated.json','w',encoding='utf-8') as f:
        json.dump(eub, f, ensure_ascii=False)

    print(f"\n=== SONUÇ ===")
    print(f"✓ Güncellenen: {updated}/{total}")
    print(f"⚠ Çekilemedi: {failed}")
    print(f"📉 Fiyat değişen: {price_changed}")
    print(f"❌ Stokta yok: {out_of_stock}")
    print(f"📅 Yeni tarih: {eub['updated']}")
