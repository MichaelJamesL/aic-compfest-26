#!/usr/bin/env python3
"""Regenerate the demo CSVs, with timestamps relative to *now*.

    backend/.venv/bin/python demo-data/make_demo_data.py

Run it with an interpreter that can import `ai-engine/src` (numpy, pydantic):
the sensor series are verified with the engine's own `detect_anomalies` and
`health_score`, in both modes the backend can score them — the per-batch IQR
fence, and the robust-z baseline fitted by POST /assets/{id}/baseline. A demo
where the sick machines do not light up, or the healthy ones do, fails here
instead of on stage.

Sensor data for the two mills is real: UCI AI4I 2020 Predictive Maintenance
Dataset (cached in source/ai4i2020.csv). The rest is synthetic, built to match
the machine on its nameplate: currents follow the motor rating, the pump's flow
sits at its duty point, thresholds come from the manuals shipped in docs/.
"""
from __future__ import annotations

import csv
import io
import json
import random
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "ai-engine"))

from src import baseline, config as engine_config  # noqa: E402
from src.schemas import Asset as EngineAsset, MaintenanceRecord as EngineRecord, SensorReading  # noqa: E402
from src.signals import detect_anomalies, health_score  # noqa: E402

AI4I_URL = "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip"
SOURCE = HERE / "source" / "ai4i2020.csv"
NOW = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

# 5 days of hourly readings per tag. The baseline is fitted on all of it; the
# analyzer scores the newest ANALYSIS_LIMIT rows, which is where the fault sits.
POINTS = 120
ANALYSIS_LIMIT = 200  # mirrors run_analysis() in backend/app/analysis/service.py


# --- machines -------------------------------------------------------------
# Every nameplate here is a real product, and every machine that fails in this
# demo has a manual in docs/ that covers it.

ASSETS = [
    {
        "external_id": "CNC-MILL-01", "name": "Mesin Milling Bridgeport Series I #1",
        "asset_type": "cnc_mill", "criticality": "high", "location": "Lini Machining A",
        "specs": {"manufacturer": "Bridgeport", "model": "Series I Standard Mill",
                  "spindle_power_kw": 1.5, "installed": "2019-03-11",
                  "max_process_temp_c": 40, "max_torque_nm": 65,
                  "tool_life_min": 200, "maintenance_interval_days": 60},
    },
    {
        "external_id": "CNC-MILL-02", "name": "Mesin Milling Bridgeport Series I #2",
        "asset_type": "cnc_mill", "criticality": "high", "location": "Lini Machining A",
        "specs": {"manufacturer": "Bridgeport", "model": "Series I Standard Mill",
                  "spindle_power_kw": 1.5, "installed": "2020-08-02",
                  "max_process_temp_c": 40, "max_torque_nm": 65,
                  "tool_life_min": 200, "maintenance_interval_days": 60},
    },
    {
        "external_id": "PUMP-01", "name": "Pompa Air Pendingin Utama",
        "asset_type": "pump", "criticality": "high", "location": "Utilitas - Cooling Tower",
        "specs": {"manufacturer": "Grundfos", "model": "NK 80-250", "motor_power_kw": 30,
                  "installed": "2018-06-20", "duty_flow_m3h": 120, "duty_head_m": 32,
                  "shaft_diameter_mm": 48,
                  "bearing_de": "double angular contact, SKF 3306 A-2Z",
                  "bearing_nde": "roller bearing, SKF 6306-2Z",
                  "relubrication_hours": 3500, "grease_g_per_bearing": 38,
                  "max_bearing_temp_c": 85, "max_vibration_mm_s": 4.5,
                  "maintenance_interval_days": 90},
    },
    {
        "external_id": "COMP-01", "name": "Kompresor Udara Sekrup 55 kW",
        "asset_type": "compressor", "criticality": "high", "location": "Ruang Utilitas",
        "specs": {"manufacturer": "OPPAIR", "model": "oil-injected screw, 55 kW",
                  "motor_power_kw": 55, "installed": "2017-11-04",
                  "rated_pressure_bar": 7.5, "max_oil_temp_c": 95,
                  "max_filter_dp_bar": 0.5, "maintenance_interval_days": 90},
    },
    {
        "external_id": "MOTOR-01", "name": "Motor Induksi 30 kW Konveyor Utama",
        "asset_type": "motor", "criticality": "medium", "location": "Lini Perakitan B",
        "specs": {"manufacturer": "ABB", "model": "M3BP 200MLA 4", "motor_power_kw": 30,
                  "installed": "2021-01-15", "rated_current_a": 55, "rated_speed_rpm": 1475,
                  "insulation_class": "F", "max_winding_temp_c": 105,
                  "max_vibration_mm_s": 3.5, "maintenance_interval_days": 120},
    },
    {
        "external_id": "CONV-01", "name": "Konveyor Sabuk Lini Perakitan",
        "asset_type": "conveyor", "criticality": "medium", "location": "Lini Perakitan B",
        "specs": {"manufacturer": "Interroll", "model": "belt conveyor 1100",
                  "belt_width_mm": 800, "drive_power_kw": 5.5, "installed": "2021-01-15",
                  "maintenance_interval_days": 120},
    },
    {
        "external_id": "PRESS-01", "name": "Mesin Press Hidrolik 100 Ton",
        "asset_type": "press", "criticality": "high", "location": "Lini Stamping",
        "specs": {"manufacturer": "Yangli", "model": "YL32-100", "capacity_ton": 100,
                  "installed": "2016-09-30", "rated_pressure_bar": 250,
                  "max_oil_temp_c": 60, "maintenance_interval_days": 90},
    },
    {
        "external_id": "CHILL-01", "name": "Chiller Air-Cooled 80 TR",
        "asset_type": "chiller", "criticality": "medium", "location": "Utilitas - Rooftop",
        "specs": {"manufacturer": "Trane", "model": "CGAM 080", "capacity_tr": 80,
                  "refrigerant": "R-410A", "installed": "2019-12-01",
                  "maintenance_interval_days": 180},
    },
]


