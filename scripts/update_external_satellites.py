#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "external_satellites.json"
PIPELINE_DIR = ROOT / "external_pipeline"
STATE_DIR = PIPELINE_DIR / "state"
REPORT_DIR = ROOT / "reports" / "external"
DATA_DIR = ROOT / "data"

PIPELINE_STEPS = [
    "fetch_satbeams.py",
    "fetch_kingofsat.py",
    "parse_kingofsat.py",
    "parse_satbeams.py",
    "enrich_satbeams_quality.py",
    "validate_satbeams.py",
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    temp.replace(path)


def load_converter():
    module_path = ROOT / "scripts" / "import_pilot_satellites.py"
    spec = importlib.util.spec_from_file_location("satellite_converter", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Dönüştürücü modül yüklenemedi")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_workspace(base: Path, sat: dict[str, Any]) -> None:
    for name in ("scripts", "config", "raw/satbeams", "raw/kingofsat", "candidate/satbeams", "output/satbeams", "output", "reports"):
        (base / name).mkdir(parents=True, exist_ok=True)

    for script in PIPELINE_STEPS:
        shutil.copy2(PIPELINE_DIR / "scripts" / script, base / "scripts" / script)

    satbeams_cfg = [{
        "id": sat["id"],
        "name": sat["name"],
        "position": sat["position"],
        "position_label": sat["position_label"],
        "minimum_channels": sat["minimum_channels"],
        "minimum_transponders": sat["minimum_transponders"],
        "max_unknown_quality_ratio": sat["max_unknown_quality_ratio"],
    }]
    king_cfg = [{
        "id": sat["id"],
        "name": sat["kingofsat_name"],
        "position": sat["kingofsat_position"],
        "url": sat["kingofsat_url"],
    }]
    write_json(base / "config" / "satbeams_satellites.json", satbeams_cfg)
    write_json(base / "config" / "kingofsat_satellites.json", king_cfg)

    current_state = STATE_DIR / f"{sat['id']}.json"
    if current_state.exists():
        shutil.copy2(current_state, base / "output" / "satbeams" / current_state.name)


def run_step(workspace: Path, script_name: str, log_file) -> None:
    command = [sys.executable, str(workspace / "scripts" / script_name)]
    process = subprocess.run(
        command,
        cwd=workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=420,
        check=False,
    )
    log_file.write(f"\n===== {script_name} =====\n")
    log_file.write(process.stdout)
    log_file.flush()
    if process.returncode != 0:
        raise RuntimeError(f"{script_name} başarısız, kod={process.returncode}")


def publish_satellite(workspace: Path, sat: dict[str, Any], converter) -> dict[str, Any]:
    state_candidate = workspace / "output" / "satbeams" / f"{sat['id']}.json"
    source = load_json(state_candidate)
    converter.validate_source(source, state_candidate)
    document = converter.build_document(source, sat["id"], sat["name"])

    output_path = DATA_DIR / f"{sat['id']}.json"
    converter.write_json(output_path, document)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(state_candidate, STATE_DIR / state_candidate.name)

    return {
        "channels": document["toplam_kanal"],
        "transponders": document["toplam_tp"],
        "output": str(output_path.relative_to(ROOT)),
        "state": str((STATE_DIR / state_candidate.name).relative_to(ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", default=[], help="Yalnız belirtilen uydu id")
    parser.add_argument("--validate-state-only", action="store_true", help="Ağa çıkmadan mevcut state dosyalarını üretim şemasına dönüştür")
    args = parser.parse_args()

    satellites = load_json(CONFIG_PATH)
    if args.only:
        allowed = set(args.only)
        satellites = [sat for sat in satellites if sat["id"] in allowed]
    if not satellites:
        raise SystemExit("İşlenecek uydu bulunamadı")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    converter = load_converter()
    report = {
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "ok": True,
        "successful": 0,
        "failed": 0,
        "satellites": [],
    }

    for sat in satellites:
        item = {"id": sat["id"], "name": sat["name"], "ok": False, "errors": []}
        log_path = REPORT_DIR / f"{sat['id']}.log"
        try:
            if args.validate_state_only:
                state = STATE_DIR / f"{sat['id']}.json"
                if not state.exists():
                    raise FileNotFoundError(state)
                source = load_json(state)
                converter.validate_source(source, state)
                document = converter.build_document(source, sat["id"], sat["name"])
                converter.write_json(DATA_DIR / f"{sat['id']}.json", document)
                item.update({"channels": document["toplam_kanal"], "transponders": document["toplam_tp"]})
            else:
                with tempfile.TemporaryDirectory(prefix=f"sat-{sat['id']}-") as temp_dir:
                    workspace = Path(temp_dir)
                    prepare_workspace(workspace, sat)
                    with log_path.open("w", encoding="utf-8") as log_file:
                        for script_name in PIPELINE_STEPS:
                            run_step(workspace, script_name, log_file)
                    item.update(publish_satellite(workspace, sat, converter))
            item["ok"] = True
            report["successful"] += 1
        except Exception as exc:
            item["errors"].append(f"{type(exc).__name__}: {exc}")
            report["failed"] += 1
            report["ok"] = False
        report["satellites"].append(item)
        print(json.dumps(item, ensure_ascii=False))

    write_json(REPORT_DIR / "update_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # Tek uydu hatası diğer geçerli uyduların yayınlanmasını engellemez.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
