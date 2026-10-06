import torch

_original_torch_load = torch.load
def _safe_load(*args, **kwargs):
    # 如果呼叫時沒有特別指定 weights_only，就強制設為 False
    kwargs.setdefault("weights_only", False)
    return _original_torch_load(*args, **kwargs)
torch.load = _safe_load

from PaperDetector_yolo import PaperDetector_yolo
from BoxDistanceAnalyzer import BoxDistanceAnalyzer
import cv2
import sys
import os


# ================== aruco.pt + SAM2（剪紙區域 object mask）==================
from ultralytics import YOLO, SAM
from pathlib import Path
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
    # 預設失敗分數，任何流程失敗都回傳 -1
    score = -1

    # 檢查是否有傳入 uid 與 id
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
    print("====先用模型裁切 paper 區域====")

    detector_path = None
    min_dist_cm = None
    max_dist_cm = None

    try:
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

        if detector.original is not None:
            region = detector.extract_paper_region()
            if region is not None:
                detector_path = detector.save_results()

        print("====再用裁切後圖片進行評分====")
        if detector_path:
            if detector.object_mask_points_warped is None:
                print("原圖未偵測到 object mask，無法進行距離評分")
            else:
                result = BoxDistanceAnalyzer(
                    detector_path,
                    contour_points=detector.object_mask_points_warped,
                    largest_contour_points=detector.object_mask_largest_contour_warped,
                )
                if result is not None:
                    result_img, min_dist_cm, max_dist_cm = result
                    if result_img is not None:
                        result_path = os.path.join("kid", uid, f"{img_id}_result.jpg")
                        cv2.imwrite(result_path, result_img)

        if min_dist_cm is not None and max_dist_cm is not None:
            correct = 4.0
            kid = max(abs(min_dist_cm - correct), abs(max_dist_cm - correct))
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
