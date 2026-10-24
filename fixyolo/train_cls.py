"""
train_cls.py - 形狀分類 (circle / square / cross / other) 訓練，資料來源是 cut_shape.py 的 shape_result/

步驟:
  1. 依「原始照片」分組切 train / val
     Roboflow 匯出的同一張照片會有好幾個 .rf.<hash> 擴增版本 (檔名 LINE_ALBUM_-_250728_101_jpg.rf.xxx_3.png)，
     隨機切會讓同一張照片同時出現在 train 和 val，val 分數會假高。所以取 .rf. 前面那段當分組，整組一起分。
  2. 只對 train 做離線擴增，順便把每類補到一樣多 (少的類別擴增比較多張)
     rot   任意角度旋轉 (四類旋轉後類別都不變：菱形算 square、X 算 cross)
     flip  左右 / 上下翻轉
     thick 筆畫變粗 / 變細 (不同筆、不同解析度)
     fit   圖形大小 / 位置微調 (模擬切圖框大小不準)
     ※ ultralytics 分類訓練不吃 degrees，所以旋轉只能在這裡做
  3. 用 ultralytics YOLO 分類模型訓練 (預設 yolo11n-cls.pt，224)
     關掉不適合黑白圖的線上擴增：hsv、erasing (會把圓挖斷)、randaugment (Solarize 會把白線變黑)
     RandomResizedCrop 只裁掉 <=10% (scale=0.1)，避免把圖形切掉一塊
  4. 用 best.pt 對 val 推論，印混淆矩陣，把分錯的圖存到 runs/classify/<name>/val_errors/<真實>_as_<預測>/

資料集 (--dataset，預設 shape_cls_dataset/，已存在就沿用，加 --rebuild 重做):
    shape_cls_dataset/train/{circle,square,cross,other}/
    shape_cls_dataset/val/{circle,square,cross,other}/
    shape_cls_dataset/split.json     哪些照片分到 val

用法:
    python train_cls.py                              # 建資料集 + 訓練 + 評估
    python train_cls.py --build-only                 # 只建資料集，先看看分得如何
    python train_cls.py --rebuild --epochs 150
    python train_cls.py --model yolo11s-cls.pt --name shape_cls_s
    python train_cls.py --eval-only runs/classify/shape_cls/weights/best.pt
訓練完把 best.pt 換成 ../PDMS2_web/models/shape_cls.pt，或 cut_shape.py --cls-model 指定
"""
import argparse
import json
import random
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
CLASSES = ("circle", "cross", "other", "square")  # 跟舊 shape_cls.pt 同順序 (ultralytics 依字母排)
SIZE = 224
# 黑白線條圖的線上擴增設定 (quickdraw_pretrain.py 也用)
BW_AUG = dict(
    hsv_h=0.0, hsv_s=0.0, hsv_v=0.0,  # 黑白圖不需要顏色擴增；旋轉 / 粗細另外離線做
    fliplr=0.5, flipud=0.5,
    erasing=0.0,          # 隨機挖洞會把圓挖斷變成沒封口
    auto_augment="",      # randaugment 的 Solarize / Posterize 會破壞黑白圖
    scale=0.1,            # RandomResizedCrop 最多只裁掉 10%
)


def parse_args():
    p = argparse.ArgumentParser(description="形狀分類訓練 (shape_result -> shape_cls)")
    p.add_argument("--src", default=str(BASE_DIR / "shape_result"), help="cut_shape.py 的輸出 (分好類的資料夾)")
    p.add_argument("--dataset", default=str(BASE_DIR / "shape_cls_dataset"), help="產生的 train/val 資料集")
    p.add_argument("--val-ratio", type=float, default=0.2, help="分到 val 的照片比例")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--aug-mult", type=float, default=3.0,
                   help="train 每類補到 (最多那類的原圖數 x 這個倍數) 張")
    p.add_argument("--rebuild", action="store_true", help="重新產生資料集")
    p.add_argument("--build-only", action="store_true", help="只建資料集不訓練")
    p.add_argument("--model", default="yolo11n-cls.pt")
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--patience", type=int, default=20, help="val 幾個 epoch 沒進步就停")
    p.add_argument("--batch", type=int, default=64)
    p.add_argument("--imgsz", type=int, default=SIZE)
    p.add_argument("--device", default=None, help="例: 0 / cpu (預設自動)")
    p.add_argument("--name", default="shape_cls", help="runs/classify/<name>")
    p.add_argument("--eval-only", default=None, help="只評估這個權重")
    return p.parse_args()


