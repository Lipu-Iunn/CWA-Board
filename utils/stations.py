from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple
from config import STATION_LIST_FILENAME

import pandas as pd

STATIONS_LIST_PATH = Path(__file__).resolve().parent.parent / STATION_LIST_FILENAME


def _normalize_sheet_name(name: str) -> str:
    # 去掉前後空白，例如「咖啡產區 」
    return name.strip()


def _normalize_station_id(raw: object) -> str:
    if pd.isna(raw):
        return ""
    return str(raw).strip()


def _get_column(df: pd.DataFrame, logical_name: str) -> str:
    """
    logical_name: 'stno' | 'zone' | 'name'
    """
    lowered = {c.strip().lower(): c for c in df.columns}

    if logical_name in lowered:
        return lowered[logical_name]

    raise KeyError(f"工作表缺少必要欄位：{logical_name}")


@lru_cache(maxsize=1)
def load_station_groups() -> Tuple[List[str], Dict[str, List[str]], Dict[str, Dict]]:
    """
    回傳：
    - all_group_names: ["全部", "茶葉產區", "咖啡產區", ...]
    - groups: { group_name: [stno1, stno2, ...] }
    - stations: {
        stno: {"stno": ..., "zone": ..., "name": ..., "groups": [g1, g2, ...]}
      }
    """
    xls = pd.ExcelFile(STATIONS_LIST_PATH)

    stations: Dict[str, Dict] = {}
    groups: Dict[str, List[str]] = {}

    for sheet_name in xls.sheet_names:
        group_name = _normalize_sheet_name(sheet_name)
        df = xls.parse(sheet_name)

        col_stno = _get_column(df, "stno")
        col_zone = _get_column(df, "zone")
        col_name = _get_column(df, "name")

        group_station_ids: List[str] = []

        for _, row in df.iterrows():
            stno = _normalize_station_id(row[col_stno])
            if not stno:
                continue

            zone = str(row[col_zone]).strip() if not pd.isna(row[col_zone]) else ""
            name = str(row[col_name]).strip() if not pd.isna(row[col_name]) else ""

            if stno not in stations:
                stations[stno] = {
                    "stno": stno,
                    "zone": zone,
                    "name": name,
                    "groups": [],
                }
            # 更新 zone / name 以 Excel 為主
            stations[stno]["zone"] = zone
            stations[stno]["name"] = name

            if group_name not in stations[stno]["groups"]:
                stations[stno]["groups"].append(group_name)

            group_station_ids.append(stno)

        groups[group_name] = group_station_ids

    all_group_names = ["全部"] + list(groups.keys())
    return all_group_names, groups, stations


def get_all_station_ids() -> List[str]:
    """
    提供「所有要抓取的測站代碼清單」，給 scheduler / fetcher 用。
    """
    _, _, stations = load_station_groups()
    return list(stations.keys())


def get_groups() -> List[str]:
    """
    僅回傳所有群組名稱（含「全部」）。
    """
    all_group_names, _, _ = load_station_groups()
    return all_group_names


def get_group_mapping() -> Dict[str, List[str]]:
    """
    回傳 {群組名稱: [stno, ...]}。
    """
    _, groups, _ = load_station_groups()
    return groups


def get_station_meta(station_id: str) -> Dict | None:
    """
    回傳單一測站的 meta（含 name、zone、groups），給 /api 用來補充欄位。
    """
    _, _, stations = load_station_groups()
    return stations.get(station_id)
