# 運用 AI 技術判別精細動作之早期遲緩篩檢系統

> 這個分支（`doc`）只放專案的報告與文件，不含程式碼。程式碼請見 [`main` 分支](https://github.com/hannshushua/PDMS2-AI-Screener/tree/main)。

**專案名稱：** AI-based Early Screening System for Fine Motor Developmental Delay Identification  
**系統簡稱：** FMAS（妙妙屋 AI 精細動作篩檢系統）  
**團隊名稱：** 現在發現還不遲，你說對不隊（獵遲小隊）  
**團隊成員：** 洪偉城、林政維、呂昊宸、林宛瑩  
**指導教授：** 趙一平教授  
**文件版本：** v2.0（2026-06-01）

[![Python 3.10+](https://img.shields.io/badge/Python-3.10-blue.svg)](https://www.python.org/) [![Frontend](https://img.shields.io/badge/Frontend-HTML5%2FCSS3%2FJavaScript-E34F26.svg)](https://developer.mozilla.org/docs/Web) [![Backend](https://img.shields.io/badge/Backend-Flask-black.svg)](https://flask.palletsprojects.com/) [![Database](https://img.shields.io/badge/Database-MySQL%208.0+-4479A1.svg)](https://www.mysql.com/) [![CV](https://img.shields.io/badge/Computer%20Vision-OpenCV-green.svg)](https://opencv.org/) [![Model](https://img.shields.io/badge/Model-YOLO-red.svg)](https://github.com/ultralytics) [![Segmentation](https://img.shields.io/badge/Segmentation-SAM-purple.svg)](https://github.com/facebookresearch/segment-anything) [![DL](https://img.shields.io/badge/Deep%20Learning-TensorFlow%2FPyTorch-EE4C2C.svg)](https://www.tensorflow.org/)

---

## 介紹影片

- [運用 AI 技術判別精細動作之早期遲緩篩檢系統介紹影片](https://www.youtube.com/watch?v=FlGjlvIecec&feature=youtu.be)
- [第二次報告影片](https://youtu.be/MkSqsJYiUxs)

---

## 目錄

1. [專案摘要](#1-專案摘要)
2. [問題與目標族群](#2-問題與目標族群)
3. [系統完成度](#3-系統完成度)
4. [軟硬體與部署](#4-軟硬體與部署)
5. [可執行檔與操作步驟](#5-可執行檔與操作步驟)
6. [驗證結果與限制](#6-驗證結果與限制)
7. [文件索引](#7-文件索引)
8. [參考資料](#8-參考資料)

---

## 1. 專案摘要

本專題是一套結合 **兒童精細動作篩檢、影像 AI 判讀、RAG 居家建議、MySQL 紀錄與雙端 Web 介面** 的早期遲緩篩檢系統。系統以 **PDMS-2（Peabody Developmental Motor Scales-2）** 為評分基準，將測驗流程遊戲化，讓非職能治療師人員也能完成初步篩檢與結果整理。

一句話版本：**把 PDMS-2 的精細動作測驗做成可攜式、可追蹤、可自動分析的篩檢系統。**

### 這個專題做了什麼

- 施測端提供兒童測驗流程與關卡操作。
- 管理端提供兒童資料、測驗紀錄與結果查詢。
- MacWeb 提供影像分析與結果回傳。
- RAG 模組提供個別化居家建議。
- MySQL 負責保存兒童、關卡與測驗資料。

### 目前完成到哪裡

- 已完成 17 個 PDMS-2 子關卡的系統化整合，涵蓋積木、圖形描繪、剪紙、折紙與儀器題。
- 已完成施測端、管理端與 AI 分析伺服器的分工架構。
- 已完成 RAG 居家建議流程與測試報告產出。
- 已完成物件導向設計文件，對應課程第 4 到第 8 章。

---

## 2. 問題與目標族群

### 問題背景

兒童發展遲緩若無法及早辨識，常會錯過黃金介入期。偏鄉或資源不足地區更容易因為人力、設備與評估流程限制，而讓診斷與介入延後。

本專題希望解決的不是單純「做一個測驗網站」，而是以下三件事：

1. 讓兒童篩檢流程更容易被執行。
2. 讓評分與紀錄更標準化。
3. 讓結果可以被後續追蹤與轉介使用。

### 目標族群

- **施測者**：衛生所、幼兒園、社區或巡迴篩檢現場的人員。
- **管理者**：需要查看歷史紀錄、管理兒童資料與成績的人員。
- **家長**：需要理解孩子表現與後續居家練習方向的人。
- **孩童**：實際接受測驗的 4 至 6 歲兒童。

### 設計目標

- 降低測驗門檻。
- 減少人工逐張判讀壓力。
- 保留原始測驗與結果紀錄。
- 讓使用者從系統中得到可執行的後續建議。

---

## 3. 系統完成度

### 系統功能一覽

| 功能 | 完成內容 | 狀態 |
|------|----------|------|
| 施測端 | 提供測驗流程、子關卡切換、影像與結果傳遞 | 已完成 |
| 管理端 | 查詢、管理、結果與使用者資料操作 | 已完成 |
| AI 分析 | 影像分析伺服器與關卡對應分析流程 | 已完成 |
| RAG 建議 | 依測驗結果生成居家練習建議 | 已完成 |
| 資料保存 | MySQL 紀錄、影像檔案與分析結果追蹤 | 已完成 |
| 文件化 | 說明文件、使用案例、活動圖與類別圖 | 已完成 |

### 關卡覆蓋範圍

系統目前整合了 17 個 PDMS-2 子關卡，覆蓋以下題型：

- Ch1 積木建構
- Ch2 圖形描繪
- Ch3 剪紙
- Ch4 折紙
- Ch5 側重儀器

### 核心技術流程

1. 施測端蒐集影像與互動資料。
2. AI 伺服器進行偵測、分割、尺度校正或幾何分析。
3. 系統將分析結果回傳資料庫。
4. 管理端與 RAG 模組根據結果產出可閱讀的建議。

### 系統特色

- **遊戲化測驗**：把測驗包裝成故事情境，降低兒童抗拒。
- **多模型分析**：依題型使用 YOLO、SAM、TensorFlow 與幾何規則。
- **可追蹤資料**：測驗結果、影像與建議可持續保存。
- **雙端部署**：施測端與分析伺服器分離，便於實際部署。

---

## 4. 軟硬體與部署

### 硬體需求

- 施測用電腦：Intel i5 等級以上，建議 8GB RAM 以上。
- 攝影機：雙鏡頭或相容 USB 攝影機。
- 顯示器：觸控螢幕佳，便於兒童互動。
- 分析主機：Mac Mini 或其他可執行 AI 服務的主機。
- 資料庫主機：MySQL 8.0+。

### 軟體需求

- Windows 11 或 macOS。
- Python 3.10 以上。
- Git。
- MySQL 8.0+。
- Chrome 或 Edge。

### 專案結構（`main` 分支）

```text
PDMS2-AI-Screener/
├── PDMS2_web/                 施測端與管理端
│   ├── run.py                 施測端主程式
│   ├── admin.py               管理端主程式
│   ├── scripts/               測試與輔助腳本
│   ├── ch1-t1 ~ ch5-t1/       各關卡分析模組
│   └── requirements.txt       施測端依賴
├── MacWeb/
│   ├── web.py                 分析伺服器主程式
│   └── requirements.txt       分析伺服器依賴
├── doc/                       專案文件
└── picture/                   圖片素材
```

### 必要環境變數

這些值通常放在 `PDMS2_web/.env`，`MacWeb/web.py` 也會讀取同一份設定：

- `PDMS_DATA_ROOT`：測驗資料與影像儲存根目錄。
- `DB_HOST`、`DB_PORT`、`DB_USER`、`DB_PASSWORD`、`DB_NAME`：MySQL 連線設定。
- `WEB_SECRET_KEY`：Web session 金鑰。
- `IMAGE_SIGN_SECRET`：圖片簽章金鑰。
- `MACWEB_BASE_URL`：分析伺服器位址，預設為 `http://127.0.0.1:3000`。
- `REMOTE_CONFIG_SYNC`：是否同步遠端設定。

### 建議部署順序

1. 先啟動 MacWeb 分析伺服器。
2. 再啟動施測端。
3. 最後視需要啟動管理端。

---

## 5. 可執行檔與操作步驟

### 主要可執行檔（位於 `main` 分支）

| 檔案 | 用途 | 建議執行方式 |
|------|------|--------------|
| [PDMS2_web/run.py](https://github.com/hannshushua/PDMS2-AI-Screener/blob/main/PDMS2_web/run.py) | 施測端主程式 | `python PDMS2_web/run.py` |
| [PDMS2_web/admin.py](https://github.com/hannshushua/PDMS2-AI-Screener/blob/main/PDMS2_web/admin.py) | 管理端主程式 | `python PDMS2_web/admin.py` |
| [MacWeb/web.py](https://github.com/hannshushua/PDMS2-AI-Screener/blob/main/MacWeb/web.py) | AI 分析伺服器 | `python MacWeb/web.py` |
| [PDMS2_web/scripts/rag_tester.py](https://github.com/hannshushua/PDMS2-AI-Screener/blob/main/PDMS2_web/scripts/rag_tester.py) | RAG 測試腳本 | `python PDMS2_web/scripts/rag_tester.py` |
| [PDMS2_web/scripts/camtest.py](https://github.com/hannshushua/PDMS2-AI-Screener/blob/main/PDMS2_web/scripts/camtest.py) | 攝影機測試腳本 | `python PDMS2_web/scripts/camtest.py` |

### 安裝步驟

1. 取得專案。

```bash
git clone https://github.com/hannshushua/PDMS2-AI-Screener.git
cd PDMS2-AI-Screener
```

2. 建立虛擬環境。

```powershell
python -m venv .venv39
.\.venv39\Scripts\Activate.ps1
```

3. 安裝施測端依賴。

```bash
pip install -r PDMS2_web/requirements.txt
```

4. 安裝分析伺服器依賴。

```bash
pip install -r MacWeb/requirements.txt
```

5. 建立或修改 `PDMS2_web/.env`，填入前面列出的環境變數。

### 執行步驟

1. 啟動分析伺服器。

```bash
python MacWeb/web.py
```

2. 啟動施測端。

```bash
python PDMS2_web/run.py
```

3. 若要管理資料，另開終端執行管理端。

```bash
python PDMS2_web/admin.py
```

### 測試步驟

1. 先做服務啟動測試：確認 `MacWeb/web.py`、`run.py`、`admin.py` 都能正常啟動。
2. 再做攝影機測試：執行 `PDMS2_web/scripts/camtest.py`。
3. 再做 RAG 測試：執行 `PDMS2_web/scripts/rag_tester.py`。
4. 最後進行各關卡流程測試，確認影像上傳、分析回傳與結果紀錄正常。

### 標準安裝順序建議

若是第一次部署，建議順序如下：

1. 安裝 Python 與 Git。
2. 安裝 `PDMS2_web` 與 `MacWeb` 的依賴。
3. 準備 MySQL 與 `.env`。
4. 啟動 MacWeb。
5. 啟動施測端。
6. 啟動管理端。
7. 再做 RAG 與攝影機驗證。

---

## 6. 驗證結果與限制

### 驗證結果

本專題除了完成系統整合，也實際產出 RAG 測試結果。四次測試摘要如下：

- 2026-05-19 01:48:08：Ch1、Ch2、Ch3 皆 success，分數 100/100
- 2026-05-19 01:46:54：Ch1、Ch2、Ch3 皆 success，分數 100/100
- 2026-05-19 01:44:18：Ch1 100/100，Ch2 70/100，Ch3 100/100
- 2026-05-19 01:42:59：Ch1、Ch2、Ch3 皆 success，分數 50/100

整體來看，RAG 建議流程已可穩定產出結果，且在較新的測試中已達到 100/100 的完整案例表現。

### 我們做到的程度

- 已完成從題目資料、影像分析、結果儲存到建議生成的完整流程。
- 已完成可實際啟動的多端架構，而不是只有單一腳本示範。
- 已完成課程要求的詞彙表、使用案例圖、使用案例描述、活動圖與類別圖。
- 已完成 RAG 的查詢與建議生成，並能輸出測試報告。

### 目前限制

- 這是一套依賴攝影機、影像品質與現場擺位的系統，實際表現會受硬體與環境影響。
- MySQL、`.env`、模型檔與資料根目錄都必須先設定好，否則服務無法完整啟動。
- 不同題型依賴不同分析模組，因此某些關卡在特定硬體或權重檔未備齊時，可能只能部分運作。
- 測試報告目前主要驗證 RAG 生成流程，若要作為正式部署依據，仍建議再做現場實機測試。

---

## 7. 文件索引

### [第一次報告](第一次報告/)（期中）

| 檔案 | 說明 |
| --- | --- |
| [114期中_大學部軟硬體專題.pdf](第一次報告/114期中_大學部軟硬體專題.pdf) | 期中報告簡報 |
| [軟硬體專題需求規格書.pdf](第一次報告/軟硬體專題需求規格書.pdf) | 需求規格書 |

### [第二次報告](第二次報告/)（期末）

| 檔案 | 說明 |
| --- | --- |
| [114 大學部軟硬體專題for期末.pdf](第二次報告/114%20大學部軟硬體專題for期末.pdf) | 期末報告簡報 |
| [設計文件書_FMD_AI_Screener.md](第二次報告/設計文件書_FMD_AI_Screener.md) | 設計文件書（FMD-DD-001） |

### [物件導向程式設計期末報告](物件導向程式設計期末報告/)

物件導向程式設計課程期末專題設計文件，依設計文件書 FMD-DD-001 v1.0 撰寫，對應課程第 4 至第 8 章。所有 UML 圖表使用 Mermaid 語法撰寫，可直接於 GitHub 檢視。

| 檔案 | 說明 |
| --- | --- |
| [使用案例規格與詞彙表_FMD_AI_Screener.md](物件導向程式設計期末報告/使用案例規格與詞彙表_FMD_AI_Screener.md) | 使用案例規格與詞彙表（FMD-UC-001，合併版） |
| [ch04-vocabulary.md](物件導向程式設計期末報告/ch04-vocabulary.md) | 第四章：詞彙表 |
| [ch05-use-case-diagrams.md](物件導向程式設計期末報告/ch05-use-case-diagrams.md) | 第五章：使用案例圖 |
| [ch06-use-case-descriptions.md](物件導向程式設計期末報告/ch06-use-case-descriptions.md) | 第六章：使用案例描述 |
| [ch07-activity-diagrams.md](物件導向程式設計期末報告/ch07-activity-diagrams.md) | 第七章：活動圖 |
| [ch08-class-diagram.md](物件導向程式設計期末報告/ch08-class-diagram.md) | 第八章：類別圖 |

#### 使用案例功能域總覽

| UC | 功能域 | 主要執行者 | 簡述 |
|----|--------|-----------|------|
| UC-01 | 兒童帳號管理 | 管理者 | 兒童 UID 建立、查詢、刪除 |
| UC-02 | 進行精細動作測驗 | 施測者、兒童 | 妙妙屋情境化測驗，完成 17 個 PDMS-2 子關卡 |
| UC-03 | AI 影像分析與評分 | AI 分析引擎 | YOLO、SAM、幾何規則與分類模型輸出 0-2 分 |
| UC-04 | 成績管理與查詢 | 管理者、家長 | 分項得分查詢、手動修改、成績歷史追蹤 |
| UC-05 | 生成 AI 居家建議 | PDMS2Advisor（RAG） | 依測驗結果生成個人化練習建議 |
| UC-06 | 系統設定與機器管理 | 超級管理者、施測者 | 攝影機校正、px2cm 設定、帳號管理 |

### [doc](doc/)（專案文件）

| 檔案 | 說明 |
| --- | --- |
| [系統架構.md](doc/系統架構.md) | 系統架構說明書：模組、介面與資料流 |
| [團隊分工.md](doc/團隊分工.md) | 團隊分工項目清單 |
| [幼兒版任務口白稿.md](doc/幼兒版任務口白稿.md) | 2–6 歲幼兒版任務口白稿 |
| [測試計畫書.pdf](doc/測試計畫書.pdf) | 測試計畫書 |
| [軟硬體專題需求規格書.pdf](doc/軟硬體專題需求規格書.pdf) | 需求規格書 |
| [114期中_大學部軟硬體專題.pdf](doc/114期中_大學部軟硬體專題.pdf) | 期中報告簡報 |

---

## 8. 參考資料

1. Guralnick (2011), Why Early Intervention Works: A Systems Perspective.
2. CDC, Learn the Signs. Act Early: Early Intervention.
3. 衛生福利部與相關早療統計資料。
4. Relebo et al. (2021), PDMS-2 驗證研究。
5. 本專案內部測試報告與課程文件。

---

## 獲得的獎項

- [114年度「為桃園做研究」桃園市政府大專校院學生創新點子及研究實作競賽 金質研究獎](https://sccdc.tycg.gov.tw/News_Content.aspx?n=16792&s=1600221#lg=1&slide=1)
- [2025 全國 AI 專題創意競賽 佳作](https://phpweb2.nutn.edu.tw/ilt/wordpress/wp-content/uploads/2025/12/%E6%B1%BA%E8%B3%BD%E7%B5%90%E6%9E%9C.pdf)
