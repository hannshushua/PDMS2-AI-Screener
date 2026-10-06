import cv2
import numpy as np
import os
from pathlib import Path
import torch
from ultralytics import YOLO


class PaperDetector_yolo:
    def __init__(self, image_path, weights_path=None):
        self.image_path = image_path
        self.original = None
        self.result = None
        self.contour = None
        self.paper_region = None
        self.object_mask_points_original = None
        self.object_mask_largest_contour_original = None
        self.object_mask_points_warped = None
        self.object_mask_largest_contour_warped = None

        if weights_path is None:
            base_dir = Path(__file__).resolve().parents[1]
            weights_path = base_dir / "models" / "ch3_paper_box.pt"

        self.weights_path = str(weights_path)
        self.model = None
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.weights_path):
            self.model = YOLO(self.weights_path)
        else:
            raise FileNotFoundError(f"Model weights not found: {self.weights_path}")

    def detect_paper_by_yolo(self, conf=0.85, device=None):
        image = cv2.imread(self.image_path)
        if image is None:
            print("無法讀取圖像檔案")
            return None, None, None

        if device is None:
            device = "0" if torch.cuda.is_available() else "cpu"

        names = self.model.names if self.model is not None else {}
        paper_class_ids = [
            int(cls_id)
            for cls_id, cls_name in names.items()
            if "paper" in str(cls_name).lower()
        ]
        object_class_ids = [
            int(cls_id)
            for cls_id, cls_name in names.items()
            if "object" in str(cls_name).lower()
        ]
        if not paper_class_ids:
            print("警告: 模型類別中找不到 'paper'")
            self.original = image
            self.result = image.copy()
            self.contour = None
            return image, self.result, None

        detect_class_ids = sorted(set(paper_class_ids + object_class_ids))

        predict_kwargs = {
            "source": image,
            "conf": conf,
            "device": device,
            "verbose": False,
            "classes": detect_class_ids,
        }

        try:
            results = self.model.predict(**predict_kwargs)
        except Exception as e:
            if device != "cpu" and "cuda" in str(e).lower():
                print("GPU 不可用，切換到 CPU 重新嘗試")
                predict_kwargs["device"] = "cpu"
                results = self.model.predict(**predict_kwargs)
            else:
                raise

        result_image = image.copy()
        paper_contour = None
        self.object_mask_points_original = None
        self.object_mask_largest_contour_original = None
        self.object_mask_points_warped = None
        self.object_mask_largest_contour_warped = None

        if len(results) > 0:
            result = results[0]
            if result.boxes is not None and len(result.boxes) > 0:
                boxes_cls = result.boxes.cls.cpu().numpy().astype(int)
                boxes_conf = result.boxes.conf.cpu().numpy()

                paper_indices = [
                    i for i, cls_id in enumerate(boxes_cls) if cls_id in paper_class_ids
                ]
                if paper_indices:
                    max_conf_idx = max(paper_indices, key=lambda i: boxes_conf[i])
                    box = result.boxes.xyxy[max_conf_idx].cpu().numpy()
                    x1, y1, x2, y2 = box.astype(int)
                    paper_contour = np.array(
                        [[[x1, y1]], [[x2, y1]], [[x2, y2]], [[x1, y2]]],
                        dtype=np.int32,
                    )

                    cls_id = int(boxes_cls[max_conf_idx])
                    cls_name = names.get(cls_id, str(cls_id))
                    conf_score = float(boxes_conf[max_conf_idx])

                    cv2.rectangle(result_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(
                        result_image,
                        f"{cls_name} {conf_score:.2f}",
                        (x1, max(y1 - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2,
                    )
                    print(f"檢測到紙張類別 '{cls_name}'，置信度: {conf_score:.2f}")

                object_indices = [
                    i
                    for i, cls_id in enumerate(boxes_cls)
                    if cls_id in object_class_ids
                ]
                if object_indices and result.masks is not None:
                    obj_idx = max(object_indices, key=lambda i: boxes_conf[i])
                    mask = result.masks.data[obj_idx].cpu().numpy()
                    mask = (mask > 0.5).astype(np.uint8) * 255
                    if mask.shape[:2] != image.shape[:2]:
                        mask = cv2.resize(
                            mask,
                            (image.shape[1], image.shape[0]),
                            interpolation=cv2.INTER_NEAREST,
                        )

                    contours, _ = cv2.findContours(
                        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
                    )
                    if contours:
                        largest = max(contours, key=cv2.contourArea)
                        points = np.vstack([c.reshape(-1, 2) for c in contours])
                        self.object_mask_points_original = points
                        self.object_mask_largest_contour_original = largest.reshape(
                            -1, 2
                        )
                        cv2.drawContours(result_image, contours, -1, (0, 255, 255), 1)
                        print(
                            f"檢測到 object mask，置信度: {float(boxes_conf[obj_idx]):.2f}"
                        )
                    else:
                        print("有 object 偵測框但找不到 mask 輪廓")
                elif object_class_ids:
                    print("未偵測到 object mask")

        self.original = image
        self.result = result_image
        self.contour = paper_contour
        return image, result_image, paper_contour

    def extract_paper_region(self):
        if self.original is None or self.contour is None:
            print("無法提取紙張區域")
            return None

        image = self.original
        contour = self.contour

        if len(contour) != 4:
            rect = cv2.minAreaRect(contour)
            box = cv2.boxPoints(rect)
            contour = np.intp(box)

        points = contour.reshape(4, 2)
        rect = np.zeros((4, 2), dtype=np.float32)
        s = points.sum(axis=1)
        rect[0] = points[np.argmin(s)]
        rect[2] = points[np.argmax(s)]
        diff = np.diff(points, axis=1)
        rect[1] = points[np.argmin(diff)]
        rect[3] = points[np.argmax(diff)]

        # 往外擴一點，避免紙張被切太緊
        expand_ratio = 0.04
        center = np.mean(rect, axis=0)
        rect = center + (rect - center) * (1.0 + expand_ratio)
        h, w = image.shape[:2]
        rect[:, 0] = np.clip(rect[:, 0], 0, w - 1)
        rect[:, 1] = np.clip(rect[:, 1], 0, h - 1)

        width_a = np.linalg.norm(rect[0] - rect[1])
        width_b = np.linalg.norm(rect[2] - rect[3])
        max_width = max(int(width_a), int(width_b))

        height_a = np.linalg.norm(rect[0] - rect[3])
        height_b = np.linalg.norm(rect[1] - rect[2])
        max_height = max(int(height_a), int(height_b))

        dst = np.array(
            [
                [0, 0],
                [max_width - 1, 0],
                [max_width - 1, max_height - 1],
                [0, max_height - 1],
            ],
            dtype=np.float32,
        )
        matrix = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, matrix, (max_width, max_height))

        if self.object_mask_points_original is not None:
            pts = self.object_mask_points_original.astype(np.float32).reshape(-1, 1, 2)
            pts_warped = cv2.perspectiveTransform(pts, matrix).reshape(-1, 2)
            valid = (
                (pts_warped[:, 0] >= 0)
                & (pts_warped[:, 0] < max_width)
                & (pts_warped[:, 1] >= 0)
                & (pts_warped[:, 1] < max_height)
            )
            if np.any(valid):
                self.object_mask_points_warped = pts_warped[valid].astype(int)
            else:
                self.object_mask_points_warped = None

        if self.object_mask_largest_contour_original is not None:
            lpts = self.object_mask_largest_contour_original.astype(np.float32).reshape(
                -1, 1, 2
            )
            lpts_warped = cv2.perspectiveTransform(lpts, matrix).reshape(-1, 2)
            valid = (
                (lpts_warped[:, 0] >= 0)
                & (lpts_warped[:, 0] < max_width)
                & (lpts_warped[:, 1] >= 0)
                & (lpts_warped[:, 1] < max_height)
            )
            if np.any(valid):
                self.object_mask_largest_contour_warped = lpts_warped[valid].astype(int)
            else:
                self.object_mask_largest_contour_warped = None

        self.paper_region = warped
        return warped

    def save_results(self):
        name = self.image_path.split(os.sep)[-1].split(".")[0]
        result_path = os.path.join("ch3-t2", "extracted", f"{name}_extracted_paper.jpg")
        os.makedirs(os.path.dirname(result_path), exist_ok=True)
        if self.paper_region is not None:
            ok = cv2.imwrite(result_path, self.paper_region)
            if not ok:
                raise IOError(f"無法寫入檔案: {result_path}")
        print(f"結果已儲存為 '{result_path}'")
        return result_path
