#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

FILES = {
    "turksat_42.json": ("turksat_42", "Türksat 42.0°E"),
    "astra_19_2.json": ("astra_19_2", "Astra 19.2°E"),
    "hotbird_13.json": ("hotbird_13", "Hot Bird 13.0°E"),
    "hellas_39.json": ("hellas_39", "Hellas Sat 39.0°E"),
}

REQUIRED_CHANNEL = {
    "kanal_adi", "frekans", "polarizasyon", "sembol_orani", "uydu",
    "kalite", "tur", "tp_id", "konum_id", "konum_adi"
}
REQUIRED_TP = {
    "tp_id", "frekans", "polarizasyon", "sembol_orani", "uydu",
    "kanal_sayisi", "tv_sayisi", "radyo_sayisi", "konum_id", "konum_adi"
}


def validate(path: Path, expected_id: str, expected_name: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("veri_surumu") == 2, f"veri_surumu: {path}"
    assert data.get("konum_id") == expected_id, f"konum_id: {path}"
    assert data.get("konum_adi") == expected_name, f"konum_adi: {path}"
    channels = data.get("kanallar")
    tps = data.get("transponderler")
    assert isinstance(channels, list), f"kanallar: {path}"
    assert isinstance(tps, list), f"transponderler: {path}"
    assert data.get("toplam_kanal") == len(channels), f"toplam_kanal: {path}"
    assert data.get("toplam_tp") == len(tps), f"toplam_tp: {path}"

    tp_ids = set()
    for index, tp in enumerate(tps):
        missing = REQUIRED_TP - set(tp)
        assert not missing, f"TP alan eksik {path} #{index}: {sorted(missing)}"
        assert tp["konum_id"] == expected_id and tp["konum_adi"] == expected_name
        assert tp["tp_id"], f"Boş tp_id {path} #{index}"
        tp_ids.add(tp["tp_id"])

    for index, ch in enumerate(channels):
        missing = REQUIRED_CHANNEL - set(ch)
        assert not missing, f"Kanal alan eksik {path} #{index}: {sorted(missing)}"
        assert ch["konum_id"] == expected_id and ch["konum_adi"] == expected_name
        assert ch["kanal_adi"], f"Boş kanal adı {path} #{index}"
        assert ch["tp_id"] in tp_ids, f"Geçersiz tp_id {path} #{index}: {ch['tp_id']}"
        assert ch["tur"] in {"TV", "RADYO"}, f"Geçersiz tür {path} #{index}"
        if ch["tur"] == "TV":
            assert ch["kalite"] in {"SD", "HD", "4K", "4K/UHD", "Bilinmeyen"}

    print(f"VALID {path.name}: kanal={len(channels)} tp={len(tps)}")


def main() -> int:
    data_dir = Path("data")
    for filename, (position_id, position_name) in FILES.items():
        validate(data_dir / filename, position_id, position_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
