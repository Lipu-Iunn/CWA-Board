from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import config
import utils.fetcher as fetcher
import modules.db as db

SCHEDULER = None


def refresh_cache():
    if not config.CWA_TOKEN:
        config.app.logger.error("CWA_TOKEN 未設定，請在 .env 或環境變數設定。")
        return
    try:
        # 1) 抓取、合併
        rows = fetcher.fetch_data()
        if not rows:
            config.app.logger.warning("[refresh_cache] 無資料可更新")
            return

        # 2) 寫入資料庫
        db.save_observations(rows)

        # 3) 從資料庫產出今日 CSV（全檔覆寫）
        #    觀測時間恰為 00:00:00 的資料，歸入「前一天」的 CSV
        obs_time = datetime.strptime(rows[0]["time"], "%Y-%m-%d %H:%M:%S")
        if obs_time.hour == 0 and obs_time.minute == 0:
            base_day = (obs_time - timedelta(days=1)).date()
        else:
            base_day = obs_time.date()
        out_csv = db.write_csv_for_day(base_day)

        # 4) 更新快取
        with config.DATA_LOCK:
            config.DATA_CACHE["rows"] = rows   # 給 /api/data 後備用
            config.DATA_CACHE["updated_at"] = datetime.now(config.TPE)

        # 5) 推播 WebSocket：只告知資料更新時間；前端再自行 /api/data?window=...&tab=... 拉細部
        config.socketio.emit("data_update", {
            "updated_at": config.DATA_CACHE["updated_at"].strftime("%Y-%m-%d %H:%M:%S")
        }, namespace="/")

        config.app.logger.info(f"[refresh_cache] rows={len(rows)} csv={out_csv.name}")
    except Exception as e:
        config.app.logger.exception(f"[refresh_cache] failed: {e}")


def start_scheduler():
    """
    啟動排程，執行以下工作：
    1) API 抓資料：立刻跑一次，之後每隔 FETCH_INTERVAL_MIN 分鐘跑一次。
    2) 清理資料庫：每天 01:00 清理，只保留過去 48 小時資料。
    """
    global SCHEDULER
    if SCHEDULER:
        return SCHEDULER

    sched = BackgroundScheduler(
        timezone="Asia/Taipei",
        job_defaults={"coalesce": True, "max_instances": 1}
    )

    # API 抓資料
    sched.add_job(
        refresh_cache,
        "interval",
        minutes=config.FETCH_INTERVAL_MIN,
        next_run_time=datetime.now(config.TPE)  # 啟動就先跑一次
    )

    # 清理資料庫
    sched.add_job(
        db.prune_old_observations,
        "cron",
        hour=1, minute=0,
        kwargs={"hours": 48}
    )

    sched.start()
    SCHEDULER = sched
    return SCHEDULER
