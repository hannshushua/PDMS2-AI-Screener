# 第七章：活動圖

本章依課程第七章格式，根據 6 個使用案例圖及其配合的使用案例描述，各提供一張完整活動圖。  
依據設計文件書 FMD-DD-001 v1.0（2026-05-23）撰寫，圖表使用 Mermaid `flowchart TD` 語法。

---

## UC-01　兒童帳號管理活動圖

```mermaid
flowchart TD
    Start([開始]) --> A[管理者登入管理後台]
    A --> B{選擇操作}

    B -->|新增| C[輸入 UID、姓名、生日]
    C --> D{UID 格式正確?}
    D -->|否| E[顯示格式錯誤]
    E --> C
    D -->|是| F{UID 已存在?}
    F -->|是| G[顯示 UID 重複錯誤]
    G --> C
    F -->|否| H[POST /api/user/add 寫入 MySQL]
    H --> I[POST /create-uid-folder 建立目錄]
    I --> J[顯示新增成功]
    J --> End([結束])

    B -->|查詢| K[輸入目標 UID]
    K --> L[POST /api/search-scores 查詢]
    L --> M{有資料?}
    M -->|否| N[顯示無施測記錄提示]
    N --> End
    M -->|是| O[以表格顯示兒童資料與成績]
    O --> End

    B -->|刪除| P[選擇目標兒童]
    P --> Q{確認刪除?}
    Q -->|否| End
    Q -->|是| R[DELETE /users 刪除帳號]
    R --> S[顯示刪除成功]
    S --> End
```

---

## UC-02　進行精細動作測驗活動圖

```mermaid
flowchart TD
    Start([開始]) --> A[施測者輸入兒童 UID]
    A --> B[POST /session/set-uid]
    B --> C{UID 存在?}
    C -->|否| D[顯示 USER_NOT_FOUND MSG-001]
    D --> A
    C -->|是| E[Session 設定成功]
    E --> F[選擇測驗關卡]
    F --> G[POST /opencv-camera/start 啟動攝影機]
    G --> H{攝影機開啟成功?}
    H -->|否| I[顯示 MSG-003 相機無法開啟]
    I --> J[施測者至設定頁更新索引]
    J --> G
    H -->|是| K[GET /opencv-camera/frame 顯示即時預覽]
    K --> L[兒童執行測驗任務]
    L --> M[施測者按下拍照]
    M --> N[POST /opencv-camera/capture 儲存影像]
    N --> O[POST /run-python 啟動後台分析]
    O --> P[取得 task_id]
    P --> Q[輪詢 GET /check-task/task_id]
    Q --> R{分析完成?}
    R -->|否| Q
    R -->|是| S[顯示評分結果與標註影像]
    S --> T{繼續下一關卡?}
    T -->|是| F
    T -->|否| End([結束])
```

---

## UC-03　AI 影像分析與評分活動圖

```mermaid
flowchart TD
    Start([開始]) --> A[施測端送出 POST /api/analysis/submit]
    A --> B[Mac Mini 接收影像與 task_id]
    B --> C{依 task_id 選擇分析模組}

    C -->|Ch1 積木| D1[YOLO 偵測積木位置]
    D1 --> D2[SAM 分割遮罩]
    D2 --> D3[骨架化 + 層級分組]
    D3 --> D4[合規判斷評分]
    D4 --> Score[計算 0–2 分]

    C -->|Ch2 圖形| E1[A4 透視校正]
    E1 --> E2[YOLO 裁切目標區域]
    E2 --> E3[TensorFlow 形狀分類]
    E3 --> E4[幾何評分]
    E4 --> Score

    C -->|Ch3 剪紙| F1[YOLO 紙張偵測]
    F1 --> F2[ArUco 尺度校正]
    F2 --> F3[輪廓距離比計算]
    F3 --> Score

    C -->|Ch4 折紙| G1[彩色邊緣偵測]
    G1 --> G2[最大面積四邊形]
    G2 --> G3[折線精確度量測]
    G3 --> Score

    Score --> H{分析成功?}
    H -->|否| I[回傳 HTTP 500 分析失敗]
    I --> J[前端顯示分析失敗訊息]
    J --> End([結束])
    H -->|是| K[產生標註影像]
    K --> L[POST /scores/upsert 寫入 MySQL]
    L --> M[回傳 score 與 result_img_path]
    M --> N[施測端顯示評分結果]
    N --> End
```

