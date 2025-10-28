import json
from pathlib import Path
from typing import Dict
from config import STATION_LIST_FILENAME

STNS_PATH = Path(__file__).resolve().parent.parent / STATION_LIST_FILENAME


with open(STNS_PATH, "r", encoding="utf-8") as fp:
    STATIONS: Dict[str, str] = json.load(fp)
