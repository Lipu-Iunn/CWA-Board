import requests
from typing import Dict, Any, List
import config
from utils.stations import get_all_station_ids, get_station_meta
import utils.parser as parser
import utils.cleaners as cleaners

TPE = config.TPE


def fetch_from_api(base_url: str, station_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    回傳 {station_id: {'speed': float|None, 'dir': any, 'gust': any}, ...}
    任何解析失敗不會 raise，直接略過該筆或設為 None。
    """
    if not station_ids:
        return {}
    params = {
        "Authorization": config.CWA_TOKEN,
        "format": "JSON",
        "StationId": ",".join(station_ids),
        "WeatherElement": config.FIELDS
    }
    try:
        r = requests.get(base_url, params=params, timeout=config.FETCH_TIMEOUT)
        r.raise_for_status()
        payload = r.json()
    except Exception as e:
        config.app.logger.warning(f"[fetch_from_api] request error: {e}")
        return {}

    # records.Station or records.location
    records = None
    recs = payload.get("records")
    if isinstance(recs, dict):
        if isinstance(recs.get("Station"), list):
            records = recs.get("Station")
        elif isinstance(recs.get("location"), list):
            records = recs.get("location")

    if not isinstance(records, list):
        config.app.logger.warning("[fetch_from_api] unexpected JSON shape; 'records.Station' not found.")
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for rec in records:
        sid, data = parser.parse_record(rec)
        if sid:
            out[sid] = data
    return out


def build_rows(merged: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """產出各站氣象參數（欄位統一：station_id/name/time/speed/dir/...）"""
    rows: List[Dict[str, Any]] = []
    for sid, entry in merged.items():
        name = get_station_meta(sid)["name"]

        rows.append({
            "station_id": sid,
            "name": name,
            "time": entry.get("obs_time"),
            "speed": entry.get("speed"),
            "dir": entry.get("dir"),
            "gust_speed": entry.get("gust_speed"),
            "gust_dir": entry.get("gust_dir"),
            "gust_time": entry.get("gust_time"),
            "precip": entry.get("precip"),
            "air_temp": entry.get("air_temp"),
            "tmax": entry.get("tmax"),
            "tmax_time": entry.get("tmax_time"),
            "tmin": entry.get("tmin"),
            "tmin_time": entry.get("tmin_time"),
            "rh": entry.get("rh"),
            "pres": entry.get("pres")
        })

    return rows


def fetch_data() -> List[Dict[str, Any]]:
    """
    先抓 API1 全量 -> 找出缺失/風速為 None 的站 -> 用 API2 補 -> 合併
    回傳排序後的 list[ {station_id, name, speed, dir, gust} ]
    """
    all_ids = get_all_station_ids()

    # 1) API1 全抓
    data1 = fetch_from_api(config.API1, all_ids)

    # 2) 判定哪些站需要補：沒有出現在 data1，或 speed 為 None
    need_fill = [sid for sid in all_ids if (sid not in data1) or (data1[sid].get("speed") is None)]
    
    # 3) API2 補缺
    data2 = fetch_from_api(config.API2, need_fill) if need_fill else {}
    
    # 4) 合併：以 data1 為主，缺的才用 data2
    merged: Dict[str, Dict[str, Any]] = {}
    for sid in all_ids:
        base = data1.get(sid) or {}
        if (not base) or (base.get("speed") is None):
            fill = data2.get(sid) or {}
            # 以補到的覆蓋缺值
            base = {**base, **{k:v for k,v in fill.items() if v not in (None, {}, "")}}
        merged[sid] = base
    rows = build_rows(merged)

    # 5) 檢查資料是否有明顯錯誤
    #  - 校正跨日時間
    rows = cleaners.correct_occured_time(rows)

    return rows