# --- real sensor data: UCI AI4I 2020 --------------------------------------

def ai4i_rows() -> list[dict]:
    if not SOURCE.exists():
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(AI4I_URL, timeout=60) as response:
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
        SOURCE.write_bytes(archive.read("ai4i2020.csv"))
    return list(csv.DictReader(io.StringIO(SOURCE.read_text(encoding="utf-8-sig"))))


AI4I_TAGS = {
    "air_temp_c": ("Air temperature [K]", "C", lambda v: round(v - 273.15, 1)),
    "process_temp_c": ("Process temperature [K]", "C", lambda v: round(v - 273.15, 1)),
    "spindle_speed_rpm": ("Rotational speed [rpm]", "rpm", lambda v: round(v)),
    "torque_nm": ("Torque [Nm]", "Nm", lambda v: round(v, 1)),
}
# AI4I's tool-wear column is per cycle with a fresh tool each row, so exporting
# it as a PLC tag would read as a counter that resets at random. Tool life is an
# operator rule in IK-CNC-003 instead.


def mill_rows(external_id: str, block: list[dict]) -> list[dict]:
    """One machining cycle every 30 minutes, oldest first."""
    start = NOW - timedelta(minutes=30 * len(block))
    return [
        reading(external_id, tag, convert(float(row[column])), unit,
                start + timedelta(minutes=30 * i), i)
        for i, row in enumerate(block)
        for tag, (column, unit, convert) in AI4I_TAGS.items()
    ]


def mill_history(external_id: str) -> list[EngineRecord]:
    return [EngineRecord(asset_id=external_id, performed_at=NOW - timedelta(days=days),
                         action=action, findings=findings)
            for asset, days, action, findings, _ in HISTORY if asset == external_id]


