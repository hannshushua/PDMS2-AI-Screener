# 第六章：使用案例描述

本章依課程第六章格式，針對每個使用案例圖各提供正常情節與例外情節描述。  
依據設計文件書 FMD-DD-001 v1.0（2026-05-23）及系統 REST API 規格撰寫。

---

## 3.1　UC-01 兒童帳號管理

### UC01-N1　正常情節：新增兒童帳號

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | 新增兒童帳號 |
| 使用案例編號 | UC01-N1 |
| 執行者 | 管理者 |
| 前置條件 | 管理者已登入管理後台（admin.html）；欲新增的 UID 尚未存在於 `user_list` |
| 主要情節 | 1. 管理者於後台輸入兒童 UID、姓名與生日<br>2. 管理者點選「送出」<br>3. 前端送出 POST `/api/user/add`，帶入 `{uid, name, birthday}`<br>4. 後端驗證 UID 格式（不含特殊字元）<br>5. MySQL 執行 INSERT INTO `user_list`，寫入成功<br>6. 後端回傳 `{success: true}`<br>7. 前端顯示「新增成功」，並刷新兒童列表 |
| 後置條件 | `user_list` 中新增一筆兒童資料；UID 可於施測端使用 |

---

### UC01-E1　例外情節：UID 重複

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | 新增兒童帳號 — UID 重複 |
| 使用案例編號 | UC01-E1 |
| 執行者 | 管理者 |
| 前置條件 | 管理者已登入後台；欲新增的 UID 已存在於 `user_list` |
| 例外情節 | 1. 管理者輸入重複的 UID 並點選送出<br>2. POST `/api/user/add` 執行<br>3. MySQL 回傳 Duplicate Entry 錯誤<br>4. 後端回傳 `{success: false, error: "UID 已存在"}` HTTP 400<br>5. 前端顯示「UID 已存在，請更換」<br>6. UID 欄位清空，管理者重新輸入 |
| 後置條件 | 未新增任何資料；`user_list` 不變 |

---

## 3.2　UC-02 進行精細動作測驗

### UC02-N1　正常情節：完整施測流程

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | 進行精細動作測驗 |
| 使用案例編號 | UC02-N1 |
| 執行者 | 施測者、兒童 |
| 前置條件 | 攝影機已連接；兒童 UID 已存在於 `user_list`；Mac Mini 伺服器可連線 |
| 主要情節 | 1. 施測者於 start.html 輸入兒童 UID，送出 POST `/session/set-uid`<br>2. 後端查詢 `user_list`，確認 UID 存在，Session 設定成功<br>3. 施測者於 index.html 選擇測驗關卡（如 Ch1-t2）<br>4. 施測者點選「開始相機」，送出 POST `/opencv-camera/start`<br>5. 攝影機開啟，前端透過 GET `/opencv-camera/frame` 顯示即時預覽<br>6. 施測者引導兒童執行任務，按下「拍照」，送出 POST `/opencv-camera/capture`<br>7. 拍照完成，施測者點選「提交分析」，送出 POST `/run-python`<br>8. 後端回傳 `{task_id}`，前端輪詢 GET `/check-task/<task_id>`<br>9. 分析完成，回傳 `{status: "done", score: 2}`<br>10. 前端顯示評分結果與標註影像 |
| 後置條件 | 評分結果與標註影像寫入 MySQL 對應任務子表；施測紀錄寫入 `score_list` |

---

### UC02-E1　例外情節：攝影機無法開啟

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | 進行精細動作測驗 — 攝影機無法開啟 |
| 使用案例編號 | UC02-E1 |
| 執行者 | 施測者 |
| 前置條件 | 施測端 PC 未連接攝影機，或攝影機索引設定錯誤 |
| 例外情節 | 1. 施測者點選「開始相機」，送出 POST `/opencv-camera/start`<br>2. 後端嘗試開啟所有攝影機索引（0–N），全部失敗<br>3. 後端回傳 `{success: false, error: "無法開啟任何相機"}` HTTP 500，觸發 MSG-003<br>4. 前端顯示「相機無法開啟，請確認裝置連線」<br>5. 施測者至設定頁（setting.html）更新攝影機索引後重試 |
| 後置條件 | 未拍照；未建立分析任務 |

---

### UC02-E2　例外情節：UID 不存在

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | 進行精細動作測驗 — UID 不存在 |
| 使用案例編號 | UC02-E2 |
| 執行者 | 施測者 |
| 前置條件 | 施測者輸入的 UID 尚未由管理者建立 |
| 例外情節 | 1. 施測者輸入 UID，送出 POST `/session/set-uid`<br>2. 後端查詢 `user_list`，找不到該 UID<br>3. 後端回傳 `{success: false, code: "USER_NOT_FOUND"}` HTTP 404，觸發 MSG-001<br>4. 前端顯示「此使用者不存在，請請管理者建立帳號」<br>5. Session UID 未設定，頁面停留在輸入頁 |
| 後置條件 | Session UID 未設定；系統停留在 start.html 輸入頁 |

