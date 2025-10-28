import sqlite3, csv
from pathlib import Path
from datetime import datetime, timedelta, time, date
from typing import List, Dict
import config
from utils.parser import time_window_bounds


# --- 連線與建表 ---
def get_db_path() -> Path:
    base = Path(config.sys.executable).parent if getattr(config.sys, "frozen", False) else Path.cwd()
    return base / "record.db"


def db_connect():
    conn = sqlite3.connect(get_db_path(), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def db_init():
    with db_connect() as conn:
        c = conn.cursor()
        # 每筆觀測（以 station_id + obs_time 唯一，避免重複）
        c.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            station_id   TEXT NOT NULL,  -- 測站代碼
            name         TEXT,           -- 測站名稱
            obs_time     TEXT NOT NULL,  -- 觀測時間 "%Y-%m-%d %H:%M:%S" (UTC+8)
            speed        REAL,           -- 平均風風速
            dir          REAL,           -- 平均風風向
            gust_speed   REAL,           -- 最大陣風風速
            gust_dir     REAL,           -- 最大陣風風向
            gust_time    TEXT,           -- 最大陣風時間 "%Y-%m-%d %H:%M:%S" (UTC+8)
            precip       REAL,           -- 日累積雨量
            air_temp     REAL,           -- 溫度
            rh           REAL,           -- 相對溼度
            pres         REAL,           -- 氣壓
            tmax         REAL,           -- 日最高溫
            tmax_time    TEXT,           -- 日最高溫時間 "%Y-%m-%d %H:%M:%S" (UTC+8)
            tmin         REAL,           -- 日最低溫
            tmin_time    TEXT,           -- 日最低溫時間 "%Y-%m-%d %H:%M:%S" (UTC+8)
            PRIMARY KEY (station_id, obs_time)
        );
        """)
        conn.commit()


# --- 資料插入/更新 ---
def save_observations(rows: List[Dict]):
    """
    將每站一筆 rows 寫入 SQLite。
    以 (station_id, obs_time) 做 UPSERT，避免重複。
    """
    # 準備好 16 個欄位的資料；缺主鍵就跳過
    payload = []
    for r in rows:
        sid = (r.get("station_id") or "").strip()
        obs_time = r.get("time")
        if not sid or not obs_time:
            continue
        payload.append((
            sid,
            r.get("name"),
            obs_time,
            r.get("speed"),
            r.get("dir"),
            r.get("gust_speed"),
            r.get("gust_dir"),
            r.get("gust_time"),
            r.get("precip"),
            r.get("air_temp"),
            r.get("rh"),
            r.get("pres"),
            r.get("tmax"),
            r.get("tmax_time"),
            r.get("tmin"),
            r.get("tmin_time"),
        ))
    if not payload:
        return

    sql = """
    INSERT INTO observations (
      station_id, name, obs_time,
      speed, dir, gust_speed, gust_dir, gust_time,
      precip, air_temp, rh, pres,
      tmax, tmax_time, tmin, tmin_time
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(station_id, obs_time) DO UPDATE SET
      name         = excluded.name,
      speed        = excluded.speed,
      dir          = excluded.dir,
      gust_speed   = excluded.gust_speed,
      gust_dir     = excluded.gust_dir,
      gust_time    = excluded.gust_time,
      precip       = excluded.precip,
      air_temp     = excluded.air_temp,
      rh           = excluded.rh,
      pres         = excluded.pres,
      tmax         = excluded.tmax,
      tmax_time    = excluded.tmax_time,
      tmin         = excluded.tmin,
      tmin_time    = excluded.tmin_time
    """
    with db_connect() as conn:
        conn.executemany(sql, payload)
        conn.commit()


# --- CSV 匯出 ---
def write_csv_for_day(base_day: date):
    """
    依資料庫內容輸出「指定日期 day」的 CSV（UTF-8-SIG）。
    時間範圍：(day 00:00, day+1 00:00] —— 起點排除、終點包含（符合你「過去10分鐘」的需求）。
    檔名：YYYYMMDD.csv（以 day 命名）
    """
    start_dt = datetime.combine(base_day, time(0,0,0), tzinfo=config.TPE)
    end_dt   = start_dt + timedelta(days=1)

    start = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    end   = end_dt.strftime("%Y-%m-%d %H:%M:%S")

    with db_connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT *
            FROM observations
            WHERE obs_time > ? AND obs_time <= ?
            ORDER BY station_id, obs_time
        """, (start, end))
        rows = c.fetchall()

    out_path = config.get_output_dir() / f"{base_day.strftime('%Y%m%d')}.csv"

    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "測站代碼", "測站名稱", "觀測時間",
            "平均風風速(m/s)", "平均風風向(°)",
            "最大陣風風速(m/s)", "最大陣風風向(°)", "最大陣風時間",
            "日累積雨量(mm)", "溫度(℃)", "相對溼度(%)", "氣壓(hPa)",
            "日最高溫(℃)", "日最高溫時間", "日最低溫(℃)", "日最低溫時間"
        ])
        def d(x):
            try:
                return "" if x is None else f"{float(x):.1f}"
            except Exception:
                return ""
        for r in rows:
            w.writerow([
                r["station_id"],
                r["name"],
                r["obs_time"] or "",
                d(r["speed"]),
                d(r["dir"]),
                d(r["gust_speed"]),
                d(r["gust_dir"]),
                r["gust_time"],
                d(r["precip"]),
                d(r["air_temp"]),
                d(r["rh"]),
                d(r["pres"]),
                d(r["tmax"]),
                r["tmax_time"] or "",
                d(r["tmin"]),
                r["tmin_time"] or "",
            ])
    return out_path


