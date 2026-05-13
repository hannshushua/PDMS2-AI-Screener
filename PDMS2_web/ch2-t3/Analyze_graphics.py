import cv2
import os
import shutil
from ultralytics import YOLO
import math
import numpy as np
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# MODEL_PATH = BASE_DIR.parent / "ch2-t1" / "model" / "YOLO.pt"
MODEL_PATH = os.path.join(BASE_DIR.parent , "ch2-t3" , "model" , "YOLO.pt")
# target_dir = BASE_DIR.parent / "ch2-t1"
target_dir = os.path.join(BASE_DIR.parent, "ch2-t3")

class Analyze_graphics:
    def __init__(
        self,
        model_path=MODEL_PATH,
        base_output_dir = target_dir,
        class_names=["Circle", "Cross", "Diamond", "Square", "Triangle"],
    ):
        self.model = YOLO(model_path)
        self.class_names = class_names
        self.base_dir = base_output_dir

    # ------------ 公用工具 ------------
    def calculate_distance(self, center1, center2):
        return math.sqrt((center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2)

    def non_max_suppression_custom(self, detections, distance_threshold=30, conf_threshold=0.1):
        if not detections:
            return []
        detections = [d for d in detections if d["confidence"] > conf_threshold]
        detections.sort(key=lambda x: x["confidence"], reverse=True)
        filtered = []
        for detection in detections:
            is_duplicate = False
            for existing in filtered:
                distance = self.calculate_distance(detection["center"], existing["center"])
                if distance < distance_threshold and detection["cls_id"] == existing["cls_id"]:
                    is_duplicate = True
                    break
            if not is_duplicate:
                filtered.append(detection)
        return filtered

    def reset_dir(self, dir_path):
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
        os.makedirs(dir_path)

    def clear_multiple_dirs(self, dir_list):
        for dir_name in dir_list:
            dir_path = os.path.join(self.base_dir, dir_name) # 結合基底路徑
            dir_path = Path(dir_path)

            if dir_path.exists():
                print(f"清空資料夾: {dir_path}")
                shutil.rmtree(dir_path)
            dir_path.mkdir(parents=True, exist_ok=True) # 使用 Path.mkdir
            print(f"重新建立資料夾: {dir_path}")

    def ensure_dir(self, dir_name):
        dir_path = os.path.join(os.path.join(self.base_dir, dir_name)) # 結合基底路徑
        dir_path = Path(dir_path)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)

    def initialize_workspace(self, clear_all=True):
        # 這裡只保留資料夾名稱
        workspace_dirs = ["cross", "Other", "cropped_a4", "ready"]
        if clear_all:
            print("=== 初始化工作空間，清空所有資料夾 ===")
            self.clear_multiple_dirs(workspace_dirs)
        else:
            print("=== 確保工作空間資料夾存在 ===")
            for dir_name in workspace_dirs:
                self.ensure_dir(dir_name) # ensure_dir 會自動加上 self.base_dir
                print(f"確保資料夾存在: {os.path.join(self.base_dir, dir_name)}")
        print("工作空間初始化完成！\n")

    def get_next_index(self, ready_dir, image_name):
        # 確保 ready_dir 是 Path 物件
        ready_dir_obj = Path(ready_dir)

        if not ready_dir_obj.exists():
            return 0
        
        # 使用 listdir() 獲取檔名字串
        existing_files = [f for f in os.listdir(ready_dir_obj) if f.startswith(image_name)]
        
        max_index = -1
        for filename in existing_files:
            try:
                # 這裡的 filename 是字串，所以 split() 等操作是安全的
                parts = filename.split('_')
                if len(parts) >= 2 and parts[1].isdigit():
                    max_index = max(max_index, int(parts[1]))
            except Exception:
                continue
        return max_index + 1

    # Analyze_graphics 類別內

    def get_unique_filename(self, base_path):
        # 確保輸入是 Path 物件
        base_path_obj = Path(base_path)

        if not base_path_obj.exists():
            return str(base_path_obj) # 回傳字串

        dir_path = base_path_obj.parent
        filename = base_path_obj.name
        name, ext = os.path.splitext(filename) # os.path.splitext 可以處理 Path 物件

        counter = 1
        while True:
            new_filename = f"{name}_v{counter}{ext}"
            new_path = os.path.join(dir_path, new_filename) # 使用 Path 物件的 / 運算符
            
            if not new_path.exists():
                return str(new_path) # 回傳字串
            counter += 1

    # ------------ 重點：固定 224×224 的工具 ------------
    def resize_with_padding(self, image, size=224):
        """保持比例，置中補黑邊，再輸出 size×size。"""
        h, w = image.shape[:2]
        if h == 0 or w == 0:
            return np.zeros((size, size, 3), dtype=np.uint8)
        scale = size / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        canvas = np.ones((size, size, 3), dtype=np.uint8) * 255
        x = (size - new_w) // 2
        y = (size - new_h) // 2
        canvas[y:y+new_h, x:x+new_w] = resized
        return canvas

    def save_224_pair(self, cropped_img, ready_path, ready_binary_path, keep_ratio=False):
        """將彩色與二值圖都存成 224×224"""
        # 直接 resize 到 224x224，不保持比例，不加白邊
        # img224 = cv2.resize(cropped_img, (224, 224), interpolation=cv2.INTER_AREA)

        # 彩色 224×224
        cv2.imwrite(ready_path, cropped_img)

        # 二值化
        gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
        
        # 使用反轉 + Otsu
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        cv2.imwrite(ready_binary_path, binary)

        # 驗證
        color_shape = cv2.imread(ready_path).shape
        bin_shape = cv2.imread(ready_binary_path, cv2.IMREAD_GRAYSCALE).shape
        print(f"  - 寫出彩色: {ready_path} shape={color_shape}")
        print(f"  - 寫出二值: {ready_binary_path} shape={bin_shape}")
    

    # ------------ 推論＋切割 ------------
    # def infer_and_draw(self, image_path, save_results=True, expand_ratio=0.15, clear_dir=False):
    #     results = self.model(image_path, conf=0.7, iou=0.3, max_det=100, imgsz=640)
    #     image_name = os.path.splitext(os.path.basename(image_path))[0]
    #     ori_img = cv2.imread(image_path)

    #     if ori_img is None:
    #         print(f"錯誤：無法讀取圖片 {image_path}")
    #         return []

    #     ready_dir_name = "ready"
    #     ready_dir = os.path.join(self.base_dir, ready_dir_name)

    #     if save_results:
    #         if clear_dir:
    #             self.reset_dir(ready_dir)  # 建議第一次測試用 True，避免舊檔干擾
    #             index = 0
    #         else:
    #             self.ensure_dir(ready_dir)
    #             index = self.get_next_index(ready_dir, image_name)

    #     binary_paths = []

    #     # 收集所有檢測結果
    #     all_detections = []
    #     for result in results:
    #         for box in result.boxes:
    #             cls_id = int(box.cls)
    #             confidence = float(box.conf)
    #             x1, y1, x2, y2 = box.xyxy[0].tolist()

    #             width = x2 - x1
    #             height = y2 - y1
    #             expand_w = width * expand_ratio / 2
    #             expand_h = height * expand_ratio / 2

    #             img_h, img_w = ori_img.shape[:2]
    #             x1e = max(0, int(x1 - expand_w))
    #             y1e = max(0, int(y1 - expand_h))
    #             x2e = min(img_w, int(x2 + expand_w))
    #             y2e = min(img_h, int(y2 + expand_h))

    #             all_detections.append({
    #                 "cls_id": cls_id,
    #                 "confidence": confidence,
    #                 "bbox": (x1e, y1e, x2e, y2e),
    #                 "center": ((x1 + x2) / 2, (y1 + y2) / 2),
    #                 "class_name": self.class_names[cls_id] if cls_id < len(self.class_names) else f"class_{cls_id}"
    #             })

    #     filtered_detections = self.non_max_suppression_custom(all_detections, distance_threshold=30)

    #     for detection in filtered_detections:
    #         x1, y1, x2, y2 = detection["bbox"]
    #         class_name = detection["class_name"]
    #         confidence = detection["confidence"]

    #         if x2 <= x1 or y2 <= y1:
    #             print(f"跳過無效座標: ({x1}, {y1}) to ({x2}, {y2})")
    #             continue

    #         try:
    #             cropped_img = ori_img[y1:y2, x1:x2]
    #             if cropped_img.size == 0:
    #                 print(f"切割結果為空，跳過索引 {index}")
    #                 continue

    #             # ready_path = ready_dir / f"{image_name}_{index}_{class_name}.jpg"
    #             ready_path = os.path.join(ready_dir, f"{image_name}_{index}_{class_name}.jpg")

    #             # ready_binary_path = ready_dir / f"{image_name}_{index}_{class_name}_binary.jpg"
    #             ready_binary_path = os.path.join(ready_dir , f"{image_name}_{index}_{class_name}_binary.jpg")

    #             ready_path = self.get_unique_filename(ready_path)
    #             ready_binary_path = self.get_unique_filename(ready_binary_path)

    #             # ★ 關鍵：兩張都固定 224×224
    #             self.save_224_pair(cropped_img, ready_path, ready_binary_path, keep_ratio=True)

    #             print(f"成功處理 {class_name} (信心度: {confidence:.2f}), 索引: {index}")
    #             index += 1

    #             binary_paths.append(ready_binary_path)

    #         except Exception as e:
    #             print(f"處理索引 {index} 時發生錯誤: {e}")
    #             print(f"  - 座標: ({x1}, {y1}) to ({x2}, {y2})")
    #             continue

    #     print(f"\n總共成功處理 {len(binary_paths)} 個圖形")
    #     return binary_paths

    # ------------ 僅進行全圖二值化並裁切外框 (略過 YOLO 切割) ------------
    def infer_and_draw(self, image_path, save_results=True, clear_dir=False):
        # 取得檔名與讀取圖片
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        ori_img = cv2.imread(image_path)

        if ori_img is None:
            print(f"錯誤：無法讀取圖片 {image_path}")
            return []

        # 設定輸出目錄
        ready_dir_name = "ready"
        ready_dir = os.path.join(self.base_dir, ready_dir_name)

        if save_results:
            if clear_dir:
                self.reset_dir(ready_dir)  # 清空資料夾
            else:
                self.ensure_dir(ready_dir) # 確保資料夾存在

        binary_paths = []

        try:
            # 1. 轉為灰階
            gray = cv2.cvtColor(ori_img, cv2.COLOR_BGR2GRAY)
            
            # 2. 進行二值化 (使用 Otsu 自動閾值 + 反轉黑白)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            # --- 新增：強制作廢最外圈邊緣 ---
            # 直接將圖片最外圍 15 pixel 塗黑，消滅 A4 透視變換殘留的邊緣碎線
            h, w = binary.shape
            margin = 15
            if h > margin * 2 and w > margin * 2:
                binary[0:margin, :] = 0        # 上邊緣塗黑
                binary[h-margin:h, :] = 0      # 下邊緣塗黑
                binary[:, 0:margin] = 0        # 左邊緣塗黑
                binary[:, w-margin:w] = 0      # 右邊緣塗黑
            
            # 3. 尋找輪廓並裁切到內部圖形邊緣
            img_area = h * w
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            valid_contours = []
            for cnt in contours:
                x, y, cw, ch = cv2.boundingRect(cnt)
                # 過濾掉超大外框 (保險機制) 以及面積過小的雜訊(例如長寬小於3的點)
                is_outer_frame = (cw * ch) > (img_area * 0.85)
                is_noise = cw < 3 or ch < 3
                
                if not is_outer_frame and not is_noise:
                    valid_contours.append(cnt)
            
            # 如果有找到內部圖形，就進行裁切
            if valid_contours:
                x_min = min([cv2.boundingRect(c)[0] for c in valid_contours])
                y_min = min([cv2.boundingRect(c)[1] for c in valid_contours])
                x_max = max([cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2] for c in valid_contours])
                y_max = max([cv2.boundingRect(c)[1] + cv2.boundingRect(c)[3] for c in valid_contours])
                
                # 加上一點 padding (留白 10 個 pixels)，避免切到圖形最邊緣
                pad = 10
                x1 = max(0, x_min - pad)
                y1 = max(0, y_min - pad)
                x2 = min(w, x_max + pad)
                y2 = min(h, y_max + pad)
                
                # 執行裁切
                binary = binary[y1:y2, x1:x2]
            else:
                # 備用機制：如果找不到明顯輪廓，就強制往內縮
                binary = binary[margin:h-margin, margin:w-margin]

            # 4. 設定存檔路徑
            ready_binary_path = os.path.join(ready_dir, f"{image_name}_binary.jpg")
            ready_binary_path = self.get_unique_filename(ready_binary_path)

            # 5. 存檔
            if save_results:
                cv2.imwrite(ready_binary_path, binary)
                print(f"成功處理全圖二值化 (已清邊緣並精準裁切): {ready_binary_path}")
            
            binary_paths.append(ready_binary_path)

        except Exception as e:
            print(f"處理圖片 {image_name} 時發生錯誤: {e}")

        print(f"\n總共成功產出 {len(binary_paths)} 張二值化圖形")
        return binary_paths

    # ------------ 舊版固定像素 padding 切割 ------------
    def crop_with_padding(self, image_path, padding_pixels=20, clear_dir=False):
        results = self.model(image_path, conf=0.3, iou=0.3, max_det=100, imgsz=640)
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        ori_img = cv2.imread(image_path)

        ready_dir_name = "ready"
        ready_dir = os.path.join(self.base_dir, ready_dir_name)

        if clear_dir:
            self.reset_dir(ready_dir)
            index = 0
        else:
            self.ensure_dir(ready_dir)
            index = self.get_next_index(ready_dir, image_name)

        binary_paths = []

        all_detections = []
        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls)
                confidence = float(box.conf)
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                all_detections.append({
                    "cls_id": cls_id,
                    "confidence": confidence,
                    "bbox": (x1 - padding_pixels, y1 - padding_pixels, x2 + padding_pixels, y2 + padding_pixels),
                    "center": ((x1 + x2) / 2, (y1 + y2) / 2),
                    "class_name": self.class_names[cls_id] if cls_id < len(self.class_names) else f"class_{cls_id}"
                })

        filtered_detections = self.non_max_suppression_custom(all_detections, distance_threshold=30)

        for detection in filtered_detections:
            x1, y1, x2, y2 = detection["bbox"]
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(ori_img.shape[1], int(x2)), min(ori_img.shape[0], int(y2))

            if x2 <= x1 or y2 <= y1:
                continue

            cropped_img = ori_img[y1:y2, x1:x2]
            class_name = detection["class_name"]

            ready_path = os.path.join(ready_dir, f"{image_name}_{index}_{class_name}.jpg")
            ready_binary_path = os.path.join(ready_dir,  f"{image_name}_{index}_{class_name}_binary.jpg")

            ready_path = self.get_unique_filename(ready_path)
            ready_binary_path = self.get_unique_filename(ready_binary_path)

            # ★ 一樣固定 224×224
            self.save_224_pair(cropped_img, ready_path, ready_binary_path, keep_ratio=True)

            index += 1
            binary_paths.append(ready_binary_path)

        return binary_paths


if __name__ == "__main__":
    image_path = r"input\S__75472901_0.jpg"
    segmenter = Analyze_graphics()

    print("=== 使用比例擴大方式（清空資料夾，避免舊檔混淆）===")
    binary_paths = segmenter.infer_and_draw(image_path, expand_ratio=0.15, clear_dir=True)

    print("\nBinary paths:")
    for p in binary_paths:
        print(p)
