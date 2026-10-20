import torch

_original_torch_load = torch.load
def _safe_load(*args, **kwargs):
    # 如果呼叫時沒有特別指定 weights_only，就強制設為 False
    kwargs.setdefault("weights_only", False)
    return _original_torch_load(*args, **kwargs)
torch.load = _safe_load

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
    # 遠端分析時 MacWeb 會帶入現場機的 ID，才讀得到現場機量測寫進 DB 的設定
    remote_machine_id = os.environ.get("PDMS2_MACHINE_ID", "").strip()
    if remote_machine_id:
        return remote_machine_id
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


# ================== aruco.pt + SAM2（剪紙區域 object mask）==================
from ultralytics import YOLO, SAM
import numpy as np

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"  # PDMS2_web/models，兩關共用
ARUCO_MODEL_PATH = MODELS_DIR / "aruco.pt"  # 只有一類，抓 ArUco 周圍的剪紙區域
SAM_CANDIDATES = [MODELS_DIR / "sam2_b.pt"]
ARUCO_CONF = 0.5


def _detect_aruco_center(image):
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(image)
    if ids is None or len(ids) == 0:
        return None
    return corners[0][0].mean(axis=0)


def detect_object_mask_sam2(image):
    """aruco.pt 找剪紙區域 -> SAM2 用框精割。
    回傳 (所有輪廓點 Nx2, 最大輪廓 Mx2, 說明文字)；失敗回傳 (None, None, 原因)。"""
    if not ARUCO_MODEL_PATH.exists():
        return None, None, f"找不到 {ARUCO_MODEL_PATH}"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    yolo = YOLO(str(ARUCO_MODEL_PATH))
    res = yolo.predict(source=image, conf=ARUCO_CONF, device=device,
                       retina_masks=True, verbose=False)[0]
    if res.boxes is None or len(res.boxes) == 0:
        return None, None, "aruco.pt 沒有偵測到剪紙區域"

    boxes = res.boxes.xyxy.cpu().numpy()
    confs = res.boxes.conf.cpu().numpy()
    # 優先選包含 ArUco 中心的框（避開角落標記的誤判），沒有才選信心最高的
    idx = int(np.argmax(confs))
    center = _detect_aruco_center(image)
    if center is not None:
        inside = [i for i, (x1, y1, x2, y2) in enumerate(boxes)
                  if x1 <= center[0] <= x2 and y1 <= center[1] <= y2]
        if inside:
            idx = max(inside, key=lambda i: confs[i])

    h, w = image.shape[:2]
    mask, src = None, "SAM2"
    sam_path = next((p for p in SAM_CANDIDATES if p.exists()), None)
    if sam_path is not None:
        try:
            sam = SAM(str(sam_path))
            r = sam.predict(source=image, bboxes=[boxes[idx].tolist()], device=device, verbose=False)
            if r and r[0].masks is not None and len(r[0].masks.data) > 0:
                mask = r[0].masks.data[0].cpu().numpy() > 0.5
        except Exception as e:
            print(f"SAM2 精割失敗，改用 YOLO 遮罩: {e}")
    if mask is None:  # 沒有 SAM2 權重或失敗 -> 用 aruco.pt 自己的遮罩
        if res.masks is None:
            return None, None, "SAM2 與 YOLO 都沒有遮罩"
        mask, src = res.masks.data[idx].cpu().numpy() > 0.5, "YOLO"

    mask = mask.astype(np.uint8) * 255
    if mask.shape[:2] != (h, w):
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None, None, "剪紙區域遮罩找不到輪廓"
    largest = max(contours, key=cv2.contourArea)
    points = np.vstack([c.reshape(-1, 2) for c in contours])
    return points, largest.reshape(-1, 2), f"aruco.pt {confs[idx]:.2f} + {src}"


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

        # 剪紙區域改用 aruco.pt + SAM2；失敗時保留原模型的 object mask
        if detector.original is not None:
            points, largest, info = detect_object_mask_sam2(detector.original)
            if points is not None:
                detector.object_mask_points_original = points
                detector.object_mask_largest_contour_original = largest
                if detector.result is not None:
                    cv2.drawContours(detector.result, [largest.reshape(-1, 1, 2)], -1,
                                     (255, 0, 255), 2)
                print(f"剪紙區域使用 {info}")
            else:
                print(f"{info}，改用原模型的 object mask")
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