# ================== 讀寫 (中文路徑要用 imdecode / imencode) ==================
def imread_gray(path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def imwrite(path, img):
    cv2.imencode(".png", img)[1].tofile(str(path))


def photo_key(name):
    """同一張原始照片的分組 key：去掉 Roboflow 的 _jpg.rf.<hash> 和 cut_shape 加的 _<第幾個>"""
    stem = Path(name).stem
    m = re.match(r"(.+?)(?:_(?:jpg|jpeg|png))?\.rf\.", stem)
    return m.group(1) if m else re.sub(r"_\d+$", "", stem)


# ================== 1. 分組切 train / val ==================
def split_groups(src, val_ratio, seed):
    """回傳 {"train": [(path, cls)], "val": [...]}, val 照片 key 清單"""
    items = [(f, c) for c in CLASSES for f in sorted((src / c).glob("*.png"))]
    if not items:
        raise SystemExit(f"{src} 裡沒有圖 (要有 {'/'.join(CLASSES)} 子資料夾)")
    groups = defaultdict(list)
    for f, c in items:
        groups[photo_key(f.name)].append((f, c))
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    val_keys = set(keys[:max(1, round(len(keys) * val_ratio))])
    out = {"train": [], "val": []}
    for k, its in groups.items():
        out["val" if k in val_keys else "train"].extend(its)
    print(f"共 {len(items)} 張、{len(keys)} 張不同照片 -> train {len(keys) - len(val_keys)} 張照片 / val {len(val_keys)} 張照片")
    return out, sorted(val_keys)


# ================== 2. 離線擴增 ==================
def fit_to_canvas(mask, margin):
    """把白色筆畫的外接框縮放置中到 SIZE x SIZE，四周留 margin (比例)"""
    ys, xs = np.nonzero(mask > 127)
    if len(xs) == 0:
        return cv2.resize(mask, (SIZE, SIZE))
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    inner = SIZE * (1 - 2 * margin)
    s = inner / max(h, w)
    nh, nw = max(1, int(round(h * s))), max(1, int(round(w * s)))
    crop = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
    out = np.zeros((SIZE, SIZE), np.uint8)
    y0, x0 = (SIZE - nh) // 2, (SIZE - nw) // 2
    out[y0:y0 + nh, x0:x0 + nw] = crop
    return out


def augment(img, rng):
    """隨機組合 旋轉 / 翻轉 / 粗細 / 大小位置，回傳 SIZE x SIZE 灰階"""
    m = img.copy()
    # 粗細：先在原解析度處理，筆畫太細就不再變細 (會斷掉)
    r = rng.random()
    if r < 0.35:
        k = int(rng.choice([2, 3, 4]))
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    elif r < 0.6:
        thin = cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2)))
        if (thin > 127).sum() >= 0.6 * max(1, (m > 127).sum()):
            m = thin
    # 翻轉
    if rng.random() < 0.5:
        m = cv2.flip(m, 1)
    if rng.random() < 0.5:
        m = cv2.flip(m, 0)
    # 任意角度旋轉 (先放大畫布，轉完不會切到)
    ang = rng.uniform(0, 360)
    pad = SIZE // 2
    big = cv2.copyMakeBorder(m, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    c = (big.shape[1] / 2, big.shape[0] / 2)
    big = cv2.warpAffine(big, cv2.getRotationMatrix2D(c, ang, 1.0), (big.shape[1], big.shape[0]),
                         flags=cv2.INTER_LINEAR, borderValue=0)
    # 大小 / 位置：重新置中並隨機留邊，再小幅平移
    out = fit_to_canvas(big, rng.uniform(0.06, 0.2))
    tx, ty = (rng.uniform(-0.06, 0.06) * SIZE for _ in range(2))
    out = cv2.warpAffine(out, np.float32([[1, 0, tx], [0, 1, ty]]), (SIZE, SIZE), borderValue=0)
    return out


def build_dataset(args):
    src, ds = Path(args.src), Path(args.dataset)
    split, val_keys = split_groups(src, args.val_ratio, args.seed)
    if ds.exists():
        shutil.rmtree(ds)
    for part in ("train", "val"):
        for c in CLASSES:
            (ds / part / c).mkdir(parents=True, exist_ok=True)

    # val 原封不動
    for f, c in split["val"]:
        shutil.copy2(f, ds / "val" / c / f.name)

    # train 原圖 + 擴增補到 target 張
    by_cls = defaultdict(list)
    for f, c in split["train"]:
        by_cls[c].append(f)
    target = int(max(len(v) for v in by_cls.values()) * args.aug_mult)
    rng = random.Random(args.seed)
    print(f"train 每類補到 {target} 張")
    for c in CLASSES:
        files = by_cls.get(c, [])
        if not files:
            print(f"  [WARN] train 沒有 {c}")
            continue
        imgs = {}
        for f in files:
            shutil.copy2(f, ds / "train" / c / f.name)
        n_aug = max(0, target - len(files))
        order = [files[i % len(files)] for i in range(n_aug)]
        rng.shuffle(order)
        for j, f in enumerate(order):
            if f not in imgs:
                imgs[f] = imread_gray(f)
            imwrite(ds / "train" / c / f"{f.stem}_aug{j}.png", augment(imgs[f], rng))
        print(f"  {c:>6}: 原圖 {len(files)} + 擴增 {n_aug}")

    cnt = {p: {c: len(list((ds / p / c).glob("*.png"))) for c in CLASSES} for p in ("train", "val")}
    print(f"val: {cnt['val']}")
    with open(ds / "split.json", "w", encoding="utf-8") as fp:
        json.dump({"src": str(src), "seed": args.seed, "val_ratio": args.val_ratio,
                   "counts": cnt, "val_photos": val_keys}, fp, ensure_ascii=False, indent=2)


# ================== 3. 訓練 ==================
def train(args):
    from ultralytics import YOLO

    model = YOLO(args.model)
    model.train(
        data=str(Path(args.dataset)), imgsz=args.imgsz, epochs=args.epochs, patience=args.patience,
        batch=args.batch, device=args.device, seed=args.seed,
        project=str(BASE_DIR / "runs" / "classify"), name=args.name, exist_ok=True,
        **BW_AUG,
    )
    return BASE_DIR / "runs" / "classify" / args.name / "weights" / "best.pt"


# ================== 4. 評估 ==================
def evaluate(weights, args):
    from ultralytics import YOLO

    model = YOLO(str(weights))
    names = model.names
    val = Path(args.dataset) / "val"
    err_dir = Path(weights).parent.parent / "val_errors"
    if err_dir.exists():
        shutil.rmtree(err_dir)
    cm = Counter()
    files = [(f, c) for c in CLASSES for f in sorted((val / c).glob("*.png"))]
    for i in range(0, len(files), 64):
        batch = files[i:i + 64]
        rs = model.predict([str(f) for f, _ in batch], imgsz=args.imgsz, device=args.device, verbose=False)
        for (f, c), r in zip(batch, rs):
            p = names[int(r.probs.top1)]
            cm[(c, p)] += 1
            if p != c:
                d = err_dir / f"{c}_as_{p}"
                d.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, d / f.name)

    total = sum(cm.values())
    correct = sum(v for (t, p), v in cm.items() if t == p)
    print(f"\n=== val 結果 ({weights}) ===")
    print(f"準確率: {correct}/{total} = {correct / max(1, total):.3f}")
    print("混淆矩陣 (列 = 真實, 欄 = 預測)")
    print(f"{'':>8}" + "".join(f"{p:>8}" for p in CLASSES) + f"{'recall':>9}")
    for t in CLASSES:
        row = sum(cm[(t, p)] for p in CLASSES)
        print(f"{t:>8}" + "".join(f"{cm[(t, p)]:>8}" for p in CLASSES) + f"{cm[(t, t)] / max(1, row):>9.3f}")
    if correct < total:
        print(f"分錯的圖: {err_dir}")
    # 給 train_all.py 比較用
    metrics = {"weights": str(weights), "acc": correct / max(1, total), "correct": correct, "total": total,
               "recall": {t: cm[(t, t)] / max(1, sum(cm[(t, p)] for p in CLASSES)) for t in CLASSES},
               "confusion": {t: {p: cm[(t, p)] for p in CLASSES} for t in CLASSES}}
    with open(Path(weights).parent.parent / "val_metrics.json", "w", encoding="utf-8") as fp:
        json.dump(metrics, fp, ensure_ascii=False, indent=2)


def main():
    args = parse_args()
    if args.eval_only:
        evaluate(args.eval_only, args)
        return
    if args.rebuild or not (Path(args.dataset) / "train").exists():
        build_dataset(args)
    else:
        print(f"沿用資料集 {args.dataset} (要重做加 --rebuild)")
    if args.build_only:
        return
    best = train(args)
    evaluate(best, args)


if __name__ == "__main__":
    main()
