from PaperDetector_yolo import PaperDetector_yolo
from BoxDistanceAnalyzer import BoxDistanceAnalyzer
from Draw_square import Draw_square

import cv2
import json
import sys
import os
from pathlib import Path
import socket
import uuid

try:
    import pymysql
except ImportError:
    pymysql = None


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"


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


def return_score(score):
    sys.exit(int(score))


if __name__ == "__main__":
    score = -1
    if len(sys.argv) <= 2:
        print("缺少參數，使用方式: python main.py <uid> <img_id>")
        return_score(score)

    uid = sys.argv[1]
    img_id = sys.argv[2]
    image_path = os.path.join("kid", uid, f"{img_id}.jpg")
    if not os.path.exists(image_path):
        print(f"找不到圖片: {image_path}")
        return_score(score)

    print(f"\n正在處理圖片: {image_path}")
    print("====使用 YOLO 提取紙張區域====")

    kid = None
    try:
        pixel_per_cm = _read_db_config("PDMS2_PX2CM", 19.597376925845985)

        detector = PaperDetector_yolo(image_path)
        detector.detect_paper_by_yolo()
        if detector.result is not None:
            detected_path = os.path.join("kid", uid, f"{img_id}_detected.jpg")
            cv2.imwrite(detected_path, detector.result)
            print(f"偵測框圖片已儲存: {detected_path}")

        detector_path = None
        if detector.original is not None:
            region = detector.extract_paper_region()
            if region is not None:
                detector_path = detector.save_results()

        print("====使用 object mask + ArUco 紅框評分====")
        if detector_path:
            if detector.object_mask_points_warped is None:
                print("原圖未偵測到 object mask，無法進行方形評分")
                detector_path = None

        if detector_path:
            draw_result = Draw_square(detector_path)
            if draw_result is not None:
                D_sq_path, black_corners_int = draw_result
                if D_sq_path is not None:
                    analyzer = BoxDistanceAnalyzer(
                        box1=black_corners_int,
                        image_path=detector_path,
                        mask_points=detector.object_mask_points_warped,
                        largest_mask_contour=detector.object_mask_largest_contour_warped,
                    )
                    result = analyzer.analyze(pixel_per_cm=pixel_per_cm)
                    if result is not None:
                        result_img, kid = result
                        result_path = os.path.join("kid", uid, f"{img_id}_result.jpg")
                        cv2.imwrite(result_path, result_img)

        if kid is not None:
            if kid < 0.6:
                print(f"kid = {kid:.2f}, score = 2")
                score = 2
            elif kid < 1.2:
                print(f"kid = {kid:.2f}, score = 1")
                score = 1
            else:
                print(f"kid = {kid:.2f}, score = 0")
                score = 0
        else:
            print("裁切或距離分析失敗，score = -1")
    except Exception as e:
        print(f"流程執行失敗: {e}")

    return_score(score)
