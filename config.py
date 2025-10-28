import os, sys, threading
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from flask import Flask
from flask_socketio import SocketIO

# ---------- 時區 ----------
TPE = ZoneInfo("Asia/Taipei")


# ---------- .env 載入 ----------
def load_env_file():
    """
    依序嘗試載入下列位置的 .env：
    1) 目前工作目錄（方便 exe 與開發環境）
    2) 若為 PyInstaller 打包（sys.frozen=True），則 exe 同資料夾
    3) 原始碼檔所在目錄（開發時）
    找到第一個存在的就載入；不覆蓋既有的環境變數。
    """
    candidates = [Path.cwd() / ".env"]

    if getattr(sys, "frozen", False):
        # PyInstaller onefile 模式
        candidates.append(Path(sys.executable).parent / ".env")
    else:
        # 一般開發模式
        candidates.append(Path(__file__).parent / ".env")

    for p in candidates:
        if p.exists():
            load_dotenv(dotenv_path=p, override=False)
            break

load_env_file()

CWA_TOKEN = os.getenv("CWA_TOKEN", "").strip()


# ---------- 常數 ----------
API1 = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001"
API2 = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001"
FIELDS = "Now,WindDirection,WindSpeed,AirTemperature,RelativeHumidity,AirPressure,GustInfo,DailyHigh,DailyLow"
FETCH_TIMEOUT = int(os.getenv("FETCH_TIMEOUT", 15))
FETCH_INTERVAL_MIN = int(os.getenv("FETCH_INTERVAL_MIN", 1))
CSV_DIR_NAME = os.getenv("CSV_DIR_NAME", "csv").strip()
STATION_LIST_FILENAME = os.getenv("STATION_LIST_FILENAME", "stns.json").strip()


# ---------- Flask / SocketIO ----------
app = Flask(__name__, template_folder="templates", static_folder="static")
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",
    ping_timeout=10,
    ping_interval=5
)


# ---------- 全域快取 (給 /api/data & WebSocket) ----------
DATA_LOCK = threading.Lock()
DATA_CACHE = {
    "updated_at": None,  # datetime in TPE
    "rows": []           # 最新一次抓到的 rows (list[dict])
}


# ---------- 輸出 CSV 目錄 ----------
def get_output_dir() -> Path:
    """
    輸出資料夾位置：
    - 打包（frozen）時：exe 同資料夾下的 CSV_DIR_NAME
    - 開發模式：目前工作目錄下的 CSV_DIR_NAME
    """
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    out = base / CSV_DIR_NAME
    out.mkdir(parents=True, exist_ok=True)
    return out
