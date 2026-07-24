#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

SOURCE = Path("data/kanallar.json")
TARGET = Path("data/turksat_42.json")
EXPECTED_ID = "turksat_42"
EXPECTED_NAME = "Türksat 42.0°E"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    require(SOURCE.is_file(), f"Kaynak dosya bulunamadı: {SOURCE}")
    data = json.loads(SOURCE.read_text(encoding="utf-8"))

    require(isinstance(data, dict), "Türksat kaynak kökü nesne olmalı")
    require(data.get("veri_surumu") == 2, "Desteklenmeyen veri_surumu")
    require(isinstance(data.get("kanallar"), list), "kanallar listesi eksik")
    require(isinstance(data.get("transponderler"), list), "transponderler listesi eksik")
    require(data.get("toplam_kanal") == len(data["kanallar"]), "toplam_kanal uyuşmuyor")
    require(data.get("toplam_tp") == len(data["transponderler"]), "toplam_tp uyuşmuyor")

    data["konum_id"] = EXPECTED_ID
    data["konum_adi"] = EXPECTED_NAME
    data["uydu_adi"] = EXPECTED_NAME

    for tp in data["transponderler"]:
        require(isinstance(tp, dict), "Geçersiz transponder kaydı")
        tp["konum_id"] = EXPECTED_ID
        tp["konum_adi"] = EXPECTED_NAME

    for channel in data["kanallar"]:
        require(isinstance(channel, dict), "Geçersiz kanal kaydı")
        channel["konum_id"] = EXPECTED_ID
        channel["konum_adi"] = EXPECTED_NAME

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    temp = TARGET.with_suffix(TARGET.suffix + ".tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, TARGET)
    finally:
        if temp.exists():
            temp.unlink()

    print(
        f"SYNCED {SOURCE} -> {TARGET}: "
        f"kanal={len(data['kanallar'])} tp={len(data['transponderler'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