---

## UC-04　成績管理與查詢活動圖

```mermaid
flowchart TD
    Start([開始]) --> A[管理者進入 admin.html]
    A --> B{選擇操作}

    B -->|查詢| C[輸入目標 UID]
    C --> D[POST /api/search-scores]
    D --> E{有施測記錄?}
    E -->|否| F[顯示「尚無施測記錄」]
    F --> End([結束])
    E -->|是| G[以表格顯示歷次成績]
    G --> End

    B -->|新增或修改| H[輸入 uid, task_id, score, test_date]
    H --> I[POST /scores/upsert]
    I --> J{寫入成功?}
    J -->|否| K[顯示資料庫錯誤]
    K --> H
    J -->|是| L[顯示「成績已更新」]
    L --> End

    B -->|刪除| M[選擇目標成績紀錄]
    M --> N{確認刪除?}
    N -->|否| End
    N -->|是| O[DELETE /scores]
    O --> P[顯示「成績已刪除」]
    P --> End
```

---

## UC-05　生成 AI 居家建議活動圖

```mermaid
flowchart TD
    Start([開始]) --> A[家長開啟 parent_dashboard.html]
    A --> B[GET /api/ai_advice/uid]
    B --> C{AI_API_KEY 已設定?}
    C -->|否| D[記錄 Warning MSG-008]
    D --> E[回傳「AI 顧問不可用」]
    E --> F[報告頁正常載入，建議欄顯示停用訊息]
    F --> End([結束])

    C -->|是| G[查詢兒童所有關卡最新成績]
    G --> H[計算 score_signature 成績指紋]
    H --> I[查詢 ai_advice_history]
    I --> J{score_signature 相符?}
    J -->|是| K[直接回傳快取建議]
    K --> L[家長報告頁立即顯示建議]
    L --> End

    J -->|否| M[篩選弱項 score < 2]
    M --> N[對每個弱項向量相似度搜尋 Top-K=2]
    N --> O[組裝 Prompt 呼叫 LLM]
    O --> P{LLM 回應成功?}
    P -->|否| Q[回傳錯誤提示]
    Q --> End
    P -->|是| R[後處理建議文字]
    R --> S[寫入 ai_advice_history 快取]
    S --> T[家長報告頁顯示成績與建議]
    T --> End
```

---

## UC-06　系統設定與機器管理活動圖

```mermaid
flowchart TD
    Start([開始]) --> A[施測者進入 setting.html]
    A --> B[GET /camera-devices 掃描攝影機]
    B --> C{找到可用攝影機?}
    C -->|否| D[顯示「未偵測到攝影機，請確認 USB 連線」]
    D --> E{施測者連接攝影機後重新掃描?}
    E -->|否| End([結束])
    E -->|是| B

    C -->|是| F[顯示裝置清單]
    F --> G[施測者選擇俯視與側視攝影機索引]
    G --> H[施測者點選「校正 ROI」]
    H --> I[POST /camera-settings/select-roi]
    I --> J{ROI 子行程成功?}
    J -->|否| K[記錄 MSG-009 ROI 選取失敗]
    K --> H
    J -->|是| L[ROI 座標回傳顯示確認]
    L --> M[施測者點選「儲存設定」]
    M --> N[POST /camera-settings 寫入 machine_configs]
    N --> O[顯示「設定已儲存」]
    O --> P{超級管理者需要同步遠端設定?}
    P -->|否| End
    P -->|是| Q[觸發 machine_configs 遠端同步]
    Q --> R{同步成功?}
    R -->|否| S[記錄 MSG-010 遠端同步失敗]
    S --> End
    R -->|是| T[顯示「同步完成」]
    T --> End
```
