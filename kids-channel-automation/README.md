# Mimo & Pofuduk — Günlük Çocuk Kanalı Otomasyonu

Bu proje her gün özgün bir Türkçe çocuk bölümü üretir (senaryo + AI illüstrasyon
+ seslendirme + video) ve doğrudan YouTube'a yükler. Tamamen **ücretsiz**
servislerle çalışır ve **GitHub Actions üzerinde** otomatik çalıştığı için
kendi bilgisayarınıza hiçbir şey kurmanıza gerek yoktur.

## Nasıl çalışıyor

1. Gemini (ücretsiz katman) bölümün senaryosunu ve sözlerini yazar
2. [Pollinations.ai](https://pollinations.ai) (ücretsiz, key gerekmez) her sahne için bir illüstrasyon üretir
3. `edge-tts` (ücretsiz) Türkçe seslendirmeyi oluşturur
4. `ffmpeg` görselleri pan/zoom efektiyle canlandırıp seslendirmeyle birleştirir
5. YouTube Data API videoyu kanala yükler

## Otomatik çalışma

`.github/workflows/kids-channel-daily.yml` her gün saat 10:00'da (İstanbul saati)
otomatik olarak yeni bölümü üretip yükler. İlerlemeyi deponun "Actions" sekmesinden
izleyebilirsiniz.

## İlk denemeyi elle tetikleme

Günü beklemeden test etmek için: deponun GitHub sayfasında "Actions" →
"Kids channel daily episode" → "Run workflow" tıklayın. Loglardan hatasız
geçtiğini görün, sonra YouTube kanalınızda videoyu kontrol edin. İlk
denemede videonun herkese açık yayınlanmasını istemiyorsanız workflow
dosyasındaki `PUBLISH_PRIVACY: public` satırını geçici olarak `private`
yapabilirsiniz.

## Gerekli secret'lar (GitHub → Settings → Secrets and variables → Actions)

- `GEMINI_API_KEY`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

## Güvenlik ve telif kuralları

- Korumalı karakter/marka isimleri, ninni sözleri/melodileri veya üçüncü taraf görsel/ses asla kullanılmaz
- Koddaki otomatik ön-kontrol (preflight) bilinen korumalı isimleri ve mevcut şarkı/karakterlere benzeyen istekleri durdurur — bu bir güvenlik ağıdır, hukuki garanti değildir
- Yüklenen video açıkça `madeForKids` olarak işaretlenir ve ücretli ürün yerleştirmesi içermez

## Bilinen sınırlamalar (ücretsiz yol seçildiği için)

- Görseller Pollinations.ai ile üretiliyor; Veo gibi ücretli araçlara göre karakterlerin sahneler arası görsel tutarlılığı daha zayıf olabilir
- Arka plan müziği dahil değil (telif riski almamak için) — isterseniz `music/` klasörüne kendi telifsiz (CC0) parçalarınızı ekleyebilirsiniz, ileride otomasyona eklenebilir
- Bölüm başına video ~60-120 saniye; stratejide önerilen uzun format derlemeler ve YouTube Shorts bu ilk sürümde yok, sonraki adım olarak eklenebilir

## Yerel bilgisayarda test etmek isterseniz (opsiyonel, gerekli değil)

Bu proje GitHub Actions üzerinde çalışacak şekilde tasarlandı; bilgisayarınızda
hiçbir şey kurmanıza gerek yok. Yine de yerel test etmek isterseniz Python
3.11+ ve `ffmpeg` kurulu olmalı: `.env.example` dosyasını `.env` olarak
kopyalayıp doldurun, `pip install -r requirements.txt` sonrası
`python main.py --episode 1` çalıştırın.
