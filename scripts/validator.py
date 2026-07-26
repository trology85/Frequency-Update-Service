import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

APPROVED_PATH = Path("data/kanallar.json")
PREVIOUS_PATH = Path("data/kanallar_previous.json")
CANDIDATE_PATH = Path("data/kanallar_candidate.json")
DIFF_REPORT_PATH = Path("data/diff_report.json")
VALIDATION_RESULT_PATH = Path("data/validation_result.json")
ENV_PATH = Path("data/update_result.env")
POSITION_ID = "turksat_42"
POSITION_NAME = "Türksat 42.0°E"

MIN_CHANNELS = 300
MIN_TRANSPONDERS = 30
MAX_CHANNEL_DROP_RATIO = 0.18
MAX_TRANSPONDER_DROP_RATIO = 0.18
MAX_REMOVED_CHANNELS_WITHOUT_BLOCK = 80
MAX_TYPE_CHANGES_WITHOUT_BLOCK = 8
MAX_RADIO_TO_TV_WITHOUT_BLOCK = 2
MAX_RADIO_DROP_RATIO = 0.30
MAX_TECHNICAL_CHANGES_WITHOUT_BLOCK = 150
MAX_QUALITY_CHANGES_WITHOUT_WARNING = 300

RADIO_NAME_PATTERNS = (" FM", "FM ", "RADYO", "RADIO", "RADIOS", "RADIYO")
MISSING_PID_VALUES = {"", "-", "--", "0", "000", "N/A", "YOK", "NONE", "NULL"}
COMPARE_FIELDS = [
    "kanal_adi",
    "frekans",
    "polarizasyon",
    "sembol_orani",
    "fec",
    "video_pid",
    "ses_pid",
    "uydu",
    "kalite",
    "tur",
    "tp_id",
    "konum_id",
    "konum_adi",
]
TECHNICAL_FIELDS = [
    "frekans",
    "polarizasyon",
    "sembol_orani",
    "fec",
    "video_pid",
    "ses_pid",
    "kalite",
    "tur",
    "tp_id",
    "konum_id",
    "konum_adi",
]


def now_text() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def parse_int(value: Any) -> int:
    text = clean_text(value).replace(".", "").replace(",", "")
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else 0