---

## 3.3　UC-03 AI 影像分析與評分

### UC03-N1　正常情節：AI 分析並儲存評分

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | AI 影像分析與評分 |
| 使用案例編號 | UC03-N1 |
| 執行者 | AI 分析引擎（Mac Mini） |
| 前置條件 | 施測端已拍照；影像存於 `kid/{uid}/{task_id}.jpg`；Mac Mini 伺服器可連線 |
| 主要情節 | 1. 施測端送出 POST `/api/analysis/submit`（multipart/form-data，含影像、uid、img_id）<br>2. Mac Mini 接收影像，依 task_id 選擇對應分析模組<br>3. Ch1：YOLO 偵測積木 → SAM 分割遮罩 → 骨架化 → 層級分組 → 合規判斷<br>　　Ch2：A4 校正 → YOLO 裁切 → TF 分類 → 幾何評分<br>　　Ch3：YOLO 紙張偵測 → ArUco 尺度校正 → 輪廓距離比計算<br>　　Ch4：彩色邊緣偵測 → 最大四邊形 → 折線量測<br>4. 計算 0–2 分評分<br>5. 產生標註影像，儲存至 `kid/{uid}/{task_id}_result.jpg`<br>6. 呼叫 POST `/scores/upsert` 寫入 MySQL（score_list + 任務子表）<br>7. 回傳 `{ok: true, score: 2, result_img_path: "..."}` |
| 後置條件 | 評分結果與標註影像路徑寫入 MySQL；施測端顯示分數 |

---

### UC03-E1　例外情節：遠端 API 逾時

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | AI 影像分析與評分 — 遠端 API 逾時 |
| 使用案例編號 | UC03-E1 |
| 執行者 | 施測者 |
| 前置條件 | Mac Mini 伺服器不可達，或網路不穩定導致 requests 逾時 |
| 例外情節 | 1. 施測端呼叫 POST `/api/analysis/submit`<br>2. 等待 Mac Mini 回應，超過逾時限制<br>3. requests 拋出 Timeout 例外<br>4. 後端回傳 `{success: false, error: "遠端 API 請求失敗"}` HTTP 500<br>5. 前端顯示「分析失敗，請重新提交」<br>6. 施測者可選擇重試或跳過此關卡 |
| 後置條件 | 未寫入任何分數；`score_list` 及任務子表不變 |

---

## 3.4　UC-04 成績管理與查詢

### UC04-N1　正常情節：管理者查詢成績

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | 查詢兒童歷史成績 |
| 使用案例編號 | UC04-N1 |
| 執行者 | 管理者 |
| 前置條件 | 管理者已登入後台；目標兒童至少有一筆施測紀錄 |
| 主要情節 | 1. 管理者於 admin.html 輸入目標 UID 並點選查詢<br>2. 前端送出 POST `/api/search-scores`，帶入 `{uid}`<br>3. 後端查詢 `score_list` 與各任務子表<br>4. 回傳歷次施測日期、各關卡得分與標註影像路徑<br>5. 前端以表格顯示歷次成績，提供管理者手動修改或刪除功能 |
| 後置條件 | 成績資料以表格呈現；資料庫不變 |

---

### UC04-E1　例外情節：無施測記錄

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | 查詢兒童歷史成績 — 無施測記錄 |
| 使用案例編號 | UC04-E1 |
| 執行者 | 管理者 |
| 前置條件 | 目標 UID 存在於 `user_list`，但從未完成任何施測 |
| 例外情節 | 1. 管理者輸入 UID 查詢<br>2. POST `/api/search-scores` 執行<br>3. MySQL 回傳空結果集<br>4. 後端回傳 `{success: true, data: []}`<br>5. 前端顯示「此兒童尚無施測記錄」 |
| 後置條件 | 畫面顯示提示訊息；資料庫不變 |

---

## 3.5　UC-05 生成 AI 居家建議

