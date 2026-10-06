import cv2
import numpy as np
import os
from Draw_square import Draw_square
from pathlib import Path
import torch
from ultralytics import YOLO


class BoxDistanceAnalyzer:
    def __init__(
        self,
        box1=None,
        image_path=None,
        mask_points=None,
        largest_mask_contour=None,
    ):
        self.box1 = box1
        self.image_path = image_path
        self.box2 = None
        self.model_path = (
            Path(__file__).resolve().parents[1] / "models" / "ch3_paper_box.pt"
        )
        self._mask_points_cache = mask_points
        self._largest_mask_contour_cache = largest_mask_contour

    def _load_object_mask_contours(self, image_path, device=None):
        if (
            self._mask_points_cache is not None
            and self._largest_mask_contour_cache is not None
        ):
            return self._mask_points_cache, self._largest_mask_contour_cache

        img = cv2.imread(image_path)
        if img is None:
            print(f"無法讀取圖片: {image_path}")
            return None, None

        if not self.model_path.exists():
            print(f"找不到模型權重: {self.model_path}")
            return None, None

        model = YOLO(str(self.model_path))
        if device is None:
            device = "0" if torch.cuda.is_available() else "cpu"

        names = model.names if model is not None else {}
        object_class_ids = [
            int(cls_id)
            for cls_id, cls_name in names.items()
            if "object" in str(cls_name).lower()
        ]
        if not object_class_ids:
            print("模型類別中找不到 object")
            return None, None

        result = None
        selected_conf = None
        conf_candidates = [0.85]
        for conf in conf_candidates:
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
                    print(f"YOLO 推論失敗: {e}")
                    return None, None

            if len(results) == 0:
                continue

            candidate = results[0]
            if candidate.boxes is None or len(candidate.boxes) == 0:
                continue
            if candidate.masks is None or len(candidate.masks.data) == 0:
                continue

            result = candidate
            selected_conf = conf
            break

        if result is None:
            print("YOLO 沒有偵測到 object mask")
            return None, None

        print(f"object mask 偵測門檻使用 conf={selected_conf}")

        max_conf_idx = int(np.argmax(result.boxes.conf.cpu().numpy()))
        mask = result.masks.data[max_conf_idx].cpu().numpy()
        mask = (mask > 0.5).astype(np.uint8) * 255
        if mask.shape[:2] != img.shape[:2]:
            mask = cv2.resize(
                mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST
            )

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            print("object mask 找不到輪廓")
            return None, None

        largest = max(contours, key=cv2.contourArea)
        points = np.vstack([c.reshape(-1, 2) for c in contours])
        self._mask_points_cache = points
        self._largest_mask_contour_cache = largest.reshape(-1, 2)
        return self._mask_points_cache, self._largest_mask_contour_cache

    def detect_main_contour_points(self, image_path, show_debug=False):
        """
        取得 YOLO object mask 的輪廓點
        """
        points, _ = self._load_object_mask_contours(image_path)
        if points is None:
            return None

        if show_debug:
            img = cv2.imread(image_path)
            if img is None:
                return points
            debug_image = img.copy()
            for pt in points:
                cv2.circle(debug_image, tuple(pt), 1, (0, 255, 255), 1)
            cv2.imshow("debug_edges_points", debug_image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        return points

    def detect_largest_contour(self, image_path, area_threshold=3000):
        """回傳最大外部輪廓的有序點集 (N,2)；若無則回傳 None。"""
        _, largest = self._load_object_mask_contours(image_path)
        return largest

    @staticmethod
    def _closest_point_on_segment(p, a, b):
        """取得點 p 到線段 ab 的最近點（垂足，若超出端點則回端點）。
        p, a, b: np.array([x, y])
        回傳: (closest_point, distance)
        """
        ap = p - a
        ab = b - a
        ab_len_sq = float(np.dot(ab, ab))
        if ab_len_sq == 0.0:
            # 退化為單點
            return a, float(np.linalg.norm(p - a))
        t = float(np.dot(ap, ab)) / ab_len_sq
        t = max(0.0, min(1.0, t))
        proj = a + t * ab
        return proj, float(np.linalg.norm(p - proj))

    def _min_distance_to_polygon_edges(self, p, poly):
        """計算點 p 到多邊形 poly 的各邊的最短距離與對應最近點。
        poly: (N,2) 順時針或逆時針
        回傳: (min_dist, closest_point)
        """
        min_dist = float("inf")
        closest = None
        n = len(poly)
        for i in range(n):
            a = poly[i].astype(float)
            b = poly[(i + 1) % n].astype(float)
            foot, d = self._closest_point_on_segment(p.astype(float), a, b)
            if d < min_dist:
                min_dist = d
                closest = foot
        return min_dist, closest

    def draw_main_contour(self, img, color=(0, 255, 255), thickness=1):
        """
        在 img 上畫出最大輪廓的邊緣點（黃色）
        """
        points = self.detect_main_contour_points(self.image_path)
        if points is not None:
            for pt in points:
                cv2.circle(img, tuple(pt), 1, color, thickness)
        return img

    def analyze(self, pixel_per_cm=None, out_path="result"):
        if pixel_per_cm is None:
            print("未提供每公分像素數")
            return
        if self.box1 is None or self.image_path is None:
            print("box1 或 image_path 尚未設定")
            return

        # 偵測最大輪廓的邊緣點（黃色點集合）
        main_points = self.detect_main_contour_points(self.image_path, show_debug=False)
        if main_points is None:
            print("未偵測到任何邊緣")
            return

        # 內凹與外凸皆支援：對所有黃色點計算到紅框的有號距離，取絕對值最大者
        red_poly = self.box1.astype(np.int32)
        red_contour = red_poly.reshape(-1, 1, 2)

        best_abs_signed = 0.0
        best_sign = 0.0
        best_yellow = None
        best_foot = None
        for y in main_points:
            signed_d = cv2.pointPolygonTest(
                red_contour, (float(y[0]), float(y[1])), True
            )
            d_unsigned, foot = self._min_distance_to_polygon_edges(
                np.array(y, dtype=float), red_poly
            )
            if abs(signed_d) > best_abs_signed:
                best_abs_signed = abs(signed_d)
                best_sign = 1.0 if signed_d >= 0 else -1.0
                best_yellow = tuple(map(int, y))
                best_foot = tuple(map(int, foot))

        direction = "內凹" if best_sign >= 0 else "外凸"
        print(f"{direction}方向的最大最短距離: {(best_abs_signed/pixel_per_cm):.2f}")

        img = cv2.imread(self.image_path)
        img_draw = img.copy()
        cv2.putText(
            img_draw,
            f"{(best_abs_signed/pixel_per_cm):.2f} cm",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )

        cv2.polylines(
            img_draw,
            [self.box1.astype(np.int32)],
            isClosed=True,
            color=(0, 0, 255),
            thickness=1,
        )
        self.draw_main_contour(img_draw, color=(0, 255, 255), thickness=1)

        if best_yellow is not None and best_foot is not None:
            cv2.line(img_draw, best_yellow, best_foot, (0, 255, 0), 1)
            cv2.circle(img_draw, best_yellow, 2, (255, 0, 0), -1)
            cv2.circle(img_draw, best_foot, 2, (255, 0, 255), -1)

        yellow_contour = self.detect_largest_contour(self.image_path)
        best_corner_min_dist = 0.0
        if yellow_contour is not None and len(yellow_contour) >= 2:
            n_y = len(yellow_contour)
            best_corner_point = None
            best_corner_foot = None
            best_corner_min_dist = -1.0

            for corner in red_poly:
                p = corner.astype(float)
                min_d = float("inf")
                min_foot = None
                for i in range(n_y):
                    a = yellow_contour[i].astype(float)
                    b = yellow_contour[(i + 1) % n_y].astype(float)
                    foot, d = self._closest_point_on_segment(p, a, b)
                    if d < min_d:
                        min_d = d
                        min_foot = foot

                if min_d > best_corner_min_dist:
                    best_corner_min_dist = min_d
                    best_corner_point = tuple(map(int, corner))
                    best_corner_foot = tuple(map(int, min_foot))

            if best_corner_point is not None and best_corner_foot is not None:
                cv2.line(
                    img_draw, best_corner_point, best_corner_foot, (255, 255, 0), 1
                )
                cv2.circle(img_draw, best_corner_point, 3, (0, 165, 255), -1)
                cv2.circle(img_draw, best_corner_foot, 3, (0, 255, 255), -1)

                cv2.putText(
                    img_draw,
                    f"{(best_corner_min_dist/pixel_per_cm):.2f} cm",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (255, 0, 0),
                    1,
                    cv2.LINE_AA,
                )
                print(
                    f"紅框四角到黃框線之最短的最長距離: {(best_corner_min_dist/pixel_per_cm):.2f}"
                )

        os.makedirs(os.path.join("ch3-t2", out_path), exist_ok=True)
        name = self.image_path.split(os.sep)[-1].split("_")[0]
        path = f"ch3-t2/{out_path}/{name}_max_dist.png"
        cv2.imwrite(path, img_draw)
        print(f"最長距離線段與方框、最大輪廓邊緣已畫出並存檔於 {path}")

        return img_draw, max(
            best_abs_signed / pixel_per_cm, best_corner_min_dist / pixel_per_cm
        )


if __name__ == "__main__":
    detector_path = r"extracted\img2_extracted_paper.jpg"
    D_sq_path, black_corners_int = Draw_square(detector_path)
    analyzer = BoxDistanceAnalyzer(box1=black_corners_int, image_path=detector_path)
    analyzer.analyze(pixel_per_cm=19.597376925845985)
