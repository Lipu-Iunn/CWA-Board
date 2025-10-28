from datetime import datetime, timedelta


def _parse_local_ts(ts: str | None) -> datetime | None:
    """把 '%Y-%m-%d %H:%M:%S' 字串轉成 datetime（naive, 視為同一時區）。
       如果 ts 為 None / '' / 格式錯誤，就回傳 None。"""
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _fmt_local_ts(dt: datetime | None) -> str | None:
    """把 datetime 轉回 '%Y-%m-%d %H:%M:%S' 字串；None 則回傳 None。"""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def correct_occured_time(rows: list[dict]) -> list[dict]:
    """
    對每一筆 row：
      如果 gust_time / tmax_time / tmin_time 晚於 time，
      則將該欄位往前推 1 天 ( - timedelta(days=1) )。
    回傳同一個 rows（就地修改後再回傳）。
    """
    for row in rows:
        base_ts = _parse_local_ts(row.get("time"))
        if base_ts is None:
            # 如果這列本身沒有 time，就無法比對，跳過
            continue

        for key in ("gust_time", "tmax_time", "tmin_time"):
            ts_val = row.get(key)
            dt_val = _parse_local_ts(ts_val)
            if dt_val is None:
                continue

            # 如果像 00:05 的觀測(time) 對應到 gust_time 23:55 -> dt_val < base_ts，正常不動
            # 但如果 gust_time 是 23:55 "隔天" (也就是 dt_val > base_ts)，就代表 API/日界線錯置，需要 -1 天
            if dt_val > base_ts:
                fixed = dt_val - timedelta(days=1)
                row[key] = _fmt_local_ts(fixed)

    return rows