def normalize_name(value: Any) -> str:
    text = clean_text(value).upper()
    text = text.replace("İ", "I").replace("İ", "I")
    text = re.sub(r"[^A-Z0-9ÇĞÖŞÜ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_pol(value: Any) -> str:
    text = clean_text(value).upper()
    if text in {"H", "HOR", "HORIZONTAL", "YATAY"}:
        return "H"
    if text in {"V", "VER", "VERTICAL", "DİKEY", "DIKEY"}:
        return "V"
    return text


def is_missing_pid(value: Any) -> bool:
    return clean_text(value).upper() in MISSING_PID_VALUES


def has_radio_name_hint(name: str) -> bool:
    upper = f" {clean_text(name).upper()} "
    return any(pattern in upper for pattern in RADIO_NAME_PATTERNS)


def make_tp_id(freq: int, pol: str, sr: int) -> str:
    return f"{freq}_{normalize_pol(pol)}_{sr}"


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def normalize_type(channel: Dict[str, Any]) -> str:
    current = clean_text(channel.get("tur")).upper()
    video_missing = is_missing_pid(channel.get("video_pid"))
    audio_present = not is_missing_pid(channel.get("ses_pid"))
    if current == "RADYO" or (video_missing and audio_present):
        return "RADYO"
    return "TV"


def normalize_quality(channel: Dict[str, Any]) -> str:
    current = clean_text(channel.get("kalite")).upper()
    if current in {"4K", "UHD", "4K/UHD", "UHD/4K"}:
        return "4K"
    if current in {"SD", "HD"}:
        return current
    return "Bilinmeyen"


def normalize_channel(channel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = clean_text(channel.get("kanal_adi") or channel.get("Kanal"))
    freq = parse_int(channel.get("frekans") or channel.get("Frekans"))
    pol = normalize_pol(channel.get("polarizasyon") or channel.get("Pol"))
    sr = parse_int(channel.get("sembol_orani") or channel.get("SR"))
    if not name or freq <= 0 or not pol or sr <= 0:
        return None

    normalized = dict(channel)
    normalized["kanal_adi"] = name
    normalized["frekans"] = freq
    normalized["polarizasyon"] = pol
    normalized["sembol_orani"] = sr
    normalized["kapsama"] = clean_text(channel.get("kapsama") or channel.get("Kapsama"))
    normalized["fec"] = clean_text(channel.get("fec") or channel.get("FEC"))
    normalized["video_pid"] = clean_text(channel.get("video_pid") or channel.get("Video PID"))
    normalized["ses_pid"] = clean_text(channel.get("ses_pid") or channel.get("Ses PID"))
    normalized["uydu"] = clean_text(channel.get("uydu") or channel.get("Uydu")) or POSITION_NAME
    normalized["kalite"] = normalize_quality(normalized)
    normalized["tur"] = normalize_type(normalized)
    normalized["tp_id"] = clean_text(channel.get("tp_id")) or make_tp_id(freq, pol, sr)
    normalized["konum_id"] = clean_text(channel.get("konum_id")) or POSITION_ID
    normalized["konum_adi"] = clean_text(channel.get("konum_adi")) or POSITION_NAME
    return {field: normalized.get(field, "") for field in COMPARE_FIELDS + ["kapsama"]}


def normalize_dataset(data: Dict[str, Any]) -> Dict[str, Any]:
    channels: List[Dict[str, Any]] = []
    seen = set()
    for raw in data.get("kanallar", []) or []:
        channel = normalize_channel(raw)
        if not channel:
            continue
        key = (
            normalize_name(channel["kanal_adi"]),
            channel["frekans"],
            channel["polarizasyon"],
            channel["sembol_orani"],
        )
        if key in seen:
            continue
        seen.add(key)
        channels.append(channel)

    channels = sorted(channels, key=lambda item: (item["frekans"], item["polarizasyon"], item["kanal_adi"]))
    transponders = build_transponders(channels)
    return {
        "veri_surumu": 2,
        "guncelleme_tarihi": clean_text(data.get("guncelleme_tarihi")) or now_text(),
        "uydu_adi": clean_text(data.get("uydu_adi")) or POSITION_NAME,
        "toplam_kanal": len(channels),
        "toplam_tp": len(transponders),
        "transponderler": transponders,
        "kanallar": channels,
        "konum_id": clean_text(data.get("konum_id")) or POSITION_ID,
        "konum_adi": clean_text(data.get("konum_adi")) or POSITION_NAME,
    }


def build_transponders(channels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for channel in channels:
        tp_id = clean_text(channel.get("tp_id")) or make_tp_id(channel["frekans"], channel["polarizasyon"], channel["sembol_orani"])
        tp = grouped.setdefault(
            tp_id,
            {
                "tp_id": tp_id,
                "frekans": channel["frekans"],
                "polarizasyon": channel["polarizasyon"],
                "sembol_orani": channel["sembol_orani"],
                "fec": channel.get("fec", ""),
                "uydu": channel.get("uydu", POSITION_NAME),
                "kapsama": channel.get("kapsama", ""),
                "kanal_sayisi": 0,
                "tv_sayisi": 0,
                "radyo_sayisi": 0,
                "konum_id": clean_text(channel.get("konum_id")) or POSITION_ID,
                "konum_adi": clean_text(channel.get("konum_adi")) or POSITION_NAME,
            },
        )
        tp["kanal_sayisi"] += 1
        if channel.get("tur") == "RADYO":
            tp["radyo_sayisi"] += 1
        else:
            tp["tv_sayisi"] += 1
    return sorted(grouped.values(), key=lambda item: (item["frekans"], item["polarizasyon"], item["sembol_orani"]))


def content_signature(data: Dict[str, Any]) -> str:
    comparable = {
        "kanallar": sorted(
            [{field: channel.get(field, "") for field in COMPARE_FIELDS} for channel in data.get("kanallar", [])],
            key=lambda item: (item.get("kanal_adi", ""), item.get("frekans", 0), item.get("polarizasyon", "")),
        )
    }
    raw = json.dumps(comparable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_identity_maps(old_channels: List[Dict[str, Any]], new_channels: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    all_channels = old_channels + new_channels
    name_counts = Counter((normalize_name(ch["kanal_adi"]), clean_text(ch.get("uydu"))) for ch in all_channels)

    def identity(channel: Dict[str, Any]) -> str:
        name_key = (normalize_name(channel["kanal_adi"]), clean_text(channel.get("uydu")))
        if name_counts[name_key] <= 2:
            return f"NAME|{name_key[0]}|{name_key[1]}"
        return (
            f"FULL|{name_key[0]}|{name_key[1]}|{channel.get('frekans')}|"
            f"{channel.get('polarizasyon')}|{channel.get('sembol_orani')}"
        )

    return ({identity(ch): ch for ch in old_channels}, {identity(ch): ch for ch in new_channels})


def compare_datasets(old_data: Optional[Dict[str, Any]], new_data: Dict[str, Any]) -> Dict[str, Any]:
    if not old_data:
        return {
            "added_channels": [short_channel(ch) for ch in new_data.get("kanallar", [])[:50]],
            "removed_channels": [],
            "technical_changes": [],
            "quality_changes": [],
            "non_quality_technical_changes": [],
            "added_transponders": [tp.get("tp_id") for tp in new_data.get("transponderler", [])],
            "removed_transponders": [],
            "type_changes": [],
            "summary": {
                "old_channel_count": 0,
                "new_channel_count": new_data.get("toplam_kanal", 0),
                "old_tp_count": 0,
                "new_tp_count": new_data.get("toplam_tp", 0),
                "old_radio_count": 0,
                "new_radio_count": count_type(new_data, "RADYO"),
                "old_tv_count": 0,
                "new_tv_count": count_type(new_data, "TV"),
            },
        }

    old_map, new_map = build_identity_maps(old_data.get("kanallar", []), new_data.get("kanallar", []))
    old_keys = set(old_map)
    new_keys = set(new_map)

    added = [short_channel(new_map[key]) for key in sorted(new_keys - old_keys)[:200]]
    removed = [short_channel(old_map[key]) for key in sorted(old_keys - new_keys)[:200]]

    technical_changes = []
    quality_changes = []
    non_quality_technical_changes = []
    type_changes = []
    for key in sorted(old_keys & new_keys):
        old = old_map[key]
        new = new_map[key]
        changed_fields = {}
        for field in TECHNICAL_FIELDS:
            if old.get(field) != new.get(field):
                changed_fields[field] = {"old": old.get(field), "new": new.get(field)}
        if changed_fields:
            entry = {
                "kanal_adi": new.get("kanal_adi") or old.get("kanal_adi"),
                "changes": changed_fields,
            }
            technical_changes.append(entry)
            if set(changed_fields) == {"kalite"}:
                quality_changes.append(entry)
            else:
                non_quality_technical_changes.append(entry)
            if "tur" in changed_fields:
                type_changes.append(entry)

    old_tps = {tp.get("tp_id") for tp in old_data.get("transponderler", [])}
    new_tps = {tp.get("tp_id") for tp in new_data.get("transponderler", [])}

    return {
        "added_channels": added,
        "removed_channels": removed,
        "technical_changes": technical_changes[:300],
        "quality_changes": quality_changes[:300],
        "non_quality_technical_changes": non_quality_technical_changes[:300],
        "added_transponders": sorted(new_tps - old_tps),
        "removed_transponders": sorted(old_tps - new_tps),
        "type_changes": type_changes[:200],
        "summary": {
            "old_channel_count": old_data.get("toplam_kanal", len(old_data.get("kanallar", []))),
            "new_channel_count": new_data.get("toplam_kanal", len(new_data.get("kanallar", []))),
            "old_tp_count": old_data.get("toplam_tp", len(old_data.get("transponderler", []))),
            "new_tp_count": new_data.get("toplam_tp", len(new_data.get("transponderler", []))),
            "old_radio_count": count_type(old_data, "RADYO"),
            "new_radio_count": count_type(new_data, "RADYO"),
            "old_tv_count": count_type(old_data, "TV"),
            "new_tv_count": count_type(new_data, "TV"),
        },
    }


def short_channel(channel: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kanal_adi": channel.get("kanal_adi"),
        "frekans": channel.get("frekans"),
        "polarizasyon": channel.get("polarizasyon"),
        "sembol_orani": channel.get("sembol_orani"),
        "tur": channel.get("tur"),
        "kalite": channel.get("kalite"),
        "tp_id": channel.get("tp_id"),
    }


def count_type(data: Dict[str, Any], channel_type: str) -> int:
    return sum(1 for channel in data.get("kanallar", []) if channel.get("tur") == channel_type)


def radio_to_tv_count(diff: Dict[str, Any]) -> int:
    count = 0
    for entry in diff.get("type_changes", []):
        change = entry.get("changes", {}).get("tur")
        if change and change.get("old") == "RADYO" and change.get("new") == "TV":
            count += 1
    return count


def validate(old_data: Optional[Dict[str, Any]], new_data: Dict[str, Any], diff: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    summary = diff.get("summary", {})

    new_channel_count = summary.get("new_channel_count", 0)
    new_tp_count = summary.get("new_tp_count", 0)
    if new_channel_count < MIN_CHANNELS:
        errors.append(f"Kanal sayısı çok düşük: {new_channel_count} < {MIN_CHANNELS}")
    if new_tp_count < MIN_TRANSPONDERS:
        errors.append(f"TP sayısı çok düşük: {new_tp_count} < {MIN_TRANSPONDERS}")

    # İlk yayınsa temel eşiklerden geçtiği sürece izin ver.
    if not old_data:
        return len(errors) == 0, errors, warnings

    old_channel_count = max(1, summary.get("old_channel_count", 0))
    old_tp_count = max(1, summary.get("old_tp_count", 0))
    old_radio_count = max(1, summary.get("old_radio_count", 0))
    new_radio_count = summary.get("new_radio_count", 0)

    channel_drop_ratio = (old_channel_count - new_channel_count) / old_channel_count
    tp_drop_ratio = (old_tp_count - new_tp_count) / old_tp_count
    radio_drop_ratio = (old_radio_count - new_radio_count) / old_radio_count

    if channel_drop_ratio > MAX_CHANNEL_DROP_RATIO:
        errors.append(f"Kanal sayısı anormal düştü: %{channel_drop_ratio * 100:.1f}")
    if tp_drop_ratio > MAX_TRANSPONDER_DROP_RATIO:
        errors.append(f"TP sayısı anormal düştü: %{tp_drop_ratio * 100:.1f}")
    if radio_drop_ratio > MAX_RADIO_DROP_RATIO:
        errors.append(f"Radyo sayısı anormal düştü: %{radio_drop_ratio * 100:.1f}")

    removed_count = len(diff.get("removed_channels", []))
    if removed_count > MAX_REMOVED_CHANNELS_WITHOUT_BLOCK:
        errors.append(f"Bir çalışmada çok fazla kanal silinmiş görünüyor: {removed_count}")

    type_change_count = len(diff.get("type_changes", []))
    if type_change_count > MAX_TYPE_CHANGES_WITHOUT_BLOCK:
        errors.append(f"Çok fazla TV/RADYO tür değişimi var: {type_change_count}")

    rtv_count = radio_to_tv_count(diff)
    if rtv_count > MAX_RADIO_TO_TV_WITHOUT_BLOCK:
        errors.append(f"Şüpheli RADYO -> TV dönüşümü var: {rtv_count}")
    elif rtv_count > 0:
        warnings.append(f"Az sayıda RADYO -> TV dönüşümü var, kontrol önerilir: {rtv_count}")

    quality_count = len(diff.get("quality_changes", []))
    non_quality_technical_count = len(diff.get("non_quality_technical_changes", []))

    # Kalite alanı kaynak filtre/format bilgisinden yeniden üretilebilir. Bu nedenle
    # yalnız kalite değişiklikleri, frekans/PID/tür gibi gerçek teknik değişikliklerin
    # güvenlik eşiğini tüketmez. Yine de toplu kalite değişimleri raporlanır.
    if quality_count > MAX_QUALITY_CHANGES_WITHOUT_WARNING:
        warnings.append(f"Toplu kalite normalizasyonu var: {quality_count}")

    if non_quality_technical_count > MAX_TECHNICAL_CHANGES_WITHOUT_BLOCK:
        errors.append(
            "Kalite dışı teknik değişiklik sayısı anormal yüksek: "
            f"{non_quality_technical_count}"
        )

    return len(errors) == 0, errors, warnings


def write_env(should_publish: bool, status: str) -> None:
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENV_PATH.write_text(
        f"SHOULD_PUBLISH={'true' if should_publish else 'false'}\n"
        f"VALIDATION_STATUS={status}\n",
        encoding="utf-8",
    )


def main() -> None:
    candidate_raw = load_json(CANDIDATE_PATH)
    if candidate_raw is None:
        result = {
            "checked_at": now_text(),
            "status": "blocked",
            "errors": [f"Aday veri bulunamadı: {CANDIDATE_PATH}"],
            "warnings": [],
        }
        write_json(VALIDATION_RESULT_PATH, result)
        write_env(False, "blocked")
        print(result["errors"][0])
        return

    approved_raw = load_json(APPROVED_PATH)
    candidate = normalize_dataset(candidate_raw)
    approved = normalize_dataset(approved_raw) if approved_raw else None

    diff = compare_datasets(approved, candidate)
    is_safe, errors, warnings = validate(approved, candidate, diff)
    old_signature = content_signature(approved) if approved else ""
    new_signature = content_signature(candidate)

    report = {
        "checked_at": now_text(),
        "status": "pending",
        "safe": is_safe,
        "errors": errors,
        "warnings": warnings,
        "old_signature": old_signature,
        "new_signature": new_signature,
        "diff": diff,
    }

    if not is_safe:
        report["status"] = "blocked"
        write_json(DIFF_REPORT_PATH, report)
        write_json(VALIDATION_RESULT_PATH, report)
        write_env(False, "blocked")
        print("VALIDATION BLOCKED")
        for error in errors:
            print(f" - {error}")
        return

    if approved and old_signature == new_signature:
        report["status"] = "no_change"
        write_json(DIFF_REPORT_PATH, report)
        write_json(VALIDATION_RESULT_PATH, report)
        write_env(False, "no_change")
        print("Değişiklik yok. kanallar.json korunuyor.")
        return

    candidate["guncelleme_tarihi"] = now_text()
    if APPROVED_PATH.exists():
        PREVIOUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(APPROVED_PATH, PREVIOUS_PATH)

    report["status"] = "published"
    write_json(APPROVED_PATH, candidate)
    write_json(DIFF_REPORT_PATH, report)
    write_json(VALIDATION_RESULT_PATH, report)
    write_env(True, "published")
    print(f"VALIDATION OK - yayınlandı. Kanal={candidate['toplam_kanal']} TP={candidate['toplam_tp']}")


if __name__ == "__main__":
    main()