def mill_verdict(block: list[dict], external_id: str) -> tuple[int, list[str]]:
    """Score a candidate block the way the backend would: baseline fitted on the
    whole block, anomalies read off the analysis window."""
    rows = mill_rows(external_id, block)
    window = to_readings(analysis_window(rows))
    baseline.fit(external_id, to_readings(rows))
    anomalies = detect_anomalies(window, external_id)
    spec = next(a for a in ASSETS if a["external_id"] == external_id)
    asset = EngineAsset(id=external_id, name=spec["name"], type=spec["asset_type"],
                        criticality=spec["criticality"], specs=spec["specs"])
    score, _ = health_score(asset, anomalies, mill_history(external_id), now=NOW)
    return score, sorted(a.tag for a in anomalies)


# One machine runs one job, not 10,000 unrelated ones. AI4I samples independent
# cycles across products and settings, so a single failure is invisible against
# that spread — the run is narrowed to type L cycles inside one operating band.
# The measured tuples are untouched; only which cycles this machine ran is ours.
MILL_REGIME = {"type": "L", "rpm": (1400, 1700), "torque": (30.0, 50.0)}


def in_regime(row: dict) -> bool:
    low_rpm, high_rpm = MILL_REGIME["rpm"]
    low_torque, high_torque = MILL_REGIME["torque"]
    return (row["Type"] == MILL_REGIME["type"]
            and low_rpm <= float(row["Rotational speed [rpm]"]) <= high_rpm
            and low_torque <= float(row["Torque [Nm]"]) <= high_torque)


