# 公司請假系統 v2.0（支援 Windows 11 + 多機同步）

## 功能
- 事假 / 病假 / 年假 / 公假 / 喪假
- 時數與天數雙模式
- 請假申請、餘額查詢、主管審核
- **多台電腦同步使用**（需部署到雲端）

---

## 方案一：多機同步（推薦）

把系統部署到免費雲端（Render.com），所有 Windows 電腦都連同一個網址即可同步。

### 步驟（約 5~8 分鐘）

1. 到 https://render.com 註冊帳號（可用 GitHub 登入）
2. 把本專案上傳到 GitHub（或直接用 Render 的「Deploy from Git」）
3. 在 Render 建立 **Web Service** + **PostgreSQL** 資料庫
4. 設定完成後，Render 會給你一個網址，例如：
   `https://leave-system-xxxx.onrender.com`
5. **所有人只要用瀏覽器打開這個網址**，就能同步使用

> 免費方案在長時間沒人使用時會休眠，第一次開啟可能需等 30~50 秒。

### 快速部署指令（有 GitHub 時）

把整個 `leave_system` 資料夾推到 GitHub 後，在 Render 選擇「New → Blueprint」並選擇 `render.yaml` 即可一鍵部署。

---

## 方案二：本機 Windows 11 應用程式（單機）

1. 安裝 Python 3.10 以上（勾選 Add to PATH）
2. 解壓縮本資料夾
3. 雙擊 `build_windows.bat`
4. 等待完成後，執行 `dist\LeaveSystem.exe`

此模式資料只存在該台電腦，無法多機同步。

---

## 方案三：本機開發模式

```bash
pip install -r requirements.txt
python main.py
```

瀏覽器會自動開啟 http://127.0.0.1:8000

---

## API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/leave-types` | 假別列表 |
| GET | `/api/employees` | 員工列表 |
| GET | `/api/balances/{emp_id}` | 假期餘額 |
| GET | `/api/requests` | 申請紀錄 |
| POST | `/api/requests` | 新增申請 |
| POST | `/api/approve` | 審核 |
| DELETE | `/api/requests/{id}` | 取消申請 |
| GET | `/api/health` | 健康檢查 |

---

## 技術說明
- Backend: FastAPI + SQLAlchemy
- 資料庫：本機用 SQLite，雲端用 PostgreSQL
- 前端：純 HTML/JS
- 已開啟 CORS，支援多網域存取
