# CWA Wind Board｜即時風速排行榜

> 以 Flask + Flask-SocketIO 打造的即時觀測資料抓取軟體、風速排行榜介面：定期抓取中央氣象署開放資料（O-A0003-001，缺值由 O-A0001-001 補），整理合併後寫入 SQLite，並輸出每日 CSV；前端提供風速排行榜介面，使用 WebSocket 即時更新。

## 功能特色

- 以 APScheduler 定期抓取指定測站們的氣象資料，包含氣壓、溫度、相對溼度、平均風、最大陣風、日累積雨量等
- 後端快取 + WebSocket 推播即時資料，前端自動重拉資料
- 使用 SQLite 存取資料，支援過去一段時間內查詢
- 自動輸出每日 UTF-8-BOM CSV（YYYYMMDD.csv）
- 以 APScheduler 定期清理資料庫（保留近 48 小時）

## 專案架構

- `app.py`：進入點，初始化資料庫、啟動排程與 SocketIO 伺服器
- `config.py`：環境變數、常數、Flask/SocketIO 實例與全域快取
- `routes.py`：HTTP 路由（首頁、`/api/data`）
- `modules/db.py`：SQLite 存取、時間查詢、CSV 輸出、清理舊資料
- `utils/`：
  - `fetcher.py`：抓取、合併 CWA 資料
  - `parser.py`：解析各 API 欄位與時間格式、時間窗計算
  - `cleaners.py`：修正不合理的資料
  - `scheduler_jobs.py`：排程任務（抓取/寫庫/輸出 CSV/推播/清理）
  - `stations.py`：載入測站清單 `stns.json`
- 前端：`templates/index.html`、`static/js/index.js`、`static/css/index.css`
- 資料輸出：`csv/`（每日 CSV）、`record.db`（SQLite）

## 安裝需求

- Python 3.11+
- pip

安裝套件：
```bash
pip install -r requirements.txt
```

## 設定

### 步驟
1. 申請並設定 CWA 開放資料授權碼（CWA_TOKEN）

2. 建立 `.env`（可放在「專案根目錄」；若打包為單一執行檔，則可與 exe 同層）：
```env
CWA_TOKEN=填入你的_CWA_TOKEN
FETCH_TIMEOUT=15
FETCH_INTERVAL_MIN=1
CSV_DIR_NAME=csv
STATION_LIST_FILENAME=stns.json
```

3. 準備測站清單：
- 從 `stns.json.sample` 複製為 `stns.json`，並依實際需求調整內容（`{"測站代碼":"測站名稱"}` 映射）

### 環境變數說明：
- `CWA_TOKEN`：CWA 開放資料授權碼，必要
- `FETCH_TIMEOUT`：呼叫 API 逾時的時間間隔（秒鐘，預設 15）
- `FETCH_INTERVAL_MIN`：定時抓取時間間隔（分鐘，預設 1）
- `CSV_DIR_NAME`：輸出 CSV 的子資料夾名稱（預設 `csv`）
- `STATION_LIST_FILENAME`：測站清單檔名（預設 `stns.json`）

## 快速開始

啟動服務：
```bash
python app.py
```
開啟瀏覽器：`http://127.0.0.1:5000`

預設只綁定本機。如需區網存取，可將 `app.py` 內啟動參數改為 `host="0.0.0.0"`：
```python
config.socketio.run(config.app, host="0.0.0.0", port=5000, debug=False, use_reloader=False)
```

## 後端行為與資料流

1. 排程每 `FETCH_INTERVAL_MIN` 分鐘執行：
   - 呼叫 API：
     - 先抓 `O-A0003-001`
     - 對缺值或風速為 None 的測站，以 `O-A0001-001` 補齊
   - 解析/清洗（`utils/parser.py`、`utils/cleaners.py`）
   - 寫入 SQLite（`modules/db.py: save_observations`，以 `(station_id, obs_time)` UPSERT）
   - 依資料庫內容輸出當日 CSV（`modules/db.py: write_csv_for_day`）
   - 更新後端快取、以 WebSocket 推播「已更新時間」

