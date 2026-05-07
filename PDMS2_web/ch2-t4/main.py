# main.py — 單線分析
# 輸入：kid\<uid>\<img_id>.jpg
# 輸出結果圖：kid\<uid>\<img_id>_result.jpg，並以 exit code 回傳分數

import os
import json
import cv2
import sys
from pathlib import Path
from final import find_baseline_and_show_all
import socket
import uuid

try:
    import pymysql
except ImportError:
    pymysql = None

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"
DEFAULT_PX2CM = 1.0


def _read_env_value(key, default):
    """從 .env 讀取值"""
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


def _get_machine_id() -> str:
    """取得或生成本機識別碼"""
    if ENV_PATH.exists():
        try:
            for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if line.startswith("MACHINE_ID="):
                    machine_id = line.split("=", 1)[1].strip()
                    if machine_id:
                        return machine_id
        except Exception:
            pass
    hostname = socket.gethostname()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, hostname))


def _read_db_config(key: str, default: float) -> float:
    """優先從資料庫讀取本機配置，失敗時回退到 .env"""
    if pymysql is None:
        return _read_env_value(key, default)
    
    if not ENV_PATH.exists():
        return default
    
    db_config = {}
    try:
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue
            k, v = raw_line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k in {"DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"}:
                db_config[k] = v
    except Exception:
        return _read_env_value(key, default)
    
    if not all(k in db_config for k in ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]):
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
            sql_map = {"PDMS2_PX2CM": "px2cm"}
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
                parsed = float(row[col_name])
                return parsed if parsed > 0 else default
    except Exception as e:
        print(f"[DB] 查詢遠端配置失敗: {e}，回退到本機 .env", file=sys.stderr)
    
    return _read_env_value(key, default)


def _read_env_float(key, default):
    """向後相容：改用 _read_db_config"""
    return _read_db_config(key, default)


def return_score(score: int):
    """用 exit code 回傳分數（與 ch2-t5 / ch3-t1 一致）"""
    sys.exit(int(score))


def main():
    # ========= 1) 讀比例檔 (優先從遠端資料庫) =========
    pixel_per_cm = _read_db_config("PDMS2_PX2CM", DEFAULT_PX2CM)
    if pixel_per_cm <= 0:
        print(".env 內的 PDMS2_PX2CM 非正值", file=sys.stderr)
        return_score(-1)

    # ========= 2) 解析參數（與其他關卡介面一致） =========
    if len(sys.argv) > 2:
        uid = sys.argv[1]
        img_id = sys.argv[2]
        image_path = os.path.join("kid", uid, f"{img_id}.jpg")
    else:
        print("參數不足，需要 uid 與 img_id", file=sys.stderr)
        return_score(-1)

    if not os.path.exists(image_path):
        print(f"找不到圖片：{image_path}", file=sys.stderr)
        return_score(-1)

    # ========= 3) 讀影像 =========
    img = cv2.imread(image_path)
    if img is None:
        print(f"圖片讀取失敗：{image_path}", file=sys.stderr)
        return_score(-1)

    # ========= 4) 分析（盡量相容：優先取回 (score, result_img)） =========
    result_img = None
    try:
        # 新版：回傳 (score, result_img)
        score, result_img = find_baseline_and_show_all(img, pixel_per_cm)
    except TypeError:
        # 舊版只回傳 score
        score = find_baseline_and_show_all(img, pixel_per_cm)
        result_img = img  # 至少把原圖當成結果圖

    # ========= 5) 準備輸出路徑：kid/<uid>/<img_id>_result.jpg =========
    result_dir = os.path.join("kid", uid)
    os.makedirs(result_dir, exist_ok=True)
    out_path = os.path.join(result_dir, f"{img_id}_result.jpg")

    # 沒有 result_img 的話就存原圖
    to_save = result_img if result_img is not None else img
    ok = cv2.imwrite(out_path, to_save)
    if not ok:
        print(f"⚠️ 影像儲存失敗：{out_path}", file=sys.stderr)
        # 但還是回傳分數，避免整個流程中斷

    print("完成結果圖：", out_path)
    print("得分：", score)

    # ========= 6) 用 exit code 回傳分數 =========
    return_score(score)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] ch2-t4 執行失敗: {e}", file=sys.stderr)
        return_score(-1)
