#!/usr/bin/env python3
"""Convert validated satellite-frequency-pilot outputs to app production schema.

The script intentionally writes one JSON file per orbital position. It does not
merge all satellites into one large physical JSON file.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SATELLITES = {
    "astra_19_2": {
        "name": "Astra 19.2°E",
        "input": "astra_19_2.json",
        "output": "astra_19_2.json",
    },
    "hotbird_13": {
        "name": "Hot Bird 13.0°E",
        "input": "hotbird_13.json",
        "output": "hotbird_13.json",
    },
    "hellas_39": {
        "name": "Hellas Sat 39.0°E",
        "input": "hellas_39.json",
        "output": "hellas_39.json",
    },
    "azerspace_46": {
        "name": "Azerspace-1 46.0°E",
        "input": "azerspace_46.json",
        "output": "azerspace_46.json",
    },
    "eutelsat_16": {
        "name": "Eutelsat 16A 16.0°E",
        "input": "eutelsat_16.json",
        "output": "eutelsat_16.json",
    },
    "astra_23_5": {
        "name": "Astra 3B/3C 23.5°E",
        "input": "astra_23_5.json",
        "output": "astra_23_5.json",
    },
    "astra_28_2": {
        "name": "Astra 2E/2F/2G 28.2°E",
        "input": "astra_28_2.json",
        "output": "astra_28_2.json",
    },
    "thor_1w": {
        "name": "Thor 5/6/7 / Intelsat 10-02 0.8°W",
        "input": "thor_1w.json",
        "output": "thor_1w.json",
    },
    "turkmenalem_52": {
        "name": "TurkmenÄlem / MonacoSat 52.0°E",
        "input": "turkmenalem_52.json",
        "output": "turkmenalem_52.json",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Kök nesne olmalı: {path}")
    return data


def as_pid(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_quality(channel: dict[str, Any]) -> str:
    channel_type = str(channel.get("type") or "").upper()
    if channel_type == "RADIO":
        return ""
    raw = str(channel.get("quality") or "UNKNOWN").strip().upper()
    if raw in {"4K", "UHD", "UHD/4K", "4K/UHD"}:
        return "4K"
    if raw in {"SD", "HD"}:
        return raw
    return "Bilinmeyen"


def normalize_type(value: Any) -> str:
    raw = str(value or "").strip().upper()
    return "RADYO" if raw == "RADIO" else "TV"


def convert_tp(tp: dict[str, Any], position_id: str, position_name: str) -> dict[str, Any]:
    return {
        "tp_id": str(tp.get("tp_id") or "").strip(),
        "frekans": tp.get("frequency"),
        "polarizasyon": str(tp.get("polarization") or "").strip(),
        "sembol_orani": tp.get("symbol_rate"),
        "fec": str(tp.get("fec") or "").strip(),
        "uydu": str(tp.get("spacecraft") or "Belirtilmemiş").strip() or "Belirtilmemiş",
        "kapsama": str(tp.get("beam") or "").strip(),
        "kanal_sayisi": int(tp.get("channel_count") or 0),
        "tv_sayisi": int(tp.get("tv_count") or 0),
        "radyo_sayisi": int(tp.get("radio_count") or 0),
        "konum_id": position_id,
        "konum_adi": position_name,
    }


def convert_channel(ch: dict[str, Any], position_id: str, position_name: str) -> dict[str, Any]:
    return {
        "kanal_adi": str(ch.get("name") or "").strip(),
        "frekans": ch.get("frequency"),
        "polarizasyon": str(ch.get("polarization") or "").strip(),
        "sembol_orani": ch.get("symbol_rate"),
        "fec": str(ch.get("fec") or "").strip(),
        "video_pid": as_pid(ch.get("vpid")),
        "ses_pid": as_pid(ch.get("audio")),
        "uydu": str(ch.get("spacecraft") or "Belirtilmemiş").strip() or "Belirtilmemiş",
        "kalite": normalize_quality(ch),
        "tur": normalize_type(ch.get("type")),
        "sid": as_pid(ch.get("sid")),
        "paket": str(ch.get("package") or ch.get("provider") or "").strip(),
        "tp_id": str(ch.get("tp_id") or "").strip(),
        "konum_id": position_id,
        "konum_adi": position_name,
        "kapsama": str(ch.get("beam") or "").strip(),
    }


def validate_source(data: dict[str, Any], path: Path) -> None:
    if not isinstance(data.get("channels"), list):
        raise ValueError(f"channels listesi yok: {path}")
    if not isinstance(data.get("transponders"), list):
        raise ValueError(f"transponders listesi yok: {path}")


def build_document(data: dict[str, Any], position_id: str, position_name: str) -> dict[str, Any]:
    channels = [
        convert_channel(item, position_id, position_name)
        for item in data["channels"]
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    transponders = [
        convert_tp(item, position_id, position_name)
        for item in data["transponders"]
        if isinstance(item, dict) and str(item.get("tp_id") or "").strip()
    ]
    channels.sort(key=lambda item: (item["kanal_adi"].casefold(), item.get("frekans") or 0))
    transponders.sort(key=lambda item: (item.get("frekans") or 0, item.get("polarizasyon") or ""))

    generated = data.get("generated_utc")
    if not generated:
        generated = datetime.now(timezone.utc).isoformat()

    return {
        "veri_surumu": 2,
        "guncelleme_tarihi": str(generated),
        "uydu_adi": position_name,
        "toplam_kanal": len(channels),
        "toplam_tp": len(transponders),
        "transponderler": transponders,
        "kanallar": channels,
        "konum_id": position_id,
        "konum_adi": position_name,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-dir", required=True, type=Path,
                        help="Pilot output/satbeams klasörü")
    parser.add_argument("--data-dir", default=Path("data"), type=Path,
                        help="Üretim data klasörü")
    args = parser.parse_args()

    for position_id, cfg in SATELLITES.items():
        source_path = args.pilot_dir / cfg["input"]
        source = load_json(source_path)
        validate_source(source, source_path)
        document = build_document(source, position_id, cfg["name"])
        output_path = args.data_dir / cfg["output"]
        write_json(output_path, document)
        print(f"OK {output_path}: kanal={document['toplam_kanal']} tp={document['toplam_tp']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
