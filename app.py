import os
import config
import modules.db as db
import routes
import utils.scheduler_jobs as scheduler_jobs

def main():
    # 確保 DB schema 存在
    db.db_init()

    # 啟動排程：只在真正的 run process 啟動一次，避免重複
    is_reloader_child = (os.environ.get("WERKZEUG_RUN_MAIN") == "true")
    if not config.app.debug or is_reloader_child:
        scheduler_jobs.start_scheduler()

    # 啟動 SocketIO/Flask
    config.socketio.run(
        config.app,
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )

if __name__ == "__main__":
    main()