# --- 查詢時間窗給 /api/data ---
def query_rows_for_window(window: str, tab: str) -> list[dict]:
    """
    依時間段 window 與分頁 tab 取每站一筆代表資料：
      window = 'now' | '1h' | '24h' | 'today'
      tab    = 'avg-wind' | 'gust' | 'daily-precip' | 'air-temp' | 'rh'
    回傳欄位會對齊前端既有鍵名。
    """
    start, end = time_window_bounds(window)

    match tab:
        case "avg-wind":
            metric = "speed"
            columns = ["station_id", "name", "speed", "dir", "obs_time AS time"]
        case "gust":
            metric = "gust_speed"
            columns = ["station_id", "name", "gust_speed", "gust_dir", "gust_time AS time"]
        case "daily-precip":
            metric = "precip"
            columns = ["station_id", "name", "precip", "obs_time AS time"]
        case "air-temp":
            metric = "air_temp"
            columns = ["station_id", "name", "air_temp", "obs_time AS time"]
        case "rh":
            metric = "rh"
            columns = ["station_id", "name", "rh", "obs_time AS time"]
        case _:
            metric = "speed"
            columns = ["station_id", "name", "speed", "dir", "obs_time AS time"]

    with db_connect() as conn:
        c = conn.cursor()
        if start is None and end is None:
            # 每站最新一筆
            columns_str = ",".join([f"o.{col}" for col in columns])
            c.execute(f"""
                WITH latest AS (
                  SELECT station_id, MAX(obs_time) AS t
                  FROM observations
                  GROUP BY station_id
                )
                SELECT {columns_str}
                FROM observations o
                JOIN latest l
                  ON o.station_id = l.station_id AND o.obs_time = l.t
            """)
        else:
            # 時間段內取 metric 最大；若同分數，取 obs_time 最新
            # 用窗口函數排序取 rn=1（需要 SQLite 3.25+；一般 Win10 以上 OK）
            columns_str = ",".join(columns)
            c.execute(f"""
                WITH filt AS (
                  SELECT *
                  FROM observations
                  WHERE obs_time > ? AND obs_time <= ?
                ),
                ranked AS (
                  SELECT *,
                         ROW_NUMBER() OVER (
                           PARTITION BY station_id
                           ORDER BY ({metric} IS NULL),
                                    {metric} DESC,
                                    obs_time DESC
                         ) AS rn
                  FROM filt
                )
                SELECT {columns_str}
                FROM ranked
                WHERE rn = 1
            """, (start, end))
        rows = c.fetchall()

    # 組成與現有 /api/data rows 相同的欄位
    out = []
    for r in rows:
        out.append({ k: r[k] for k in r.keys() })
    return out


# --- 清理舊資料 ---
def prune_old_observations(hours: int = 48) -> None:
    """
    刪除 obs_time <= (現在台北時間 - hours 小時) 的舊資料。
    obs_time 為 '%Y-%m-%d %H:%M:%S' 字串，字典序比較可正確反映時間。
    """
    cutoff_dt = datetime.now(config.TPE) - timedelta(hours=hours)
    cutoff = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
    with db_connect() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM observations WHERE obs_time <= ?", (cutoff,))
        deleted = c.rowcount
        conn.commit()
    config.app.logger.info(f"[prune_observations] cutoff={cutoff} deleted={deleted}")
