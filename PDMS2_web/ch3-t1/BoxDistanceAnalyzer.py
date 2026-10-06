import cv2
import numpy as np
import os
from pathlib import Path
import torch
from ultralytics import YOLO


def _detect_aruco_center_and_scale(img):
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
    corners, ids, _ = detector.detectMarkers(img)

    if ids is None or len(ids) == 0:
        raise ValueError("找不到 ArUco marker")

    pts = corners[0][0]  # 取第一個 marker
    side_lengths = [np.linalg.norm(pts[i] - pts[(i + 1) % 4]) for i in range(4)]
    avg_side_px = np.mean(side_lengths)
    aruco_length_cm = 2.0
    pixel_per_cm = avg_side_px / aruco_length_cm
    center_x = int(np.mean(pts[:, 0]))
    center_y = int(np.mean(pts[:, 1]))

    return (center_x, center_y), pixel_per_cm


def _get_object_mask_contour_points(img, conf=0.85, device=None):
    model_path = Path(__file__).resolve().parents[1] / "models" / "ch3_paper_box.pt"
    if not model_path.exists():
        raise FileNotFoundError(f"找不到模型權重: {model_path}")

    model = YOLO(str(model_path))
    if device is None:
        device = "0" if torch.cuda.is_available() else "cpu"

    names = model.names if model is not None else {}
    object_class_ids = [
        int(cls_id)
        for cls_id, cls_name in names.items()
        if "object" in str(cls_name).lower()
    ]
    if not object_class_ids:
        raise ValueError("模型類別中找不到 object")

    predict_kwargs = {
        "source": img,
        "conf": conf,
        "device": device,
        "verbose": False,
        "classes": object_class_ids,
    }

    try:
        results = model.predict(**predict_kwargs)
    except Exception as e:
        if device != "cpu" and "cuda" in str(e).lower():
            predict_kwargs["device"] = "cpu"
            results = model.predict(**predict_kwargs)
        else:
            raise

    if len(results) == 0:
        raise ValueError("YOLO 沒有輸出結果")

    result = results[0]
    if result.masks is None or len(result.masks.data) == 0:
        raise ValueError("YOLO 沒有偵測到 object mask")

    if result.boxes is None or len(result.boxes) == 0:
        raise ValueError("YOLO 沒有偵測到 object 邊界框")

    max_conf_idx = int(np.argmax(result.boxes.conf.cpu().numpy()))
    mask = result.masks.data[max_conf_idx].cpu().numpy()
    mask = (mask > 0.5).astype(np.uint8) * 255

    if mask.shape[:2] != img.shape[:2]:
        mask = cv2.resize(
            mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST
        )

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("object mask 找不到輪廓")

    contour_points = np.vstack([c.reshape(-1, 2) for c in contours])
    return contour_points


def BoxDistanceAnalyzer(
    img_path=None,
    output_path=None,
    contour_points=None,
    largest_contour_points=None,
):
    if output_path is None:
        output_path = os.path.join("ch3-t1", "result")
    os.makedirs(output_path, exist_ok=True)

    img = cv2.imread(img_path)
    if img is None:
        print("讀取圖片失敗，請確認檔案路徑正確！")
        return

    (center_x, center_y), pixel_per_cm = _detect_aruco_center_and_scale(img)
    if contour_points is None:
        contour_points = _get_object_mask_contour_points(img)

    center = np.array([center_x, center_y])
    dists = np.linalg.norm(contour_points - center, axis=1)
    min_idx = int(np.argmin(dists))
    max_idx = int(np.argmax(dists))
    min_dist = dists[min_idx]
    max_dist = dists[max_idx]
    min_dist_cm = min_dist / pixel_per_cm
    max_dist_cm = max_dist / pixel_per_cm

    if largest_contour_points is not None:
        contour_for_draw = largest_contour_points.reshape(-1, 1, 2).astype(np.int32)
    else:
        contour_for_draw = contour_points.reshape(-1, 1, 2).astype(np.int32)
    cv2.drawContours(img, [contour_for_draw], -1, (0, 255, 255), 1)
    cv2.circle(img, (center_x, center_y), 5, (0, 255, 0), -1)

    min_point = tuple(contour_points[min_idx])
    max_point = tuple(contour_points[max_idx])
    cv2.line(img, (center_x, center_y), min_point, (0, 0, 255), 2)
    cv2.line(img, (center_x, center_y), max_point, (255, 0, 0), 2)

    cv2.putText(
        img,
        f"min: {min_dist_cm:.2f}cm",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 255),
        2,
    )
    cv2.putText(
        img,
        f"max: {max_dist_cm:.2f}cm",
        (10, 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 0, 0),
        2,
    )

    name = img_path.split(os.sep)[-1].split("_")[0]
    path = f"{output_path}/{name}.png"
    cv2.imwrite(path, img)

    print(f"結果已儲存為 '{path}'")
    print(
        f"ArUco中心到object mask輪廓\n最短距離: {min_dist_cm:.2f}cm, 最長距離: {max_dist_cm:.2f}cm"
    )
    return img, min_dist_cm, max_dist_cm


if __name__ == "__main__":
    path = r"extracted\img1_extracted_paper.jpg"
    path = BoxDistanceAnalyzer(path)
