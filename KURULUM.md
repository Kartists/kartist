# Kartist — Kurulum Kılavuzu

Bu dosya, otomasyonun GitHub üzerinde her gece kendi kendine çalışması için
senin yapman gereken **tek seferlik** adımları anlatır. Toplam ~15 dakika sürer.

---

## 1) GitHub'da özel (private) bir repo aç

1. github.com → sağ üstte **+** → **New repository**
2. İsim: `kartist` (istediğin bir isim de olabilir)
3. **Private** seçili olsun
4. "Create repository" — boş repo yeterli, README ekleme

## 2) Bu klasörün içeriğini o repoya yükle

En kolay yol: GitHub Desktop veya web arayüzü.

**Web arayüzünden (kod bilmeden):**
1. Az önce açtığın repo sayfasında **"uploading an existing file"** linkine tıkla
2. `kartist-repo.zip` dosyasını önce kendi bilgisayarında bir klasöre çıkart (sağ tık → "Tümünü Ayıkla" / "Extract All")
3. Çıkan klasördeki **tüm dosya ve klasörleri** (`.github` klasörü dahil — bazen gizli görünür, "gizli dosyaları göster" gerekebilir) GitHub'daki yükleme alanına sürükle-bırak yap
4. Alt kısımda "Commit changes" yeşil butonuna bas

> **Önemli:** `.github/workflows/` klasörünün de yüklendiğinden emin ol. Bazı
> zip programları nokta ile başlayan klasörleri gizler — eğer görünmüyorsa,
> dosya gezgininde "gizli öğeleri göster" ayarını aç.

## 3) Cloudflare bilgilerini al

Worker'ın zaten bir Cloudflare hesabında yayında olduğunu varsayıyorum
(kartist.com.tr için). İki bilgiye ihtiyacın var:

**a) CLOUDFLARE_API_TOKEN**
1. dash.cloudflare.com → sağ üstte profil ikonu → **My Profile**
2. Sol menüden **API Tokens**
3. **Create Token** → **Edit Cloudflare Workers** şablonunu seç (Use template)
4. Hesabını ve gerekirse zone'unu seçip **Continue to summary** → **Create Token**
5. Çıkan uzun kodu kopyala (bir daha gösterilmeyecek, kaybetme)

**b) CLOUDFLARE_ACCOUNT_ID**
1. dash.cloudflare.com ana sayfasında, sağ tarafta **Account ID** yazan
   kutucuk var (Workers & Pages sayfasına girince de sağ altta görünür)
2. Kopyala

## 4) Bu iki bilgiyi GitHub'a "Secret" olarak ekle

1. Repo sayfasında **Settings** (dişli simgesi) → sol menüde
   **Secrets and variables** → **Actions**
2. **New repository secret**
   - Name: `CLOUDFLARE_API_TOKEN` → Value: (adım 3a'da kopyaladığın kod) → Add secret
3. Tekrar **New repository secret**
   - Name: `CLOUDFLARE_ACCOUNT_ID` → Value: (adım 3b'de kopyaladığın kod) → Add secret

## 5) Actions'ı etkinleştir ve ilk çalıştırmayı elle tetikle

1. Repo sayfasında üst menüden **Actions** sekmesine tıkla
2. Eğer bir uyarı çıkarsa **"I understand my workflows, go ahead and enable them"** de
3. Sol tarafta **"Gece Guncelleme"** workflow'unu seç
4. Sağ tarafta **"Run workflow"** butonuna bas → tekrar yeşil **Run workflow**
5. ~15-30 dakika sürecek (tam fiyat çekimi olduğu için). Yeşil tik ✅ görünce
   siteni kontrol et — fiyatlar, borsa ve PSA kutuları güncellenmiş olacak

Bundan sonra bu adım gerekmez: her gece TR saatiyle 03:00'te otomatik çalışır.

## 6) "Grafik Backfill" kendiliğinden işler, dokunma

`.github/workflows/backfill.yml` günde 7 kez otomatik çalışıp kartların
geçmiş fiyat grafiklerini yavaş yavaş tamamlar (~17.800 kart, GitHub'ın
saatlik çalışma sınırları yüzünden birkaç gün sürer). **Bittiğinde kendi
kendini siler** — bir gün Actions sekmesinde bu workflow'u göremezsen,
işi bitmiş demektir, hiçbir şey yapmana gerek yok.

---

## Bundan sonra her şey otomatik

Her gece sırasıyla şunlar olur, senin hiçbir şey yapmana gerek kalmadan:

- 121 setin güncel fiyatları PriceCharting'den çekilir
- Sitedeki tüm kart fiyatları (worker + ana sayfa + 119 set sayfası) TL'ye
  çevrilip yeniden yazılır
- Kart Borsası (günün yükselen/düşen kartları) ve PSA Kârlılık verisi
  yeniden hesaplanır
- En Ucuzu Bul fiyatları 79 mağaza linkinden tazelenir
- Günün yükselenleri görseli üretilir (`sosyal/bugun.png`) — paylaşım için
  indirip kullanabilirsin
- Site otomatik olarak Cloudflare'e yayınlanır (deploy)
- Değişiklikler repoya "gece guncelleme: TARIH" commit'i olarak kaydedilir
  (bu sayede geçmiş fiyatları GitHub'ın commit geçmişinden de görebilirsin)

## Senin elle yapman gerekenler (otomasyon dışı — devir teslim v9, Görev 5A)

Bunlar kod/otomasyon değil, insan/topluluk işleri olduğu için otomatikleştirilemedi:
- Günlük sosyal medya paylaşımı (görsel otomatik üretiliyor, paylaşmak sana kalıyor)
- Çekiliş/topluluk etkileşimi
- Yeni set çıkışlarını `worker/src/worker.js` içindeki `SETS`/`CARDS`'a elle eklemek
  (yeni bir set çıktığında; bu konuda ayrıca yardımcı olabilirim, yeter ki söyle)

## Bir şey ters giderse

- **Actions sekmesinde kırmızı ✗ görürsen:** o satıra tıkla, hangi adımda
  hata verdiği loglarda yazar. Genellikle geçici bir ağ hatasıdır, bir
  sonraki gece kendi kendine düzelir. Israrla tekrarlıyorsa logu bana yapıştır.
- **Fiyatlar güncellenmemiş görünüyorsa:** Actions sekmesinde son "Gece
  Guncelleme" koşusunun yeşil tik aldığını kontrol et.
- **Secrets'ı yanlış girdiysen:** Settings → Secrets and variables → Actions'tan
  üzerine tıklayıp güncelleyebilirsin, silmene gerek yok.
