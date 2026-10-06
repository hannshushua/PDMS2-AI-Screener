import cv2
import numpy as np
from pathlib import Path


class PaperDetector_edges:
    def __init__(self, image_path):
        self.image_path = image_path
        self.original = None
        self.result = None
        self.contour = None
        self.paper_region = None

    def detect_paper_by_color(self):
        image = cv2.imread(self.image_path)
        if image is None:
            print("無法讀取圖像檔案")
            return None

        def save_edges(edges_img):
            name = Path(self.image_path).stem
            out_dir = Path(__file__).resolve().parent / "edges"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{name}_edges_paper.jpg"
            cv2.imwrite(str(out_path), edges_img, [cv2.IMWRITE_JPEG_QUALITY, 100])
            print(f"結果已儲存為 '{out_path}'")
            return str(out_path)

        def filter_components(binary_img, min_pixels=120, max_components=8):
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
                binary_img, connectivity=8
            )
            filtered = np.zeros_like(binary_img)
            h, w = binary_img.shape
            kept = []
            for idx in range(1, num_labels):
                x, y, cw, ch, area = stats[idx]
                if area < min_pixels:
                    continue
                touches_border = (
                    x <= 1 or y <= 1 or (x + cw) >= (w - 1) or (y + ch) >= (h - 1)
                )
                if touches_border:
                    continue

                kept.append((int(area), idx))

            kept.sort(reverse=True, key=lambda x: x[0])
            for _, label_idx in kept[:max_components]:
                filtered[labels == label_idx] = 255

            return filtered

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # 1) 先抓白紙，建立 ROI，避免背景紋理進來
        white_mask = cv2.inRange(hsv, np.array([0, 0, 155]), np.array([180, 70, 255]))
        kernel5 = np.ones((5, 5), np.uint8)
        white_mask = cv2.morphologyEx(
            white_mask, cv2.MORPH_CLOSE, kernel5, iterations=2
        )
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN, kernel5, iterations=1)

        roi_mask = np.ones(white_mask.shape, dtype=np.uint8) * 255
        white_contours, _ = cv2.findContours(
            white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if white_contours:
            paper_contour = max(white_contours, key=cv2.contourArea)
            if cv2.contourArea(paper_contour) > 8000:
                paper_mask = np.zeros_like(white_mask)
                cv2.drawContours(paper_mask, [paper_contour], -1, 255, thickness=-1)
                roi_mask = cv2.dilate(
                    paper_mask, np.ones((41, 41), np.uint8), iterations=1
                )

        # 2) 任意顏色紙：用飽和度通道抓輪廓
        sat_blurred = cv2.GaussianBlur(hsv[:, :, 1], (9, 9), 0)
        edges = cv2.Canny(sat_blurred, 30, 120)
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        edges = cv2.bitwise_and(edges, roi_mask)
        edges = filter_components(edges, min_pixels=180, max_components=6)
        edges = cv2.dilate(edges, kernel, iterations=1)
        edges = filter_components(edges, min_pixels=260, max_components=4)

        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = [cnt for cnt in contours if cv2.contourArea(cnt) > 300]

        # 備援：若飽和度邊緣抓不到，再回到一般灰階邊緣
        if not contours:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (9, 9), 0)
            edges = cv2.Canny(blurred, 45, 140)
            edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
            edges = cv2.bitwise_and(edges, roi_mask)
            edges = filter_components(edges, min_pixels=220, max_components=6)
            edges = cv2.morphologyEx(edges, cv2.MORPH_DILATE, kernel, iterations=1)
            edges = filter_components(edges, min_pixels=300, max_components=4)
            contours, _ = cv2.findContours(
                edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
            )
            contours = [cnt for cnt in contours if cv2.contourArea(cnt) > 300]

        self.original = image
        self.result = image.copy()
        self.contour = max(contours, key=cv2.contourArea) if contours else None

        return save_edges(edges)


if __name__ == "__main__":
    image_path = r"img\4.jpg"
    detector = PaperDetector_edges(image_path)
    detector.detect_paper_by_color()
