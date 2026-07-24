#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CHANNEL_TECH_FIELDS = (
    "kanal_adi", "frekans", "polarizasyon", "sembol_orani", "fec",
    "video_pid", "ses_pid", "kalite", "tur", "sid", "paket",
    "tp_id", "kapsama",
)
TP_FIELDS = (
    "frekans", "polarizasyon", "sembol_orani", "fec", "uydu", "kapsama",
    "kanal_sayisi", "tv_sayisi", "radyo_sayisi",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def channel_key(item: dict[str, Any]) -> str:
    position = _text(item.get("konum_id"))
    tp_id = _text(item.get("tp_id"))
    sid = _text(item.get("sid"))
    if tp_id and sid:
        return f"{position}|{tp_id}|sid:{sid}"
    return "|".join((
        position,
        _text(item.get("frekans")),
        _text(item.get("polarizasyon")).upper(),
        _text(item.get("sembol_orani")),
        _text(item.get("kanal_adi")).casefold(),
        _text(item.get("tur")).upper(),
    ))


def tp_key(item: dict[str, Any]) -> str:
    tp_id = _text(item.get("tp_id"))
    if tp_id:
        return tp_id
    return "|".join((
        _text(item.get("konum_id")),
        _text(item.get("frekans")),
        _text(item.get("polarizasyon")).upper(),
        _text(item.get("sembol_orani")),
    ))


def _index(items: list[dict[str, Any]], key_func) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict):
            result[key_func(item)] = item
    return result


def _changes(old: dict[str, Any], new: dict[str, Any], fields: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    changed: dict[str, dict[str, Any]] = {}
    for field in fields:
        if old.get(field) != new.get(field):
            changed[field] = {"onceki": old.get(field), "yeni": new.get(field)}
    return changed


def build_diff(previous: dict[str, Any] | None, current: dict[str, Any], satellite_id: str, satellite_name: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    if previous is None:
        return {
            "uydu_id": satellite_id,
            "uydu_adi": satellite_name,
            "olusturma_zamani_utc": now,
            "ilk_yayin": True,
            "degisiklik_var": True,
            "ozet": {
                "onceki_kanal": 0,
                "yeni_kanal": len(current.get("kanallar", [])),
                "eklenen_kanal": len(current.get("kanallar", [])),
                "silinen_kanal": 0,
                "degisen_kanal": 0,
                "tur_degisen_kanal": 0,
                "onceki_tp": 0,
                "yeni_tp": len(current.get("transponderler", [])),
                "eklenen_tp": len(current.get("transponderler", [])),
                "silinen_tp": 0,
                "degisen_tp": 0,
            },
            "eklenen_kanallar": current.get("kanallar", []),
            "silinen_kanallar": [],
            "degisen_kanallar": [],
            "eklenen_transponderler": current.get("transponderler", []),
            "silinen_transponderler": [],
            "degisen_transponderler": [],
        }

    old_channels = _index(previous.get("kanallar", []), channel_key)
    new_channels = _index(current.get("kanallar", []), channel_key)
    old_tps = _index(previous.get("transponderler", []), tp_key)
    new_tps = _index(current.get("transponderler", []), tp_key)

    added_channels = [new_channels[k] for k in sorted(new_channels.keys() - old_channels.keys())]
    removed_channels = [old_channels[k] for k in sorted(old_channels.keys() - new_channels.keys())]
    changed_channels = []
    type_changed = 0
    for key in sorted(old_channels.keys() & new_channels.keys()):
        changes = _changes(old_channels[key], new_channels[key], CHANNEL_TECH_FIELDS)
        if changes:
            if "tur" in changes:
                type_changed += 1
            changed_channels.append({
                "anahtar": key,
                "kanal_adi": new_channels[key].get("kanal_adi") or old_channels[key].get("kanal_adi"),
                "degisiklikler": changes,
            })

    added_tps = [new_tps[k] for k in sorted(new_tps.keys() - old_tps.keys())]
    removed_tps = [old_tps[k] for k in sorted(old_tps.keys() - new_tps.keys())]
    changed_tps = []
    for key in sorted(old_tps.keys() & new_tps.keys()):
        changes = _changes(old_tps[key], new_tps[key], TP_FIELDS)
        if changes:
            changed_tps.append({"anahtar": key, "degisiklikler": changes})

    changed = any((added_channels, removed_channels, changed_channels, added_tps, removed_tps, changed_tps))
    return {
        "uydu_id": satellite_id,
        "uydu_adi": satellite_name,
        "olusturma_zamani_utc": now,
        "ilk_yayin": False,
        "degisiklik_var": changed,
        "ozet": {
            "onceki_kanal": len(old_channels),
            "yeni_kanal": len(new_channels),
            "eklenen_kanal": len(added_channels),
            "silinen_kanal": len(removed_channels),
            "degisen_kanal": len(changed_channels),
            "tur_degisen_kanal": type_changed,
            "onceki_tp": len(old_tps),
            "yeni_tp": len(new_tps),
            "eklenen_tp": len(added_tps),
            "silinen_tp": len(removed_tps),
            "degisen_tp": len(changed_tps),
        },
        "eklenen_kanallar": added_channels,
        "silinen_kanallar": removed_channels,
        "degisen_kanallar": changed_channels,
        "eklenen_transponderler": added_tps,
        "silinen_transponderler": removed_tps,
        "degisen_transponderler": changed_tps,
    }
