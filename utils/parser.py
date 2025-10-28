import json
from datetime import datetime, timedelta, time
from typing import Tuple, Dict, Any
from zoneinfo import ZoneInfo
import config

TPE = config.TPE


def _safe_get(d, *keys, default=None):
    """逐層 dict 安全取值（大小寫容錯可在呼叫時提供多個鍵名）"""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        if isinstance(k, (list, tuple)):
            found = None
            for kk in k:
                if kk in cur:
                    found = cur[kk]
                    break
            cur = found
        else:
            cur = cur.get(k)
    return cur if cur is not None else default


def _safe_float(x):
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s == "" or s.lower() in ("nan", "null", "-99"):
            return None
        return float(s)
    except Exception:
        return None


def _safe_str(x):
    if x is None:
        return None
    s = str(x).strip()
    return s if s and s != "-99" else None


def _iso_to_tpe_str(x: str | None) -> str | None:
    """接收 ISO 8601（含 Z 或 +00:00/+08:00），回傳 %Y-%m-%d %H:%M:%S 格式。"""
    if not x:
        return None
    try:
        s = x.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # 若來源沒 tz，保守視為 UTC 再轉台北（依需求可調）
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(TPE).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        # 如果解析資料，就原樣回傳
        return x
    

def _extract_station_id(rec: Dict[str, Any]) -> str | None:
    for k in ("StationId","stationId","StationID","STID","stno"):
        v = rec.get(k)
        if v:
            return str(v)
    st = rec.get("Station") or {}
    for k in ("StationId","stationId","StationID"):
        v = st.get(k)
        if v:
            return str(v)
    return None


def _extract_weather_element(rec: Dict[str, Any]) -> Dict[str, Any]:
    we = rec.get("WeatherElement") or rec.get("weatherElement") or {}
    if not isinstance(we, dict):
        we = {}
    # 把 WeatherElement 攤平
    return {**rec, **we}


def _extract_obs_time(rec: Dict[str, Any]) -> str | None:
    """
    觀測時間：優先 ObsTime.DateTime；其次 time.obsTime；都沒有則 None。
    最後轉成 +08:00 的 ISO。
    """
    obs = rec.get("ObsTime") or rec.get("obsTime") or rec.get("time") or {}
    if isinstance(obs, dict):
        dt = obs.get("DateTime") or obs.get("obsTime")
    else:
        dt = None
    return _iso_to_tpe_str(_safe_str(dt))


def _parse_gust(gust_raw: Any) -> Dict[str, Any]:
    """
    回傳 {'speed': float|None, 'dir': str|None, 'time': str|None(+08:00 ISO)}
    """
    g = gust_raw
    if isinstance(g, str):
        try:
            g = json.loads(g)
        except Exception:
            g = None
    if not isinstance(g, dict):
        return {"speed": None, "dir": None, "time": None}

    speed = _safe_float(g.get("PeakGustSpeed") or g.get("peakGustSpeed"))
    occ = g.get("Occurred_at") or g.get("occurred_at") or {}
    if not isinstance(occ, dict):
        occ = {}
    dir_ = _safe_str(occ.get("WindDirection") or occ.get("windDirection"))
    t = _iso_to_tpe_str(_safe_str(occ.get("DateTime") or occ.get("dateTime")))
    return {"speed": speed, "dir": dir_, "time": t}


def parse_record(rec: Dict[str, Any]) -> Tuple[str | None, Dict[str, Any]]:
    sid = _extract_station_id(rec)
    we = _extract_weather_element(rec)

    # 平均風
    speed = _safe_float(we.get("WindSpeed") or we.get("WDSD") or we.get("WIND_SPEED"))
    wdir  = _safe_str(we.get("WindDirection") or we.get("WDIR"))

    # 陣風
    gust = _parse_gust(we.get("GustInfo") or we.get("GUST") or we.get("Gust"))

    # 觀測時間
    obs_time = _extract_obs_time(rec)

    # 日累積雨量
    now_obj = we.get("Now") or we.get("now") or {}
    precip = _safe_float(_safe_get(now_obj, ["Precipitation","precipitation"]))

    # 溫度、相對溼度、氣壓
    air_temp = _safe_float(_safe_get(we, ["AirTemperature","airTemperature"]))
    rh       = _safe_float(_safe_get(we, ["RelativeHumidity","relativeHumidity"]))
    pres     = _safe_float(_safe_get(we, ["AirPressure","airPressure"]))

    # 今日極值
    de = we.get("DailyExtreme") or we.get("dailyExtreme") or {}
    dh = _safe_get(de, "DailyHigh") or _safe_get(de, "dailyHigh") or {}
    dl = _safe_get(de, "DailyLow")  or _safe_get(de, "dailyLow")  or {}

    # 最大值：最高溫、發生時間
    hi_tinfo = _safe_get(dh, ["TemperatureInfo","temperatureInfo"]) or {}
    tmax = _safe_float(_safe_get(hi_tinfo, ["AirTemperature","airTemperature"]))
    tmax_time_iso = _safe_str(
        _safe_get(hi_tinfo, "Occurred_at", "DateTime") or
        _safe_get(hi_tinfo, "Occurred_at", "dateTime") or
        _safe_get(hi_tinfo, "occurred_at","DateTime") or
        _safe_get(hi_tinfo, "occurred_at","dateTime")
    )
    tmax_time = _iso_to_tpe_str(tmax_time_iso)

    # 最小值：最低溫、發生時間
    lo_tinfo = _safe_get(dl, ["TemperatureInfo","temperatureInfo"]) or {}
    tmin = _safe_float(_safe_get(lo_tinfo, ["AirTemperature","airTemperature"]))
    tmin_time_iso = _safe_str(
        _safe_get(lo_tinfo, "Occurred_at","DateTime") or
        _safe_get(lo_tinfo, "Occurred_at","dateTime") or
        _safe_get(lo_tinfo, "occurred_at","DateTime") or
        _safe_get(lo_tinfo, "occurred_at","dateTime")
    )
    tmin_time = _iso_to_tpe_str(tmin_time_iso)

    return sid, {
        "obs_time":   obs_time,
        "speed":      speed,
        "dir":        wdir,
        "gust_speed": gust.get("speed"),
        "gust_dir":   gust.get("dir"),
        "gust_time":  gust.get("time"),
        "precip":     precip,
        "air_temp":   air_temp,
        "rh":         rh,
        "pres":       pres,
        "tmax":       tmax,
        "tmax_time":  tmax_time,
        "tmin":       tmin,
        "tmin_time":  tmin_time,
    }


def time_window_bounds(window: str) -> Tuple[str | None, str | None]:
    """
    回傳 (start, end) 的字串時間（%Y-%m-%d %H:%M:%S, UTC+8），
    規則：
      - "now"  -> (None, None)  代表取每站最新一筆
      - "1h"   -> (現在-1h, 現在]
      - "24h"  -> (現在-24h, 現在]
      - "today"-> (今天 00:00, 現在]
    """
    now = datetime.now(TPE)

    match window:
        case "now":
            return (None, None)
        case "1h":
            return ((now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
                now.strftime("%Y-%m-%d %H:%M:%S"))
        case "24h":
            return ((now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
                now.strftime("%Y-%m-%d %H:%M:%S"))
        case "today":
            start_dt = datetime.combine(now.date(), time(0, 0, 0), tzinfo=TPE)
            return (start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    now.strftime("%Y-%m-%d %H:%M:%S"))
        case _:
            return (None, None)
        
    # 預設當作 now
    return (None, None)
