"""
quickdraw_pretrain.py - 用 Google Quick, Draw! 手繪塗鴉預訓練分類模型，當 train_cls.py 的底

為什麼: shape_result 只有約 300 張不同照片；ImageNet 預訓練學的是照片，跟手繪線條差很多。
先讓模型在大量手繪幾何圖形上學會「看線條」，再用 train_cls.py 微調成 circle / cross / other / square。

步驟:
  1. 下載: 從 Quick, Draw! (CC BY 4.0) 串流讀 simplified ndjson，每類只取前 --per-class 張「有被辨識成功」的
     (不用下載整個 30~40MB 的檔)，存在 quickdraw/raw/<類別>.ndjson，已存在就沿用
  2. 畫圖: 筆畫座標畫成 224 黑底白線 (跟 cut_shape.py 的 binary 一樣)，筆畫粗細隨機
     存到 quickdraw/dataset/{train,val}/<類別>/
     ※ 不做旋轉：square 轉 45 度會變 diamond，預訓練類別會互相打架
  3. 預訓練: yolo11n-cls.pt (ImageNet) -> runs/classify/quickdraw_pre/weights/best.pt

預設類別 (Quick, Draw! 裡純幾何的 10 類，沒有 cross 這類，cross 交給微調學):
    circle square triangle line diamond hexagon octagon zigzag squiggle star

用法:
    python quickdraw_pretrain.py                         # 下載 + 畫圖 + 預訓練
    python quickdraw_pretrain.py --per-class 10000 --epochs 20
    python quickdraw_pretrain.py --build-only            # 只下載 + 畫圖
接著微調:
    python train_cls.py --model runs/classify/quickdraw_pre/weights/best.pt --name shape_cls_qd
"""
import argparse
import json
import random
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from train_cls import BASE_DIR, BW_AUG, SIZE, fit_to_canvas, imwrite

URL = "https://storage.googleapis.com/quickdraw_dataset/full/simplified/{}.ndjson"
CATEGORIES = ("circle", "square", "triangle", "line", "diamond",
              "hexagon", "octagon", "zigzag", "squiggle", "star")
QD_DIR = BASE_DIR / "quickdraw"


def parse_args():
    p = argparse.ArgumentParser(description="Quick, Draw! 預訓練")
    p.add_argument("--categories", nargs="+", default=list(CATEGORIES))
    p.add_argument("--per-class", type=int, default=6000, help="每類取幾張")
    p.add_argument("--val-ratio", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--rebuild", action="store_true", help="重新畫圖 (下載的 ndjson 會沿用)")
    p.add_argument("--build-only", action="store_true")
    p.add_argument("--model", default="yolo11n-cls.pt")
    p.add_argument("--epochs", type=int, default=15)
    p.add_argument("--batch", type=int, default=128)
    p.add_argument("--device", default=None)
    p.add_argument("--name", default="quickdraw_pre")
    return p.parse_args()


# ================== 1. 下載 ==================
def download(cat, n):
    """串流讀 ndjson，只留 recognized 的前 n 筆，存成 quickdraw/raw/<cat>.ndjson"""
    out = QD_DIR / "raw" / f"{cat}.ndjson"
    if out.exists() and sum(1 for _ in open(out, encoding="utf-8")) >= n:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    url = URL.format(urllib.parse.quote(cat))
    kept = 0
    with urllib.request.urlopen(url, timeout=60) as r, open(out, "w", encoding="utf-8") as f:
        for line in r:
            d = json.loads(line)
            if not d.get("recognized"):
                continue
            f.write(json.dumps({"drawing": d["drawing"]}) + "\n")
            kept += 1
            if kept >= n:
                break
    print(f"  下載 {cat}: {kept} 張")
    return out


# ================== 2. 畫圖 ==================
def render(strokes, rng):
    """simplified 座標 (0~255) 畫成 SIZE x SIZE 黑底白線，粗細 / 留邊隨機"""
    k = 2  # 先畫在 512 的畫布上，縮小時線條比較平滑
    canvas = np.zeros((256 * k + 40, 256 * k + 40), np.uint8)
    thick = int(rng.uniform(12, 32))  # 縮到 224 後約 4~11 px，跟 shape_result 差不多
    for xs, ys in strokes:
        pts = np.array([[x * k + 20, y * k + 20] for x, y in zip(xs, ys)], np.int32)
        if len(pts) == 1:
            cv2.circle(canvas, tuple(pts[0]), thick // 2, 255, -1)
        else:
            cv2.polylines(canvas, [pts], False, 255, thick, cv2.LINE_AA)
    return fit_to_canvas(canvas, rng.uniform(0.06, 0.2))


def build(args):
    ds = QD_DIR / "dataset"
    if ds.exists():
        if not args.rebuild:
            print(f"沿用 {ds} (要重畫加 --rebuild)")
            return ds
        shutil.rmtree(ds)
    rng = random.Random(args.seed)
    print("下載 Quick, Draw! ...")
    for cat in args.categories:
        src = download(cat, args.per_class)
        lines = open(src, encoding="utf-8").read().splitlines()[:args.per_class]
        n_val = int(len(lines) * args.val_ratio)
        name = cat.replace(" ", "_")
        for part in ("train", "val"):
            (ds / part / name).mkdir(parents=True, exist_ok=True)
        for i, line in enumerate(lines):
            part = "val" if i < n_val else "train"
            imwrite(ds / part / name / f"{name}_{i}.png", render(json.loads(line)["drawing"], rng))
        print(f"  畫好 {cat}: train {len(lines) - n_val} / val {n_val}")
    return ds


# ================== 3. 預訓練 ==================
def main():
    args = parse_args()
    ds = build(args)
    if args.build_only:
        return
    from ultralytics import YOLO

    YOLO(args.model).train(
        data=str(ds), imgsz=SIZE, epochs=args.epochs, batch=args.batch, device=args.device, seed=args.seed,
        project=str(BASE_DIR / "runs" / "classify"), name=args.name, exist_ok=True, **BW_AUG,
    )
    best = BASE_DIR / "runs" / "classify" / args.name / "weights" / "best.pt"
    print(f"\n預訓練完成: {best}")
    print(f"接著微調: python train_cls.py --model {best.relative_to(BASE_DIR)} --name shape_cls_qd")


if __name__ == "__main__":
    main()