### UC05-N1　正常情節：生成並顯示 AI 建議

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | 生成 AI 居家建議 |
| 使用案例編號 | UC05-N1 |
| 執行者 | 家長／教師 |
| 前置條件 | AI_API_KEY 已設定於 `.env`；兒童至少有一筆施測紀錄；向量庫已初始化 |
| 主要情節 | 1. 家長開啟 parent_dashboard.html，帶入兒童 UID<br>2. 前端送出 GET `/api/ai_advice/<uid>`<br>3. 後端 PDMS2Advisor 查詢所有關卡最新成績，計算 score_signature<br>4. 查詢 `ai_advice_history`，快取未命中（score_signature 不符）<br>5. 篩選弱項（score < 2），對每個弱項進行向量相似度搜尋（Top-K=2）<br>6. 組裝 Prompt，呼叫 LLM 生成建議<br>7. 後處理（移除不當句子），寫入 `ai_advice_history` 快取<br>8. 回傳 `{ok: true, advice: "..."}`<br>9. 家長報告頁顯示成績總覽與 AI 居家建議 |
| 後置條件 | AI 建議顯示於報告頁；`ai_advice_history` 寫入新快取 |

---

### UC05-E1　例外情節：AI API 金鑰未設定

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | 生成 AI 居家建議 — API 金鑰未設定 |
| 使用案例編號 | UC05-E1 |
| 執行者 | 家長／教師 |
| 前置條件 | 系統未設定 `AI_API_KEY`（`.env` 中缺少或為空）|
| 例外情節 | 1. 家長開啟 parent_dashboard.html<br>2. GET `/api/ai_advice/<uid>` 執行<br>3. PDMS2Advisor 初始化時偵測到 `AI_API_KEY` 未設定，記錄 Warning MSG-008<br>4. 回傳固定文字「AI 顧問不可用。」HTTP 200<br>5. 家長報告頁正常顯示成績總覽<br>6. 建議欄位顯示「AI 顧問不可用」 |
| 後置條件 | 頁面正常載入；建議功能停用；`ai_advice_history` 不變；LLM API 未被呼叫 |

---

### UC05-E2　例外情節：快取命中，直接回傳建議

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | 生成 AI 居家建議 — 快取命中 |
| 使用案例編號 | UC05-E2 |
| 執行者 | 家長／教師 |
| 前置條件 | 兒童成績自上次生成建議後未變動，`ai_advice_history` 有對應快取 |
| 例外情節 | 1. 家長開啟 parent_dashboard.html<br>2. GET `/api/ai_advice/<uid>` 執行<br>3. PDMS2Advisor 計算 score_signature，查詢 `ai_advice_history`<br>4. score_signature 相符，快取命中<br>5. 直接回傳快取建議，不呼叫 LLM<br>6. 家長報告頁立即顯示建議（回應更快）|
| 後置條件 | `ai_advice_history` 不變；LLM API 未被呼叫；建議正常顯示 |

---

## 3.6　UC-06 系統設定與機器管理

### UC06-N1　正常情節：攝影機設定與 ROI 校正

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | 系統設定與機器管理 |
| 使用案例編號 | UC06-N1 |
| 執行者 | 施測者 |
| 前置條件 | 攝影機已連接 USB；施測端 Flask 正在運行 |
| 主要情節 | 1. 施測者進入 setting.html<br>2. 前端送出 GET `/camera-devices` 掃描所有可用攝影機<br>3. 後端回傳裝置清單，前端顯示可選攝影機列表<br>4. 施測者選擇俯視（Top）與側視（Side）攝影機索引<br>5. 施測者點選「校正 ROI」，送出 POST `/camera-settings/select-roi`<br>6. 後端開啟 OpenCV ROI 選取視窗，施測者拖拉選取區域<br>7. ROI 座標（x/y/w/h）回傳，前端顯示確認<br>8. 施測者點選「儲存」，送出 POST `/camera-settings`<br>9. 後端寫入 MySQL `machine_configs`（以 MACHINE_ID UUID 識別本機）<br>10. 前端顯示「設定已儲存」 |
| 後置條件 | 攝影機設定與 ROI 校正值寫入 `machine_configs`；下次施測時自動套用 |

---

### UC06-E1　例外情節：攝影機未偵測到

| 欄位 | 說明 |
|------|------|
| 使用案例名稱 | 系統設定與機器管理 — 攝影機未偵測到 |
| 使用案例編號 | UC06-E1 |
| 執行者 | 施測者 |
| 前置條件 | 施測端未連接任何攝影機，或裝置未被 OS 識別 |
| 例外情節 | 1. 施測者進入 setting.html，觸發 GET `/camera-devices`<br>2. 後端掃描所有攝影機索引，無任何裝置可用<br>3. 回傳 `{devices: []}` 空陣列<br>4. 前端顯示「未偵測到攝影機，請確認 USB 連線」<br>5. 施測者連接攝影機後，點選「重新掃描」觸發再次偵測 |
| 後置條件 | `machine_configs` 不變；設定未儲存 |
