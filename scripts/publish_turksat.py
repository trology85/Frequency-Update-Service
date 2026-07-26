#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

CANDIDATE = Path("data/kanallar_candidate.json")
PUBLISHED = Path("data/kanallar.json")
PREVIOUS = Path("data/kanallar_previous.json")
SATELLITE = Path("data/turksat_42.json")
ENV_FILE = Path("data/update_result.env")


def atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def main() -> int:
    if not CANDIDATE.is_file():
        raise FileNotFoundError(f"Aday Türksat dosyası bulunamadı: {CANDIDATE}")

    data = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    # Türksat'ın resmi filtreli çıktısı doğrudan yayınlanır.
    # İsim/PID tahmini, eski-yeni kıyaslaması veya ikinci doğrulama yapılmaz.
    if PUBLISHED.is_file():
        shutil.copy2(PUBLISHED, PREVIOUS)

    atomic_write(PUBLISHED, data)
    atomic_write(SATELLITE, data)

    ENV_FILE.write_text(
        "SHOULD_PUBLISH=true\nVALIDATION_STATUS=published\n",
        encoding="utf-8",
    )

    print(
        "TÜRKSAT VERİSİ DOĞRUDAN YAYINLANDI - "
        f"kanal={data.get('toplam_kanal', len(data.get('kanallar', [])))} "
        f"tp={data.get('toplam_tp', len(data.get('transponderler', [])))}"
    )
    print("SHOULD_PUBLISH=true")
    print("VALIDATION_STATUS=published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
