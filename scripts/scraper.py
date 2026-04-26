import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime

def turksat_bot():
    base_url = "https://www.turksat.com.tr/uydu/yayincilik-hizmetleri/turksat-frekans-listesi"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # Gezeceğimiz filtreler ve bunların bizim sistemdeki karşılıkları
    filtreler = {
        "HD": {"yayin": "HD", "kalite": "HD", "tur": "TV"},
        "SD": {"yayin": "SD", "kalite": "SD", "tur": "TV"},
        "4K": {"yayin": "4K", "kalite": "4K", "tur": "TV"},
        "RD": {"yayin": "RD", "kalite": "SD", "tur": "RADYO"}
    }

    tum_kanallar = []

    for key, ayar in filtreler.items():
        print(f"\n>>> {key} yayınlar taranıyor...")
        page = 0
        
        while True:
            # Senin bulduğun URL yapısını kullanıyoruz
            url = f"{base_url}?kanal=&paket=&kapsama=&uydu=&polarizasyon=&yayin={ayar['yayin']}&sifreleme=&page={page}"
            
            try:
                response = requests.get(url, headers=headers, timeout=20)
                if response.status_code != 200:
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                table = soup.find('table', class_='views-table')
                
                if not table:
                    break

                rows = table.find('tbody').find_all('tr')
                if not rows:
                    break

                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 10:
                        kanal_verisi = {
                            "kanal_adi": cols[1].text.strip(),
                            "frekans": int(cols[2].text.strip().replace('.', '')),
                            "polarizasyon": cols[3].text.strip(),
                            "kapsama": cols[4].text.strip(),
                            "sembol_orani": int(cols[5].text.strip().replace('.', '')),
                            "fec": cols[6].text.strip(),
                            "video_pid": cols[7].text.strip(),
                            "ses_pid": cols[8].text.strip(),
                            "uydu": cols[9].text.strip(),
                            "kalite": ayar['kalite'],
                            "tur": ayar['tur']
                        }
                        tum_kanallar.append(kanal_verisi)

                print(f"Sayfa {page + 1} tamamlandı...")
                page += 1
                time.sleep(1.5) # Siteyi yormadan seri ilerliyoruz

            except Exception as e:
                print(f"Hata: {e}")
                break

    # Veriyi hazırlıyoruz
    final_data = {
        "guncelleme_tarihi": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "uydu_adi": "Türksat 42.0°E",
        "toplam_kanal": len(tum_kanallar),
        "kanallar": tum_kanallar
    }

    # JSON olarak kaydetme (data klasörünün var olduğunu varsayıyoruz)
    with open('data/kanallar.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)

    print(f"\nİşlem Başarılı! {len(tum_kanallar)} kanal 'data/kanallar.json' dosyasına kaydedildi.")

if __name__ == "__main__":
    turksat_bot()
