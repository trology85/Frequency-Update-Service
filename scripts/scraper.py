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

    # Filtreleri genişletiyoruz. Boş string ("") tüm kanalları getirir.
    filtreler = {
        "HD": {"yayin": "HD", "kalite": "HD", "tur": "TV"},
        "SD": {"yayin": "SD", "kalite": "SD", "tur": "TV"},
        "4K": {"yayin": "4K", "kalite": "4K", "tur": "TV"},
        "RD": {"yayin": "RD", "kalite": "SD", "tur": "RADYO"},
        "Tümü": {"yayin": "", "kalite": "SD", "tur": "TV"} # Diğer her şeyi yakalamak için
    }

    # Tekrar eden kanalları önlemek için bir sözlük kullanıyoruz
    # Key: (kanal_adi, frekans, polarizasyon)
    kanallar_dict = {}

    for key, ayar in filtreler.items():
        print(f"\n>>> {key} yayınlar taranıyor...")
        page = 0
        
        while True:
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
                        name = cols[1].text.strip()
                        freq = cols[2].text.strip().replace('.', '')
                        pol = cols[3].text.strip()
                        
                        # Benzersiz bir anahtar oluşturuyoruz
                        kanal_key = f"{name}_{freq}_{pol}"
                        
                        # Eğer bu kanal daha önce (örneğin HD filtresinde) eklenmediyse ekle
                        if kanal_key not in kanallar_dict:
                            # Kalite tahmini (Eğer isimde HD geçiyorsa HD yap)
                            final_kalite = ayar['kalite']
                            if "HD" in name.upper() and key == "Tümü":
                                final_kalite = "HD"
                            elif "4K" in name.upper() and key == "Tümü":
                                final_kalite = "4K"

                            kanal_verisi = {
                                "kanal_adi": name,
                                "frekans": int(freq),
                                "polarizasyon": pol,
                                "kapsama": cols[4].text.strip(),
                                "sembol_orani": int(cols[5].text.strip().replace('.', '')),
                                "fec": cols[6].text.strip(),
                                "video_pid": cols[7].text.strip(),
                                "ses_pid": cols[8].text.strip(),
                                "uydu": cols[9].text.strip(),
                                "kalite": final_kalite,
                                "tur": ayar['tur']
                            }
                            kanallar_dict[kanal_key] = kanal_verisi

                print(f"Sayfa {page + 1} tamamlandı...")
                page += 1
                time.sleep(1)

            except Exception as e:
                print(f"Hata: {e}")
                break

    # Sözlükteki değerleri listeye çeviriyoruz
    tum_kanallar = list(kanallar_dict.values())

    # Veriyi hazırlıyoruz
    final_data = {
        "guncelleme_tarihi": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "uydu_adi": "Türksat 42.0°E",
        "toplam_kanal": len(tum_kanallar),
        "kanallar": tum_kanallar
    }

    with open('data/kanallar.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)

    print(f"\nİşlem Başarılı! {len(tum_kanallar)} benzersiz kanal kaydedildi.")

if __name__ == "__main__":
    turksat_bot()
