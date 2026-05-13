# -*- coding: utf-8 -*-
import os
import sys
import cv2
import json
import numpy as np
from ultralytics import YOLO
from pathlib import Path
import socket
import uuid

try:
    import pymysql
except ImportError:
    pymysql = None

def _get_machine_id() -> str:
    """取得或生成本機識別碼（從上層 .env 或 fallback 為 hostname-based UUID）"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if line.startswith("MACHINE_ID="):
                    machine_id = line.split("=", 1)[1].strip()
                    if machine_id:
                        return machine_id
        except Exception:
            pass

    hostname = socket.gethostname()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, hostname))


def _read_env_value(key, default):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return default

    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            if not raw_line or raw_line.strip().startswith("#") or "=" not in raw_line:
                continue
            current_key, value = raw_line.split("=", 1)
            if current_key.strip() == key:
                try:
                    return float(value.strip())
                except Exception:
                    return default
    except Exception:
        return default

    return default


def _read_db_config(key: str, default):
    """優先從遠端 DB 讀取設定，失敗時回退至 .env 或回傳預設值"""
    if pymysql is None:
        return _read_env_value(key, default)

    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return default

    db_config = {}
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            if not raw_line or raw_line.strip().startswith("#") or "=" not in raw_line:
                continue
            k, v = raw_line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k in {"DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"}:
                db_config[k] = v
    except Exception:
        return _read_env_value(key, default)

    if not all(k in db_config for k in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME")):
        return _read_env_value(key, default)

    try:
        machine_id = _get_machine_id()
        conn = pymysql.connect(
            host=db_config["DB_HOST"],
            port=int(db_config["DB_PORT"]),
            user=db_config["DB_USER"],
            password=db_config["DB_PASSWORD"],
            database=db_config["DB_NAME"],
            charset="utf8mb4",
            autocommit=True,
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            sql_map = {
                "PDMS2_PX2CM": "px2cm",
                "PDMS2_CH4_T1_STANDARD_AREA": "standard_area",
            }
            if key not in sql_map:
                conn.close()
                return _read_env_value(key, default)

            col_name = sql_map[key]
            cur.execute(
                f"SELECT {col_name} FROM machine_configs WHERE machine_id=%s LIMIT 1",
                (machine_id,)
            )
            row = cur.fetchone()
            conn.close()

            if row and col_name in row:
                try:
                    return float(row[col_name])
                except Exception:
                    return _read_env_value(key, default)
    except Exception as e:
        print(f"[DB] 查詢遠端配置失敗: {e}，回退到本機 .env")

    return _read_env_value(key, default)
# --- 設定區 ---
BASE_DIR = Path(__file__).resolve().parent
YOLO_PATH = BASE_DIR / "best.pt"  # 確保這是 Segmentation 模型
ENV_PATH = BASE_DIR.parent / ".env"


def _read_env_float(key, default):
    if not ENV_PATH.exists():
        return default
    try:
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue
            current_key, value = raw_line.split("=", 1)
            if current_key.strip() == key:
                parsed = float(value.strip())
                return parsed if parsed > 0 else default
    except Exception:
        return default
    return default

def return_score(score):
    """回傳整數分數給作業系統或呼叫此程式的後端"""
    sys.exit(int(score))

def load_pixel_ratio(json_path):
    """讀取比例尺，若失敗則使用預設值"""
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            return float(data.get("pixel_per_cm", 16.70))
    except:
        return 16.70

def calculate_score(approx, px2cm):
    """評分邏輯：計算邊長、誤差並給分"""
    pts = approx.reshape(-1, 2)
    side_lengths_px = []
    for i in range(4):
        p1, p2 = pts[i], pts[(i + 1) % 4]
        side_lengths_px.append(np.linalg.norm(p1 - p2))
    
    # 轉換為公分並取兩位小數
    side_cm = sorted([round(d / px2cm, 2) for d in side_lengths_px])
    short_edges = side_cm[:2] # 抓取最短的兩邊作為 7.5cm 理論邊
    
    # 計算誤差
    d1 = abs(short_edges[0] - 7.5)
    d2 = abs(short_edges[1] - 7.5)
    max_err = round(max(d1, d2), 2)
    
    # 判定分數
    if d1 <= 0.3 and d2 <= 0.3:
        return 2, side_cm, max_err
    if d1 <= 1.2 and d2 <= 1.2:
        return 1, side_cm, max_err
    return 0, side_cm, max_err

def main():
    # 檢查是否由外部傳入 uid 和 img_id
    if len(sys.argv) <= 2:
        print("❌ 請提供 uid 與 img_id (例如: python script.py user123 img001)")
        return_score(-1)

    uid = sys.argv[1]
    img_id = sys.argv[2]
    
    # 自動組合輸入與輸出的路徑
    input_image = os.path.join("kid", uid, f"{img_id}.jpg")
    output_image = os.path.join("kid", uid, f"{img_id}_result.jpg")

    if not os.path.exists(input_image):
        print(f"❌ 找不到圖片檔案：{input_image}")
        return_score(-1)

    print("⏳ 正在載入 YOLO 模镸...")
    try:
        yolo = YOLO(YOLO_PATH)
        px2cm = _read_db_config("PDMS2_PX2CM", 16.70) # 載入比例尺
    except Exception as e:
        print(f"❌ 載入失敗: {e}")
        return_score(-1)

    print(f"\n🖼️ 正在處理: {input_image}")
    
    img_cv = cv2.imread(input_image)
    if img_cv is None: 
        print("❌ 無法讀取圖片")
        return_score(-1)
    
    # --- 預測開始 ---
    results = yolo(input_image, conf=0.7, verbose=False) 
    res_img = img_cv.copy() 
    final_score = -1 # 預設分數為 -1
    
    if results[0].masks is not None:
        # 只取第一個(或最大的)遮罩來計算，避免多重干擾
        mask_xy = results[0].masks.xy[0] 
        pts = np.array(mask_xy, np.int32).reshape((-1, 1, 2)) 
        
        # ==========================================
        # 🎨 畫圖專用：微幅平滑魔法 (消除鋸齒，保留真實形狀)
        smooth_pts = cv2.approxPolyDP(pts, 0.002 * cv2.arcLength(pts, True), True)
        
        # 🎯 算分數專用：強制擬合成 4 個頂點的四邊形 (不畫出來，只給數學算)
        approx_for_score = cv2.approxPolyDP(pts, 0.04 * cv2.arcLength(pts, True), True)
        if len(approx_for_score) != 4: 
            approx_for_score = cv2.approxPolyDP(pts, 0.07 * cv2.arcLength(pts, True), True)
        # ==========================================

        # --- 整合紅框的評分與 UI 邏輯 ---
        if len(approx_for_score) == 4:
            score, side_cm, err = calculate_score(approx_for_score, px2cm)
            final_score = score
            color = (0, 255, 0) if score == 2 else (0, 165, 255) if score == 1 else (0, 0, 255)
            
            # 畫出分數、誤差、邊長
            cv2.putText(res_img, f"Score: {score}", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)
            cv2.putText(res_img, f"Max Err: {err}cm", (50, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.putText(res_img, f"Sides: {side_cm}", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        else:
            final_score = -1
            color = (0, 0, 255) # 0分顯示紅色
            cv2.putText(res_img, "Score: -1", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)
            cv2.putText(res_img, f"Reason: Detected {len(approx_for_score)} pts", (50, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # ✨ 畫出「滑順版」的邊緣輪廓，線條粗細為 2，並套用剛剛判定的顏色！
        cv2.polylines(res_img, [smooth_pts], isClosed=True, color=color, thickness=2)
            
    else:
        final_score = -1
        cv2.putText(res_img, "Score: -1", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        cv2.putText(res_img, "Reason: No Target Detected", (50, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # 存檔
    cv2.imwrite(output_image, res_img)
    print(f"💾 已儲存評分結果圖至: {output_image}")
    
    # 印出分數並透過 sys.exit 回傳給系統
    print(f"score = {final_score}")
    return_score(final_score)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] ch4-t1 執行失敗: {e}")
        return_score(-1)