"""
ch2 畫圖三關共用 —— 手繪圖形 4 類分類（circle / cross / other / square）。
吃 prepare.py 產出的 224 binary(3通道)，回傳 (類別, 信心)。

用法：
  from classify import Classifier
  clf = Classifier()                       # 載 models/shape_cls.pt
  label, conf = clf.classify(bin_bgr)      # bin_bgr = prepare 的 r["binary_bgr"]
  label, conf = clf.classify_path(path)    # 或直接吃 binary 圖檔路徑
"""

from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent / "models"
DEFAULT_CLS_WEIGHTS = MODELS_DIR / "shape_cls.pt"


def pick_device(arg=None):
    if arg:
        return arg
    try:
        import torch
        return "0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class Classifier:
    def __init__(self, cls_weights=DEFAULT_CLS_WEIGHTS, device=None, imgsz=224):
        from ultralytics import YOLO
        self.device = pick_device(device)
        self.model = YOLO(str(cls_weights))
        self.imgsz = imgsz
        print(f"[classify] cls={cls_weights}  classes={self.model.names}")

    def classify(self, bin_bgr):
        """bin_bgr: 224x224x3 binary 影像。回傳 (類別名稱, 信心 float)。"""
        res = self.model.predict(source=bin_bgr, imgsz=self.imgsz,
                                 device=self.device, verbose=False)[0]
        i = int(res.probs.top1)
        return res.names[i], float(res.probs.top1conf)

    def classify_path(self, img_path):
        import cv2
        return self.classify(cv2.imread(str(img_path)))
