import json
from pathlib import Path
from typing import Dict, List, TypedDict

class HumidityLevelEntry(TypedDict):
    level: str
    max: float

class FuzzyParams(TypedDict):
    dry: Dict[str, float]
    very_dry: Dict[str, float]
    activation: float

class Thresholds(TypedDict):
    zoneStateThresholds: Dict[str, float]
    humidityLevelThresholds: List[HumidityLevelEntry]
    fuzzy: FuzzyParams


def _load_thresholds() -> Thresholds:
    root = Path(__file__).resolve().parent.parent
    data_path = root / 'shared' / 'humidity_thresholds.json'
    return json.loads(data_path.read_text(encoding='utf-8'))

THRESHOLDS = _load_thresholds()
ZONE_STATE_THRESHOLDS = THRESHOLDS['zoneStateThresholds']
HUMIDITY_LEVEL_THRESHOLDS = THRESHOLDS['humidityLevelThresholds']
FUZZY_PARAMS = THRESHOLDS['fuzzy']


def calculate_humidity_level(humedad: float) -> str:
    for entry in HUMIDITY_LEVEL_THRESHOLDS:
        if humedad < float(entry['max']):
            return entry['level']
    return HUMIDITY_LEVEL_THRESHOLDS[-1]['level']


def interpret_humedad(humedad: float) -> str:
    if humedad >= float(ZONE_STATE_THRESHOLDS['humedo']):
        return 'humedo'
    if humedad >= float(ZONE_STATE_THRESHOLDS['normal']):
        return 'normal'
    if humedad >= float(ZONE_STATE_THRESHOLDS['seco']):
        return 'seco'
    return 'muy_seco'


def estado_desde_humedad(humedad: float) -> str:
    return interpret_humedad(humedad)


def mu_dry(h: float) -> float:
    start = FUZZY_PARAMS['dry']['start']
    end = FUZZY_PARAMS['dry']['end']
    if h <= start:
        return 1.0
    if h >= end:
        return 0.0
    return (end - h) / (end - start)


def mu_very_dry(h: float) -> float:
    start = FUZZY_PARAMS['very_dry']['start']
    end = FUZZY_PARAMS['very_dry']['end']
    if h <= start:
        return 1.0
    if h >= end:
        return 0.0
    return (end - h) / (end - start)


def requiere_riego(humedad: float) -> bool:
    return (mu_dry(humedad) + mu_very_dry(humedad)) > float(FUZZY_PARAMS['activation'])
