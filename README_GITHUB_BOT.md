# Türksat Frekans Rehberi - Güvenli GitHub Bot Mimarisi

Bu paket GitHub tarafında çift kontrollü yayın mantığı kurar.

## Akış

1. `scripts/scraper.py` Türksat sayfasından bugünkü veriyi çeker.
2. Veri önce `data/kanallar_candidate.json` olarak oluşturulur.
3. `scripts/validator.py` bu aday veriyi mevcut onaylı `data/kanallar.json` ile karşılaştırır.
4. Veri güvenliyse `data/kanallar.json` güncellenir.
5. Veri şüpheliyse `data/kanallar.json` korunur ve uygulamaya yanlış veri gitmez.

## Önemli dosyalar

- `data/kanallar.json`: Uygulamanın kullandığı son onaylı veri.
- `data/kanallar_previous.json`: Bir önceki onaylı veri.
- `data/kanallar_candidate.json`: Bugünkü ham/aday veri. Workflow artifact olarak saklanır, normalde commitlenmez.
- `data/diff_report.json`: Karşılaştırma raporu.
- `data/validation_result.json`: Son kontrol sonucu.

## Koruma kuralları

- Kanal sayısı çok düşerse yayın durur.
- TP sayısı çok düşerse yayın durur.
- Radyo sayısı anormal düşerse yayın durur.
- Toplu `RADYO -> TV` dönüşümü olursa yayın durur.
- Çok fazla teknik değişiklik olursa yayın durur.
- Veri değişmediyse sadece tarih için commit oluşturulmaz.
