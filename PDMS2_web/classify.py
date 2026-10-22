"""
ch2 畫圖三關共用 —— 手繪圖形 4 類分類（circle / cross / other / square）。
吃 prepare.py 產出的 224 binary(3通道)。

用法：
  from classify import Classifier
  clf = Classifier()                         # 載 models/shape_cls.pt
  t = clf.check_target(bin_bgr, "circle")    # 各關用這個：只看目標形狀的機率
  t["ok"], t["p"], t["probs"], t["why"]
  label, conf = clf.classify(bin_bgr)        # [舊] 取最高的那類 (shape_pipeline 等舊程式用)
  label, conf = clf.classify_path(path)

check_target 為什麼不取最高：
  ch2-t1 只問「像不像圓」、ch2-t2 只問「像不像方」、ch2-t3 只問「像不像十字」。
  取最高的話，歪圓 circle 0.45 / square 0.55 會被判成方形 -> 0 分；
  改成「目標類別機率 >= TARGET_THR 就過」，其他類別多高都不影響。
"""

from pathlib import Path

import cv2
import numpy as np

MODELS_DIR = Path(__file__).resolve().parent / "models"
DEFAULT_CLS_WEIGHTS = MODELS_DIR / "shape_cls.pt"

# 目標形狀機率 >= 這個值就算畫對 (val 集: 0.4 時 circle 102/104、square 186/199、cross 121/124 通過)
TARGET_THR = 0.4
# 額外用圓度保底的目標：凸包圓度 4πA/P² >= 門檻也算過 (正圓 1.0、正方形 0.785)
# 模型會把凹凸不平的圓看成方形，ch2-t1 以圓為主，圓度夠就給過
ROUND_RESCUE = {"circle": 0.85}


def pick_device(arg=None):
    if arg:
        return arg
    try:
        import torch
        return "0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def roundness(binary):
    """筆畫外輪廓凸包的圓度 4πA/P²：正圓 1.0、正方形 0.785、越扁越尖越小"""
    if binary.ndim == 3:
        binary = cv2.cvtColor(binary, cv2.COLOR_BGR2GRAY)
    m = cv2.morphologyEx((binary > 127).astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return 0.0
    hull = cv2.convexHull(max(cnts, key=cv2.contourArea))
    p = cv2.arcLength(hull, True)
    return float(4 * np.pi * cv2.contourArea(hull) / (p * p)) if p else 0.0


def fmt_probs(probs):
    return "  ".join(f"{k} {v:.2f}" for k, v in probs.items())


class Classifier:
    def __init__(self, cls_weights=DEFAULT_CLS_WEIGHTS, device=None, imgsz=224):
        from ultralytics import YOLO
        self.device = pick_device(device)
        self.model = YOLO(str(cls_weights))
        self.imgsz = imgsz
        print(f"[classify] cls={cls_weights}  classes={self.model.names}")

    def _predict(self, bin_bgr):
        return self.model.predict(source=bin_bgr, imgsz=self.imgsz,
                                  device=self.device, verbose=False)[0]

    def probs(self, bin_bgr):
        """各類機率 {類別: float}"""
        res = self._predict(bin_bgr)
        return {res.names[k]: float(p) for k, p in enumerate(res.probs.data.tolist())}

    def check_target(self, bin_bgr, target, thr=TARGET_THR, round_thr=None):
        """只看目標形狀：P(target) >= thr 就過 (target 是 circle 時圓度夠高也過)。
        round_thr: 圓度保底門檻，None = 用 ROUND_RESCUE 的設定，0 = 關掉。
        回傳 dict: ok, p (目標機率), probs (各類機率), roundness (沒用到為 None), why (說明)"""
        probs = self.probs(bin_bgr)
        p = probs.get(target, 0.0)
        out = {"ok": p >= thr, "p": p, "probs": probs, "roundness": None,
               "why": f"{target} {p:.2f} {'>=' if p >= thr else '<'} {thr}"}
        rt = ROUND_RESCUE.get(target, 0.0) if round_thr is None else round_thr
        if not out["ok"] and rt > 0:
            rd = roundness(bin_bgr)
            out["roundness"] = rd
            if rd >= rt:
                out["ok"] = True
                out["why"] += f"，但圓度 {rd:.2f} >= {rt} 改判通過"
            else:
                out["why"] += f"，圓度 {rd:.2f} < {rt}"
        return out

    def classify(self, bin_bgr):
        """[舊] 取最高的那類。bin_bgr: 224x224x3 binary 影像。回傳 (類別名稱, 信心 float)。"""
        res = self._predict(bin_bgr)
        i = int(res.probs.top1)
        return res.names[i], float(res.probs.top1conf)

    def classify_path(self, img_path):
        return self.classify(cv2.imread(str(img_path)))
