# Çoklu uydu veri düzeni

Üretim reposunda her orbital konum ayrı JSON dosyasıdır:

- `data/turksat_42.json`
- `data/astra_19_2.json`
- `data/hotbird_13.json`
- `data/hellas_39.json`
- `data/azerspace_46.json`

Mevcut uygulama sürümleri bozulmasın diye `data/kanallar.json` şimdilik Türksat
uyumluluk dosyası olarak korunur. Uygulamanın çoklu uydu sürümü uydu dosyalarını
ayrı ayrı indirir ve uygulama içinde tek mantıksal listede kullanır.

Pilot verileri üretim şemasına dönüştürmek için:

```bash
python scripts/import_pilot_satellites.py \
  --pilot-dir /path/to/satellite-frequency-pilot/output/satbeams \
  --data-dir data
python scripts/validate_satellite_files.py
```

Dönüştürme geçici dosyaya yazıp tamamlanınca hedef dosyanın üzerine atomik olarak
geçer. Uydular tek büyük fiziksel JSON dosyasına birleştirilmez.
