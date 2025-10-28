from flask import render_template, jsonify, request
import config
import modules.db as db


@config.app.route("/")
def index():
    with config.DATA_LOCK:
        updated_at = config.DATA_CACHE["updated_at"]
    return render_template(
        "index.html",
        fetch_interval_min=config.FETCH_INTERVAL_MIN,
        updated_at=updated_at
    )


@config.app.route("/api/data")
def api_data():
    window = request.args.get("window")   # 'now','1h','24h','today'
    tab = request.args.get("tab")         # 'avg-wind','gust','daily-precip','air-temp','rh'

    with config.DATA_LOCK:
        updated_at = config.DATA_CACHE["updated_at"]
        cached_rows = config.DATA_CACHE["rows"]

    updated_str = updated_at.strftime("%Y-%m-%d %H:%M:%S") if updated_at else None

    if window and tab:
        try:
            rows = db.query_rows_for_window(window, tab)
            return jsonify({"updated_at": updated_str, "rows": rows})
        except Exception as e:
            config.app.logger.exception(f"/api/data query failed: {e}")
            # 失敗退回快取
            return jsonify({"updated_at": updated_str, "rows": cached_rows})
    else:
        # 原行為：回傳快取（最新一輪）
        return jsonify({"updated_at": updated_str, "rows": cached_rows})