def mill_blocks(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """(failing, healthy). The failing run ends in real heat-dissipation failure
    cycles — the mode IK-CNC-003 describes: the spindle slows and the process
    heat stops being carried away. The healthy run is the same machine, same
    job, no failure labelled anywhere in it.
    """
    steady = [row for row in rows if row["Machine failure"] == "0" and in_regime(row)]
    if len(steady) < 2 * POINTS:
        raise SystemExit("not enough steady AI4I cycles for two mills")
    # The worst real HDF cycles of this product type, ending with the slowest.
    failing_cycles = sorted(
        (row for row in rows if row["HDF"] == "1" and row["Type"] == MILL_REGIME["type"]),
        key=lambda row: -float(row["Rotational speed [rpm]"]),
    )[-3:]
    failing = steady[:POINTS - len(failing_cycles)] + failing_cycles
    healthy = steady[POINTS:2 * POINTS]

    score, tags = mill_verdict(failing, "CNC-MILL-01")
    if score >= 85 or not tags:
        raise SystemExit(f"failing mill block is not convincing: score {score}, flags {tags}")
    if mill_verdict(healthy, "CNC-MILL-02")[1]:
        raise SystemExit("healthy mill block flags an anomaly")
    print(f"  AI4I: failing mill score {score}, flags {tags}")
    return failing, healthy


# --- synthetic sensor data ------------------------------------------------

def reading(external_id, tag, value, unit, recorded_at, i) -> dict:
    return {
        "tag": tag, "value": value, "unit": unit,
        "recorded_at": recorded_at.isoformat().replace("+00:00", "Z"),
        "source": "plc_export", "external_id": f"{external_id}-{tag}-{i:03d}",
    }


def quiet(values: list[float], window: int) -> bool:
    """True when neither detector has anything to say about these values —
    checked over the same window the analyzer reads, in both modes."""
    readings = as_readings({"probe": values})
    if flagged_tags(readings[-window:]):
        return False
    baseline.fit("probe", readings)
    return not flagged_tags(readings[-window:], "probe")


def series(level: float, noise: float, tail: list[float] | None, window: int) -> list[float]:
    """Steady level plus noise, with `tail` grafted on the end. Noise alone must
    never trip a detector — otherwise a healthy machine shows up red — so a draw
    that does is redrawn."""
    body = POINTS - len(tail or [])
    for _ in range(500):
        values = [round(level + random.gauss(0, noise), 2) for _ in range(body)]
        if tail or quiet(values, window):
            return values + list(tail or [])
    raise SystemExit(f"noise too wide for a clean series at level {level}")


def synth_rows(external_id: str, tags: dict) -> list[dict]:
    """tags: tag -> (unit, level, noise, tail). The tail is the fault."""
    start = NOW - timedelta(hours=POINTS)
    window = ANALYSIS_LIMIT // len(tags)  # points per tag the analyzer sees
    return [
        reading(external_id, tag, value, unit, start + timedelta(hours=i), i)
        for tag, (unit, level, noise, tail) in tags.items()
        for i, value in enumerate(series(level, noise, tail, window))
    ]


SYNTHETIC = {
    # Bearing running away: hot and loud, and the flow starts to drop with it.
    # 62 C / 2.6 mm/s is a healthy 30 kW NK 80-250 at its duty point.
    "PUMP-01": {
        "bearing_temp_c": ("C", 62.0, 1.2, [74.8, 84.1, 92.6]),
        "vibration_mm_s": ("mm/s", 2.6, 0.25, [4.4, 6.3, 8.1]),
        "flow_m3h": ("m3/h", 118.0, 2.0, [107.5, 99.4, 94.2]),
        "motor_current_a": ("A", 48.0, 0.9, [49.4, 49.8, 50.2]),
    },
    # Clogged air filter: pressure drop climbs, oil temperature follows, the
    # motor pulls harder and the network still loses pressure.
    "COMP-01": {
        "discharge_pressure_bar": ("bar", 7.4, 0.08, [7.30, 7.25, 7.20]),
        "oil_temp_c": ("C", 78.0, 1.5, [88.4, 96.1, 101.5]),
        "air_filter_dp_bar": ("bar", 0.22, 0.02, [0.41, 0.53, 0.64]),
        "motor_current_a": ("A", 96.0, 1.4, [97.9, 98.6, 99.3]),
    },
    # One vibration spike on an otherwise healthy motor: the "watch it" case.
    "MOTOR-01": {
        "winding_temp_c": ("C", 71.0, 1.6, None),
        "vibration_mm_s": ("mm/s", 1.7, 0.15, [1.8, 3.9, 2.2]),
        "current_a": ("A", 47.0, 1.1, None),
        "speed_rpm": ("rpm", 1478.0, 4.0, None),
    },
    "CONV-01": {
        "belt_speed_mps": ("m/s", 0.85, 0.02, None),
        "drive_current_a": ("A", 10.8, 0.4, None),
        "roller_temp_c": ("C", 41.0, 1.3, None),
        "vibration_mm_s": ("mm/s", 1.2, 0.12, None),
    },
    "PRESS-01": {
        "hydraulic_pressure_bar": ("bar", 182.0, 2.5, None),
        "oil_temp_c": ("C", 52.0, 1.4, None),
        "cycle_time_s": ("s", 8.4, 0.15, None),
        "ram_position_mm": ("mm", 248.0, 0.6, None),
    },
    # R-410A condensing near 45 C, ~90 kW drawn at 400 V for 80 TR.
    "CHILL-01": {
        "chw_supply_temp_c": ("C", 7.2, 0.3, None),
        "condenser_pressure_bar": ("bar", 27.4, 0.6, None),
        "compressor_current_a": ("A", 143.0, 3.0, None),
        "approach_temp_c": ("C", 1.4, 0.2, None),
    },
}

DEGRADED = {"PUMP-01", "COMP-01", "CNC-MILL-01", "MOTOR-01"}

# Parts a vendor brings with the job, deliberately not warehouse stock. Anything
# else used in HISTORY must exist in INVENTORY, or the story stops adding up.
NON_STOCK = {"airend-bearing-set", "gasket-set"}


# --- maintenance history --------------------------------------------------
# (asset, days ago, action, findings, parts used). Part codes match INVENTORY
# and the SOPs in docs/.
HISTORY = [
    ("PUMP-01", 400, "Overhaul tahunan pompa", "Impeller aus ringan, seal mekanik diganti", "seal-mekanik-nk80,gasket-set"),
    ("PUMP-01", 300, "Pelumasan ulang bearing bracket (3500 jam)", "Grease lama mengeras, bearing DE bersih", "grease-mobil-polyrex-em"),
    ("PUMP-01", 210, "Penggantian bearing DE", "Bearing DE berisik, clearance di luar batas", "skf-3306-a2z"),
    ("PUMP-01", 140, "Preventive maintenance 3 bulanan", "Alignment kopling ulang, getaran turun ke 2.4 mm/s", "coupling-insert"),
    ("PUMP-01", 22, "Inspeksi getaran tidak terjadwal", "Bearing DE panas berlebih (>85 C)", ""),
    ("PUMP-01", 9, "Inspeksi getaran tidak terjadwal", "Bearing DE panas berlebih (>85 C)", ""),
    ("CNC-MILL-01", 380, "Overhaul spindle", "Bearing spindle diganti sepasang, runout 0.008 mm", "spindle-bearing-set"),
    ("CNC-MILL-01", 260, "Kalibrasi sumbu X-Y-Z", "Backlash sumbu Y 0.03 mm, dikompensasi di kontroler", ""),
    ("CNC-MILL-01", 175, "Ganti oli way lube dan filter", "Level oli way lube rendah, saluran Z tersumbat", "way-lube-iso68"),
    ("CNC-MILL-01", 95, "Preventive maintenance 2 bulanan", "Coolant diganti, filter chip bersih, tool holder diperiksa", "coolant-concentrate,filter-chip"),
    ("CNC-MILL-01", 34, "Perbaikan sistem pendingin spindle", "Radiator pendingin kotor, suhu proses naik saat beban tinggi", ""),
    ("CNC-MILL-02", 410, "Instalasi ulang dan leveling mesin", "Leveling ulang setelah pemindahan lini", ""),
    ("CNC-MILL-02", 240, "Ganti oli way lube dan filter", "Normal, tidak ada temuan", "way-lube-iso68"),
    ("CNC-MILL-02", 120, "Kalibrasi sumbu X-Y-Z", "Semua sumbu dalam toleransi 0.01 mm", ""),
    ("CNC-MILL-02", 45, "Preventive maintenance 2 bulanan", "Coolant diganti, tidak ada temuan", "coolant-concentrate"),
    ("COMP-01", 365, "Overhaul airend", "Bearing airend diganti, clearance rotor dalam batas", "airend-bearing-set"),
    ("COMP-01", 280, "Ganti oli kompresor dan filter oli", "Oli menghitam lebih cepat dari jadwal", "oli-kompresor-46,filter-oli"),
    ("COMP-01", 190, "Ganti elemen filter udara", "Delta P filter 0.48 bar mendekati batas", "elemen-filter-udara"),
    ("COMP-01", 100, "Preventive maintenance 3 bulanan", "Separator diganti, drain trap dibersihkan", "separator-element"),
    ("COMP-01", 30, "Pembersihan cooler dan drain", "Cooler tersumbat debu, suhu oli turun 6 C setelah dibersihkan", ""),
    ("MOTOR-01", 330, "Rewinding motor", "Isolasi belitan turun, motor di-rewind di vendor", ""),
    ("MOTOR-01", 200, "Pelumasan ulang bearing motor", "Normal", "grease-mobil-polyrex-em"),
    ("MOTOR-01", 80, "Pengukuran tahanan isolasi", "IR 120 Mohm, aman", ""),
    ("MOTOR-01", 26, "Pengencangan kembali dudukan motor", "Baut dudukan kendor, getaran 3.6 mm/s sebelum perbaikan", ""),
    ("CONV-01", 300, "Ganti sabuk konveyor", "Sabuk retak di sambungan", "belt-800mm"),
    ("CONV-01", 180, "Ganti roller idler", "Dua roller macet", "roller-idler"),
    ("CONV-01", 60, "Preventive maintenance 2 bulanan", "Tracking sabuk disetel, pelumasan bearing roller", "grease-mobil-polyrex-em"),
    ("PRESS-01", 420, "Ganti seal silinder hidrolik", "Kebocoran pada seal rod, oli menetes", "seal-kit-100t"),
    ("PRESS-01", 310, "Ganti oli hidrolik dan filter", "Partikel logam halus di filter", "oli-hidrolik-iso46,filter-hidrolik"),
    ("PRESS-01", 150, "Kalibrasi pressure switch", "Setpoint bergeser 4 bar", ""),
    ("PRESS-01", 70, "Preventive maintenance 3 bulanan", "Cycle time 8.4 s, dalam batas", ""),
    ("PRESS-01", 18, "Inspeksi kebocoran hidrolik", "Rembes kecil pada fitting, dikencangkan", ""),
    ("CHILL-01", 350, "Cleaning kondensor tahunan", "Fin kondensor kotor berat", "coil-cleaner"),
    ("CHILL-01", 200, "Top-up refrigerant", "Tekanan rendah, ditemukan rembes di flare", "refrigerant-r410a"),
    ("CHILL-01", 90, "Preventive maintenance 6 bulanan", "Approach temp 1.3 C, normal", ""),
]


# --- factory-wide business context ----------------------------------------
# PUT /api/v1/business-context takes shifts, roster and warehouse in one call;
# operator reports are per machine, via PUT /assets/{id}/condition.

SHIFT = {"start": "07:00", "end": "23:00"}
DAY_SHIFT = {"start": "07:00", "end": "15:00"}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

BUSINESS_CONTEXT = {
    # Two shifts Monday-Friday; Saturday morning is the maintenance window.
    "production_schedule": {
        "work_time": {**{day: SHIFT for day in WEEKDAYS}, "saturday": DAY_SHIFT},
    },
    "technicians": [
        {
            "name": "Budi Santoso", "role": "teknisi mekanik", "specialty": "rotating equipment",
            "work_time": {**{day: DAY_SHIFT for day in WEEKDAYS}, "saturday": DAY_SHIFT},
            "occupied_time": {"wednesday": [{"start": "08:00", "end": "12:00"}]},
        },
        {
            "name": "Rian Pratama", "role": "teknisi mekanik", "specialty": "hidrolik dan pneumatik",
            "work_time": {day: {"start": "15:00", "end": "23:00"} for day in WEEKDAYS},
            "occupied_time": {},
        },
        {
            "name": "Sari Wulandari", "role": "teknisi listrik", "specialty": "motor dan kontrol",
            "work_time": {**{day: DAY_SHIFT for day in WEEKDAYS},
                          "saturday": {"start": "07:00", "end": "12:00"}},
            "occupied_time": {"friday": [{"start": "13:00", "end": "15:00"}]},
        },
    ],
    # `asset_external_ids` is resolved to real asset ids by seed.py.
    "inventory": [
        {"id": "skf-3306-a2z", "name": "Bearing SKF 3306 A-2Z (double angular contact)", "stock": 1,
         "unit": "pcs", "min_stock": 2, "asset_external_ids": ["PUMP-01"]},
        {"id": "skf-6306-2z", "name": "Bearing SKF 6306-2Z", "stock": 2,
         "unit": "pcs", "min_stock": 2, "asset_external_ids": ["PUMP-01"]},
        {"id": "grease-mobil-polyrex-em", "name": "Grease Mobil Polyrex EM 390 g", "stock": 4,
         "unit": "tube", "min_stock": 2, "asset_external_ids": ["PUMP-01", "MOTOR-01", "CONV-01"]},
        {"id": "seal-mekanik-nk80", "name": "Seal mekanik Grundfos NK 80-250", "stock": 0,
         "unit": "pcs", "min_stock": 1, "eta": "3 hari", "asset_external_ids": ["PUMP-01"]},
        {"id": "coupling-insert", "name": "Coupling insert pompa NK", "stock": 2,
         "unit": "set", "min_stock": 1, "asset_external_ids": ["PUMP-01"]},
        {"id": "elemen-filter-udara", "name": "Elemen filter udara kompresor sekrup 55 kW", "stock": 2,
         "unit": "pcs", "min_stock": 1, "asset_external_ids": ["COMP-01"]},
        {"id": "filter-oli", "name": "Filter oli kompresor", "stock": 2,
         "unit": "pcs", "min_stock": 1, "asset_external_ids": ["COMP-01"]},
        {"id": "separator-element", "name": "Separator element kompresor", "stock": 0,
         "unit": "pcs", "min_stock": 1, "eta": "5 hari", "asset_external_ids": ["COMP-01"]},
        {"id": "oli-kompresor-46", "name": "Oli kompresor ISO VG 46 20 L", "stock": 1,
         "unit": "drum", "min_stock": 1, "asset_external_ids": ["COMP-01"]},
        {"id": "coolant-concentrate", "name": "Coolant concentrate 20 L", "stock": 3,
         "unit": "jerigen", "min_stock": 1, "asset_external_ids": ["CNC-MILL-01", "CNC-MILL-02"]},
        {"id": "filter-chip", "name": "Filter chip conveyor mesin milling", "stock": 1,
         "unit": "pcs", "min_stock": 1, "asset_external_ids": ["CNC-MILL-01", "CNC-MILL-02"]},
        {"id": "way-lube-iso68", "name": "Way lube ISO VG 68 20 L", "stock": 2,
         "unit": "jerigen", "min_stock": 1, "asset_external_ids": ["CNC-MILL-01", "CNC-MILL-02"]},
        {"id": "spindle-bearing-set", "name": "Bearing spindle Bridgeport (matched pair)", "stock": 0,
         "unit": "set", "min_stock": 1, "eta": "10 hari",
         "asset_external_ids": ["CNC-MILL-01", "CNC-MILL-02"]},
        {"id": "belt-800mm", "name": "Sabuk konveyor 800 mm", "stock": 1,
         "unit": "roll", "min_stock": 1, "asset_external_ids": ["CONV-01"]},
        {"id": "roller-idler", "name": "Roller idler konveyor", "stock": 6,
         "unit": "pcs", "min_stock": 4, "asset_external_ids": ["CONV-01"]},
        {"id": "seal-kit-100t", "name": "Seal kit silinder hidrolik 100 ton", "stock": 1,
         "unit": "set", "min_stock": 1, "asset_external_ids": ["PRESS-01"]},
        {"id": "oli-hidrolik-iso46", "name": "Oli hidrolik ISO VG 46 20 L", "stock": 2,
         "unit": "drum", "min_stock": 1, "asset_external_ids": ["PRESS-01"]},
        {"id": "filter-hidrolik", "name": "Filter hidrolik press", "stock": 2,
         "unit": "pcs", "min_stock": 1, "asset_external_ids": ["PRESS-01"]},
        {"id": "refrigerant-r410a", "name": "Refrigerant R-410A 11.3 kg", "stock": 1,
         "unit": "tabung", "min_stock": 1, "asset_external_ids": ["CHILL-01"]},
        {"id": "coil-cleaner", "name": "Coil cleaner kondensor 5 L", "stock": 2,
         "unit": "jerigen", "min_stock": 1, "asset_external_ids": ["CHILL-01"]},
    ],
    "operator_reports": {
        "PUMP-01": "Suara mendengung dari sisi kopling sejak dua hari terakhir, casing bearing terasa panas saat disentuh.",
        "COMP-01": "Kompresor lebih sering unload dan tekanan jaringan turun saat semua mesin jalan.",
        "CNC-MILL-01": "Suhu proses naik dan permukaan hasil milling mulai kasar menjelang akhir shift.",
        "MOTOR-01": "Getaran terasa di dudukan motor saat konveyor start, hilang setelah beberapa menit.",
    },
}


# --- verification, using the engine's own detector ------------------------

def as_readings(by_tag: dict[str, list[float]]) -> list[SensorReading]:
    start = NOW - timedelta(hours=POINTS)
    return [
        SensorReading(tag=tag, value=value, unit="", recorded_at=start + timedelta(hours=i))
        for tag, values in by_tag.items()
        for i, value in enumerate(values)
    ]


def to_readings(rows: list[dict]) -> list[SensorReading]:
    return [
        SensorReading(tag=row["tag"], value=float(row["value"]), unit=row["unit"],
                      recorded_at=datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00")))
        for row in rows
    ]


def flagged_tags(rows, asset_id: str | None = None) -> list[str]:
    readings = rows if rows and isinstance(rows[0], SensorReading) else to_readings(rows)
    return sorted(anomaly.tag for anomaly in detect_anomalies(readings, asset_id))


def analysis_window(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: row["recorded_at"], reverse=True)[:ANALYSIS_LIMIT]


def verify_parts() -> None:
    stocked = {part["id"] for part in BUSINESS_CONTEXT["inventory"]} | NON_STOCK
    used = {code for _, _, _, _, parts in HISTORY for code in parts.split(",") if code}
    assert not used - stocked, f"maintenance history uses unknown parts: {sorted(used - stocked)}"
    assets = {asset["external_id"] for asset in ASSETS}
    for part in BUSINESS_CONTEXT["inventory"]:
        unknown = set(part["asset_external_ids"]) - assets
        assert not unknown, f"part {part['id']} fits unknown machines: {sorted(unknown)}"
    for external_id in BUSINESS_CONTEXT["operator_reports"]:
        assert external_id in assets, f"operator report for unknown machine {external_id}"


def verify(readings: dict[str, list[dict]]) -> None:
    """The demo is only worth showing if the sick machines light up and the
    healthy ones stay quiet — in both modes the backend can score them, over
    exactly the rows the analyzer reads."""
    history_by_asset: dict[str, list[EngineRecord]] = {}
    for asset, days, action, findings, _ in HISTORY:
        history_by_asset.setdefault(asset, []).append(EngineRecord(
            asset_id=asset, performed_at=NOW - timedelta(days=days),
            action=action, findings=findings))

    for spec in ASSETS:
        external_id = spec["external_id"]
        rows = readings[external_id]
        window = to_readings(analysis_window(rows))
        fenced = flagged_tags(window)

        # What POST /assets/{id}/baseline fits: every reading stored so far.
        fitted = baseline.fit(external_id, to_readings(rows))
        assert fitted, f"{external_id}: no tag had enough history to fit a baseline"
        learned = flagged_tags(window, external_id)

        expected = external_id in DEGRADED
        assert bool(fenced) is expected, f"{external_id}: fence flagged {fenced}"
        assert bool(learned) is expected, f"{external_id}: baseline flagged {learned}"

        asset = EngineAsset(id=external_id, name=spec["name"], type=spec["asset_type"],
                            criticality=spec["criticality"], specs=spec["specs"])
        score, _ = health_score(asset, detect_anomalies(window, external_id),
                                history_by_asset.get(external_id, []), now=NOW)
        assert (score < 85) is expected, f"{external_id}: score {score} contradicts its story"
        print(f"  {external_id:<12} score {score:>3}  fence {fenced or '[]'}  baseline {learned or '[]'}")


# --- writing --------------------------------------------------------------

def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.relative_to(HERE)}: {len(rows)} rows")


def main() -> None:
    random.seed(20260825)
    bank = tempfile.TemporaryDirectory()
    engine_config.BASELINE_DIR = bank.name  # never touch the real baseline bank

    failing, healthy = mill_blocks(ai4i_rows())
    readings = {
        "CNC-MILL-01": mill_rows("CNC-MILL-01", failing),
        "CNC-MILL-02": mill_rows("CNC-MILL-02", healthy),
        **{external_id: synth_rows(external_id, tags) for external_id, tags in SYNTHETIC.items()},
    }
    verify(readings)
    verify_parts()

    write_csv(HERE / "assets.csv",
              ["external_id", "name", "asset_type", "criticality", "location", "specs_json"],
              [{**{key: asset[key] for key in
                   ("external_id", "name", "asset_type", "criticality", "location")},
                "specs_json": json.dumps(asset["specs"], ensure_ascii=False)} for asset in ASSETS])

    for external_id, items in readings.items():
        write_csv(HERE / "readings" / f"{external_id}.csv",
                  ["tag", "value", "unit", "recorded_at", "source", "external_id"], items)

    write_csv(HERE / "maintenance-history.csv",
              ["asset_external_id", "performed_at", "action", "findings", "parts_used", "external_id"],
              [{"asset_external_id": asset,
                "performed_at": (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z"),
                "action": action, "findings": findings, "parts_used": parts,
                "external_id": f"MR-{asset}-{days:04d}"}
               for asset, days, action, findings, parts in HISTORY])

    (HERE / "business-context.json").write_text(
        json.dumps(BUSINESS_CONTEXT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("business-context.json")


if __name__ == "__main__":
    main()
