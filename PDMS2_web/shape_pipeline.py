"""
[相容轉接層] 邏輯已拆到 prepare.py(分類前) 與 classify.py(分類)。
本檔只為了讓舊 import (fix_draw/test_cls.py、bootstrap_shape_labels.py) 繼續可用。
新程式請直接用：
  from prepare import Preparer
  from classify import Classifier
"""

from pathlib import Path

import cv2
import numpy as np

# 分類前的所有工具函式（單一來源在 prepare.py）
from prepare import (pick_device, get_paper_bbox, sam_mask_from_bbox, locate_paper,
                     find_shape_bbox, crop_square, to_binary, Preparer,
                     DEFAULT_PAPER_WEIGHTS, DEFAULT_SAM_WEIGHTS)
from classify import Classifier, DEFAULT_CLS_WEIGHTS


def paper_mask_cv(frame):
    """[legacy] CV 亮色區塊當紙張 mask（現行流程已不用；保留供舊測試腳本）。"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    m = np.zeros_like(gray)
    cv2.drawContours(m, [c], -1, 255, cv2.FILLED)
    return m


class ShapePipeline:
    """[相容] 用 Preparer + Classifier 組出舊的 analyze() 介面。"""

    def __init__(self, paper_weights=DEFAULT_PAPER_WEIGHTS,
                 sam_weights=DEFAULT_SAM_WEIGHTS,
                 cls_weights=DEFAULT_CLS_WEIGHTS, device=None,
                 paper_conf=0.4, pad=30, size=224, imgsz=224, **_):
        self.prep = Preparer(paper_weights, sam_weights, device, paper_conf, pad, size)
        self.clf = Classifier(cls_weights, device, imgsz)
        # 舊程式可能直接存取的屬性
        self.device = self.prep.device
        self.paper = self.prep.paper
        self.sam = self.prep.sam
        self.cls = self.clf.model
        self.paper_conf = paper_conf
        self.pad = pad
        self.size = size

    def classify_binary(self, bin_bgr):
        return self.clf.classify(bin_bgr)

    def analyze(self, img_path, out_dir, stem):
        r = self.prep.prepare(img_path, out_dir, stem)
        if not r["ok"]:
            return {"ok": False, "reason": r["reason"], "vis": r.get("vis")}
        label, conf = self.clf.classify(r["binary_bgr"])
        vis = r["vis"]
        sq = r["bbox"]
        cv2.putText(vis, f"{label} {conf*100:.1f}%", (sq[0], max(sq[1] - 10, 24)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        cv2.imwrite(r["vis_path"], vis)
        return {"ok": True, "label": label, "conf": conf,
                "color_path": r["color_path"], "binary_path": r["binary_path"],
                "vis_path": r["vis_path"], "vis": vis}
