import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.turksat.com.tr/uydu/yayincilik-hizmetleri/turksat-frekans-listesi"
OUTPUT_PATH = Path("data/kanallar_candidate.json")
REQUEST_TIMEOUT = 20
PAGE_DELAY_SECONDS = 1.0
POSITION_ID = "turksat_42"
POSITION_NAME = "Türksat 42.0°E"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

FILTERS = {
    # Türksat'ın resmi sitesindeki filtre sonucu nihai sınıflandırmadır.
    "HD": {"yayin": "HD", "kalite": "HD", "tur": "TV"},
    "SD": {"yayin": "SD", "kalite": "SD", "tur": "TV"},
    "4K": {"yayin": "4K", "kalite": "4K", "tur": "TV"},
    "RD": {"yayin": "RD", "kalite": "Bilinmeyen", "tur": "RADYO"},
}


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def parse_int(value: Any) -> int:
    text = clean_text(value).replace(".", "").replace(",", "")
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else 0


def normalize_pol(value: Any) -> str:
    text = clean_text(value).upper()
    if text in {"H", "HOR", "HORIZONTAL", "YATAY"}:
        return "H"
    if text in {"V", "VER", "VERTICAL", "DİKEY", "DIKEY"}:
        return "V"
    return text


def make_tp_id(freq: int, pol: str, sr: int) -> str:
    return f"{freq}_{normalize_pol(pol)}_{sr}"


def build_transponders(channels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for channel in channels:
        tp_id = channel.get("tp_id") or make_tp_id(
            parse_int(channel.get("frekans")),
            channel.get("polarizasyon", ""),
            parse_int(channel.get("sembol_orani")),
        )
        channel["tp_id"] = tp_id
        tp = grouped.setdefault(
            tp_id,
            {
                "tp_id": tp_id,
                "frekans": parse_int(channel.get("frekans")),
                "polarizasyon": normalize_pol(channel.get("polarizasyon")),
                "sembol_orani": parse_int(channel.get("sembol_orani")),
                "fec": clean_text(channel.get("fec")),
                "uydu": clean_text(channel.get("uydu")) or POSITION_NAME,
                "kapsama": clean_text(channel.get("kapsama")),
                "kanal_sayisi": 0,
                "tv_sayisi": 0,
                "radyo_sayisi": 0,
                "konum_id": POSITION_ID,
                "konum_adi": POSITION_NAME,
            },
        )
        tp["kanal_sayisi"] += 1
        if clean_text(channel.get("tur")).upper() == "RADYO":
            tp["radyo_sayisi"] += 1
        else:
            tp["tv_sayisi"] += 1

        # Aynı TP içinde boş kalan temel alanları mümkün olduğunca doldur.
        if not tp.get("fec") and channel.get("fec"):
            tp["fec"] = clean_text(channel.get("fec"))
        if not tp.get("kapsama") and channel.get("kapsama"):
            tp["kapsama"] = clean_text(channel.get("kapsama"))

    return sorted(grouped.values(), key=lambda item: (item["frekans"], item["polarizasyon"], item["sembol_orani"]))


def normalize_channel(raw: Dict[str, Any], filter_key: str, filter_settings: Dict[str, str]) -> Optional[Dict[str, Any]]:
    name = clean_text(raw.get("kanal_adi"))
    freq = parse_int(raw.get("frekans"))
    pol = normalize_pol(raw.get("polarizasyon"))
    sr = parse_int(raw.get("sembol_orani"))

    if not name or freq <= 0 or not pol or sr <= 0:
        return None

    video_pid = clean_text(raw.get("video_pid"))
    audio_pid = clean_text(raw.get("ses_pid"))
    quality = filter_settings["kalite"]
    channel_type = filter_settings["tur"]
    tp_id = make_tp_id(freq, pol, sr)

    return {
        "kanal_adi": name,
        "frekans": freq,
        "polarizasyon": pol,
        "kapsama": clean_text(raw.get("kapsama")),
        "sembol_orani": sr,
        "fec": clean_text(raw.get("fec")),
        "video_pid": video_pid,
        "ses_pid": audio_pid,
        "uydu": clean_text(raw.get("uydu")) or POSITION_NAME,
        "kalite": quality,
        "tur": channel_type,
        "tp_id": tp_id,
        "konum_id": POSITION_ID,
        "konum_adi": POSITION_NAME,
    }


def fetch_channels() -> List[Dict[str, Any]]:
    session = requests.Session()
    session.headers.update(HEADERS)
    channels_by_key: Dict[str, Dict[str, Any]] = {}

    for filter_key, settings in FILTERS.items():
        print(f"\n>>> {filter_key} yayınlar taranıyor...")
        page = 0

        while True:
            url = (
                f"{BASE_URL}?kanal=&paket=&kapsama=&uydu=&polarizasyon="
                f"&yayin={settings['yayin']}&sifreleme=&page={page}"
            )

            try:
                response = session.get(url, timeout=REQUEST_TIMEOUT)
                if response.status_code != 200:
                    print(f"Sayfa alınamadı: HTTP {response.status_code} ({filter_key}, page={page})")
                    break

                soup = BeautifulSoup(response.text, "html.parser")
                table = soup.find("table", class_="views-table")
                if not table or not table.find("tbody"):
                    break

                rows = table.find("tbody").find_all("tr")
                if not rows:
                    break

                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 10:
                        continue

                    raw_channel = {
                        "kanal_adi": cols[1].text,
                        "frekans": cols[2].text,
                        "polarizasyon": cols[3].text,
                        "kapsama": cols[4].text,
                        "sembol_orani": cols[5].text,
                        "fec": cols[6].text,
                        "video_pid": cols[7].text,
                        "ses_pid": cols[8].text,
                        "uydu": cols[9].text,
                    }
                    channel = normalize_channel(raw_channel, filter_key, settings)
                    if not channel:
                        continue

                    # SR de anahtara dahil. Aynı ad/frekans/pol ama farklı SR ihtimalinde kayıt ezilmesin.
                    channel_key = f"{channel['kanal_adi']}|{channel['frekans']}|{channel['polarizasyon']}|{channel['sembol_orani']}"
                    existing = channels_by_key.get(channel_key)
                    if not existing:
                        channels_by_key[channel_key] = channel
                        continue

                    # Aynı kayıt birden fazla resmi filtrede görünürse ilk kaynak sonucu korunur.
                    # Kanal adı, PID veya eski JSON üzerinden yeniden sınıflandırma yapılmaz.

                print(f"Sayfa {page + 1} tamamlandı...")
                page += 1
                time.sleep(PAGE_DELAY_SECONDS)

            except Exception as exc:
                print(f"Hata: {exc}")
                break

    return sorted(
        channels_by_key.values(),
        key=lambda item: (item.get("frekans", 0), item.get("polarizasyon", ""), item.get("kanal_adi", "")),
    )


def write_candidate(channels: List[Dict[str, Any]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    transponders = build_transponders(channels)
    final_data = {
        "veri_surumu": 2,
        "guncelleme_tarihi": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "uydu_adi": POSITION_NAME,
        "toplam_kanal": len(channels),
        "toplam_tp": len(transponders),
        "transponderler": transponders,
        "kanallar": channels,
        "konum_id": POSITION_ID,
        "konum_adi": POSITION_NAME,
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(final_data, file, ensure_ascii=False, indent=4)
    print(f"\nAday veri hazır: {OUTPUT_PATH} | kanal={len(channels)} tp={len(transponders)}")


def main() -> None:
    channels = fetch_channels()
    write_candidate(channels)


if __name__ == "__main__":
    main()