2. 每日 01:00 清理資料庫，只保留近 48 小時資料（可調）

資料儲存位置：
- `record.db`、`csv/` 皆位於目前工作目錄

## API

### GET `/api/data`
查詢時間窗與指標，回傳每站一筆代表資料。

### Query 參數：
- `window`：`now` | `1h` | `24h` | `today`
- `tab`：`avg-wind` | `gust` | `daily-precip` | `air-temp` | `rh`

### 回應格式：
```json
{
  "updated_at": "2025-10-27 12:34:56",
  "rows": [
    {
      "station_id": "72D680",
      "name": "新竹桃改新埔分場",
      "time": "2025-10-27 12:34:00",
      "speed": 12.3,
      "dir": 280,
      "gust_speed": 18.6,
      "gust_dir": "W",
      "gust_time": "2025-10-27 11:50:00",
      "precip": 0.0,
      "air_temp": 26.4,
      "tmax": 28.1,
      "tmax_time": "2025-10-27 12:10:00",
      "tmin": 22.3,
      "tmin_time": "2025-10-27 02:40:00",
      "rh": 68.0,
      "pres": 1006.1
    }
  ]
}
```

### 行為說明：
- `window=now`：每站「最新一筆」觀測
- 其他時間段：於區間內依指定參數選取最大值，若有多筆最大值，取最新時間（使用視窗函數挑選）
- 當查詢失敗時，會回退使用後端快取最新一次的資料

## WebSocket

- 路徑：`/socket.io`（同站台）
- 事件：`data_update`，payload：
```json
{ "updated_at": "2025-10-27 12:34:56" }
```
前端收到後會重新發送 `/api/data`，依當前頁面選項取資料。

## 資料庫與 CSV

### 資料表 `observations`：
```sql
CREATE TABLE observations (
  station_id TEXT NOT NULL,
  name       TEXT,
  obs_time   TEXT NOT NULL,  -- '%Y-%m-%d %H:%M:%S' (UTC+8)
  speed      REAL,
  dir        REAL,
  gust_speed REAL,
  gust_dir   REAL,
  gust_time  TEXT,           -- '%Y-%m-%d %H:%M:%S' (UTC+8)
  precip     REAL,
  air_temp   REAL,
  rh         REAL,
  pres       REAL,
  tmax       REAL,
  tmax_time  TEXT,           -- '%Y-%m-%d %H:%M:%S' (UTC+8)
  tmin       REAL,
  tmin_time  TEXT,           -- '%Y-%m-%d %H:%M:%S' (UTC+8)
  PRIMARY KEY (station_id, obs_time)
);
```

### CSV 輸出：
- 檔名：`YYYYMMDD.csv`，含 BOM，欄位含測站代碼、測站名稱、觀測時間、平均風風速、平均風風向、最大陣風風速、最大陣風風向、最大陣風時間、日雨量、溫度、相對溼度、氣壓、日最高溫、日最高溫時間、日最低溫、日最低溫時間
- 時間範圍：(day 00:00, day+1 00:00]（起點排除、終點包含）

### 重置資料：
- 程式停止後，刪除 `record.db` 即可重新累積

## 前端操作說明

- 分頁：平均風、陣風
- 時間段：現在、過去 1 小時、過去 24 小時、今日
- 風向箭頭：顯示風的「去向」，由風向角度 +180° 旋轉

## 疑難排解

- 啟動時出現「CWA_TOKEN 未設定」：請在 `.env` 或系統環境變數設定 `CWA_TOKEN`
- 首頁顯示「尚未更新」：等待排程第一次抓取完成，或確認後端是否有網路/權杖正確
- WebSocket 無法連線：
  - 確認前端使用 `transports: ["websocket"]`，避免降級輪詢
  - 若反向代理/雲端環境，需允許 WebSocket 協定
- `stns.json` 找不到：請確保檔案存在於專案根目錄，且 `STATION_LIST_FILENAME` 指向正確檔名
