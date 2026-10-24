# 第四章：詞彙表

本詞彙表依課程第四章格式整理，涵蓋「運用 AI 技術判別精細動作之早期遲緩篩檢系統（FMD_AI_Screener）」之核心術語。  
依據設計文件書 FMD-DD-001 v1.0（2026-05-23）撰寫。

---

| 詞彙 | 定義（解釋） | 備註 |
|------|------------|------|
| PDMS-2 | Peabody Developmental Motor Scales, 2nd Edition（皮巴迪動作發展量表第二版）。適用於 0–7 歲兒童的標準化精細動作與粗動作評估工具，具良好信效度（重測 ICC = 0.98–0.99）。本系統以此量表為評分基準，選取 17 個精細動作子關卡。 | 系統評估基準量表 |
| 精細動作（Fine Motor Skill） | 涉及手部與手指精確協調的動作，如抓握、繪圖、剪紙、折紙及操作小物件，是 PDMS-2 評估的核心子量表之一，也是本系統的篩檢對象。 | 系統篩檢目標動作類型 |
| 發展遲緩（Developmental Delay） | 兒童在認知、動作、語言或社交等發展領域，較同齡兒童有明顯落後情形。本系統針對 4–6 歲兒童的精細動作遲緩進行早期篩檢。 | 系統服務目標對象 |
| 早期療育（Early Intervention） | 針對 0–6 歲有發展遲緩或障礙風險的兒童及家庭提供的服務，包含職能治療等。越早介入效果越佳，本系統旨在降低篩檢門檻以促進早期轉介。 | 系統服務宗旨 |
| UID（兒童唯一識別碼） | 系統為每位兒童指定的唯一字串識別碼（VARCHAR(50)），由管理者於後台建立。所有施測紀錄、AI 評分結果與影像資料皆以 UID 為關聯鍵，儲存於 MySQL。 | 資料庫關聯主鍵設計 |
| 子關卡（Task） | 依 PDMS-2 劃分的 17 個測驗項目，各有專屬 task_id（如 Ch1-t2、Ch2-t5）。每個子關卡有獨立的 AI 分析模組與 MySQL 任務子表（如 pyramid、draw_circle）。 | TASK_MAP 對照表定義 |
| 妙妙屋（Magic House） | 本系統設計的可攜式遊戲化測驗環境，由帳篷結構、14 吋 IPS 觸控螢幕（1920×1080）及 PW313D 雙鏡頭攝影機（俯視 + 側視）組成，提供故事情境包裝的測驗體驗。 | 硬體裝置名稱 |
| YOLO（You Only Look Once） | 單次前向傳遞完成物件偵測的深度學習模型（Ultralytics 8.3.217）。本系統使用 YOLO 在測驗影像中定位積木、紙張及剪紙輪廓等目標物件，輸出邊界框（Bounding Box）作為後續 SAM 分割的輸入。 | AI 評分第一層：偵測 |
| SAM（Segment Anything Model） | Meta 提出的通用影像分割模型。在 YOLO 偵測結果基礎上，精確切割目標物件的像素遮罩（Mask），供 Ch1 積木分析的骨架化與層級分組使用。 | AI 評分第二層：分割 |
| TensorFlow 分類模型 | 本系統訓練的影像分類深度學習模型（TensorFlow 2.20.0），用於 Ch2 圖形描繪題，辨識兒童描繪結果屬於圓形、橢圓、四邊形或十字等形狀類別。 | AI 評分第三層：分類 |
| 標準化評分（0–2 分制） | 依 PDMS-2 評分準則，以 0（完全無法完成）、1（部分完成）、2（完整完成）三級評估每項動作任務。每個子關卡評分後寫入對應的 MySQL 任務子表。 | 系統核心評分制度 |
| ArUco 標記 | 由黑白方格組成的視覺基準標記，貼附於測驗紙張。用於 Ch2 圖形描繪與 Ch3 剪紙的尺度校正，建立影像像素與實際公分（px2cm）之間的換算關係。 | 幾何量測校正工具 |
| 骨架化（Skeletonization） | 影像處理技術（scikit-image 0.24.0），將物件遮罩細化為單像素寬的骨架線。用於 Ch1 積木分析的端點偵測、線段方向判斷及層級分組。 | Ch1 積木分析步驟 |
| 非同步分析任務（Async Analysis Task） | 施測端透過 POST `/run-python` 啟動後台影像分析，取得 `task_id`，再輪詢 GET `/check-task/<task_id>` 取得結果。避免秒級推論阻塞前端 UI。 | 施測端架構設計模式 |
| RAG（Retrieval-Augmented Generation） | 結合 ChromaDB 向量資料庫檢索與 LLM 文字生成的 AI 技術。本系統以 `PDMS2Advisor` 類別實作，檢索 PDMS-2 相關文獻後生成個人化居家練習建議。 | AI 建議模組核心技術 |
| PDMS2Advisor | 本系統 RAG 模組的核心類別（`utils/rag_advisor.py`）。負責初始化 Embedding 模型（all-MiniLM-L6-v2）、建立 ChromaDB 向量索引，並依兒童弱項（score < 2）生成職能治療師等級的居家建議。 | AI 服務層主要類別 |
| score_signature（成績指紋） | `PDMS2Advisor` 為避免重複呼叫 LLM 的快取機制，將兒童所有關卡最新成績序列化為字串。若相同則直接從 `ai_advice_history` 資料表回傳快取建議，不再呼叫 LLM。 | RAG 效能優化機制 |
| ChromaDB | 開源向量資料庫（ChromaDB 1.5.9），用於儲存 PDMS-2 知識庫文件的 Embedding 向量，供 PDMS2Advisor 進行相似度搜尋（Top-K=2）。 | RAG 知識庫儲存引擎 |
| 施測端（TestingApp） | 以 `PDMS2_web/run.py`（port 8000）運行的 Flask 應用，部署於施測現場 Windows 11 PC。負責相機控制、UID Session 管理及呼叫遠端 Mac Mini 分析 API。 | 三層架構：施測端 |
| 分析伺服器（ServerApp） | 以 `MacWeb/web.py`（port 3000）運行的 Flask 應用，部署於 Mac Mini M2 Pro。負責接收影像、執行 YOLO/SAM/TensorFlow 重量級 AI 推論，並回傳評分結果。 | 三層架構：分析伺服器 |
| 管理端（AdminApp） | 以 `PDMS2_web/admin.py`（port 8001）運行的 Flask 應用。提供兒童帳號 CRUD、成績查詢與修改、管理者帳號管理等功能。 | 三層架構：管理端 |
| Tailscale VPN | 基於 WireGuard 的點對點 VPN 工具，用於施測端 PC 與 Mac Mini 伺服器之間的加密通訊，使外網環境下的巡迴施測也能安全存取分析 API。 | 網路安全基礎設施 |
| DEMO_MODE | 系統支援的展示模式（`.env` 設定 `DEMO_MODE=true`），在無實體攝影機的環境下：攝影機啟動模擬成功，拍照改讀取預存圖片，AI 分析流程照常執行。 | 測試與展示設計 |
| machine_configs（機器設定表） | MySQL 資料表，以 UUID（machine_id）識別每台施測機器，儲存攝影機索引（top/side）、ROI 座標（x/y/w/h）、px2cm 換算比例等校正值，支援多機部署集中管理。 | 多機同步設計 |
| admin_users（管理者帳號表） | MySQL 資料表，儲存管理者帳號、密碼雜湊（password_hash）、電子郵件與權限等級（level 1=一般管理者，2=進階，3=超級管理者）。 | 使用者權限架構 |
