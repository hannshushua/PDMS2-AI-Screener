"""
cut_shape.py - 批次: 找圖形 -> 切下來轉黑底白線二值圖 -> 形狀分類 -> 依結果分資料夾存
一張圖找到幾個圖形就切幾個，每個各自分類

流程跟 take.py 按 d 一樣:
    paper_seg.pt 找紙 -> shape_det.pt 在紙上找圖形 -> 切正方形 (框外用框邊像素補)
    -> 黑底白線 binary 224 -> shape_cls.pt 分類

輸出 (--out，預設 shape_result/):
    shape_result/circle/<檔名>_<第幾個>.png   (第幾個從 0 開始，面積大的在前)
    shape_result/square/<檔名>_<第幾個>.png
    shape_result/cross/<檔名>_<第幾個>.png
    shape_result/other/<檔名>_<第幾個>.png
    shape_result/predictions.csv              每個切圖的來源、預測、各類機率 (Excel 可直接開)
    找不到圖形 / 讀取失敗的只在最後列出，不存檔

範例:
    python cut_shape.py ../check_ch2
    python cut_shape.py ../check_ch2 --out shape_result --shape-conf 0.3
    python cut_shape.py ../kid -r            # 連子資料夾一起讀
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from take import (BASE_DIR, CLS_MODEL, IMG_EXTS, PAPER_SEG_MODEL, ROUND_THR, classify_shape, find_shapes,
                  fmt_probs, mask_polys, round_thr_for, task_of)

SHAPE_DET_MODEL = BASE_DIR.parent / "PDMS2_web" / "models" / "shape_det.pt"
CLASSES = ("circle", "square", "cross", "other")


def parse_args():
    p = argparse.ArgumentParser(description="批次找圖形 + 二值化 + 形狀分類，依結果分資料夾存二值圖")
    p.add_argument("folder", help="圖片資料夾")
    p.add_argument("--out", default=str(BASE_DIR / "shape_result"), help="輸出資料夾")
    p.add_argument("-r", "--recursive", action="store_true", help="連子資料夾的圖一起讀")
    p.add_argument("--paper-model", default=str(PAPER_SEG_MODEL), help="紙張 segment 權重 (過濾紙外的框)")
    p.add_argument("--shape-model", default=str(SHAPE_DET_MODEL), help="圖形偵測權重")
    p.add_argument("--cls-model", default=str(CLS_MODEL), help="形狀分類權重")
    p.add_argument("--round-thr", type=float, default=ROUND_THR,
                   help="判成 square 但圓度超過這個值就改判 circle (0 = 關掉)；ch2-t1 / ch2-t2 另有門檻 (take.TASK_ROUND_THR)")
    p.add_argument("--task", default="auto", help="關卡 (例 ch2-t1)，決定圓度門檻；auto = 從檔名抓")
    p.add_argument("--conf", type=float, default=0.5, help="紙張信心門檻")
    p.add_argument("--shape-conf", type=float, default=0.25, help="圖形偵測信心門檻")
    p.add_argument("--imgsz", type=int, default=640, help="紙張 / 圖形偵測推論尺寸")
    p.add_argument("--device", default=None, help="例: 0 / cpu (預設自動)")
    return p.parse_args()


def main():
    args = parse_args()
    folder = Path(args.folder)
    if not folder.is_dir():
        sys.exit(f"找不到資料夾 {folder}")
    pattern = "**/*" if args.recursive else "*"
    files = sorted(f for f in folder.glob(pattern) if f.is_file() and f.suffix.lower() in IMG_EXTS)
    if not files:
        sys.exit(f"{folder} 裡沒有圖片")
    for path in (args.paper_model, args.shape_model, args.cls_model):
        if not Path(path).exists():
            sys.exit(f"找不到權重 {path}")

    from ultralytics import YOLO

    paper_model = YOLO(args.paper_model)
    shape_model = YOLO(args.shape_model)
    cls_model = YOLO(args.cls_model)
    print(f"紙張: {args.paper_model}\n圖形: {args.shape_model}\n分類: {args.cls_model} "
          f"(classes={list(cls_model.names.values())})")

    out = Path(args.out)
    for c in CLASSES:
        (out / c).mkdir(parents=True, exist_ok=True)

    counts = Counter()
    failed = []
    n_cut = {}  # 每張切了幾個
    rows = []  # predictions.csv
    names = list(cls_model.names.values())
    for n, f in enumerate(files, 1):
        # cv2.imread 讀不了中文路徑，改用 imdecode
        img = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            failed.append((f, "讀取失敗"))
            print(f"[{n}/{len(files)}] {f.name}  讀取失敗")
            continue
        r = paper_model.predict(img, conf=args.conf, imgsz=args.imgsz, device=args.device, verbose=False)[0]
        shapes = find_shapes(shape_model, img, mask_polys(r), args)
        if not shapes:
            failed.append((f, "找不到圖形"))
            print(f"[{n}/{len(files)}] {f.name}  切 0 個")
            continue
        # 遞迴模式下不同子資料夾可能同名，檔名前面加上相對路徑
        stem = "_".join(f.relative_to(folder).with_suffix("").parts)
        task = task_of(f.name, args)
        thr = round_thr_for(task, args)
        print(f"[{n}/{len(files)}] {f.name}  切 {len(shapes)} 個")
        for k, shp in enumerate(shapes):
            label, cf, binary, note, probs = classify_shape(cls_model, img, shp, args, thr)
            sub = label if label in CLASSES else "other"
            name = f"{stem}_{k}.png"
            # cv2.imwrite 寫不了中文路徑，改用 imencode
            cv2.imencode(".png", binary)[1].tofile(str(out / sub / name))
            counts[sub] += 1
            print(f"    #{k} -> {sub} {cf:.2f}  [{fmt_probs(probs)}]" + (f"  (圓度改判: {note})" if note else ""))
            rows.append([str(f), f"{sub}/{name}", task or "", sub, note] + [f"{probs[c]:.4f}" for c in names])
        n_cut[f] = len(shapes)

    # utf-8-sig: Excel 開中文檔名不會亂碼
    with open(out / "predictions.csv", "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["source", "crop", "task", "pred", "round_override"] + [f"p_{c}" for c in names])
        w.writerows(rows)

    print(f"\n完成，輸出在 {out}  (共 {len(n_cut)} 張切了 {sum(counts.values())} 個)")
    for c in CLASSES:
        print(f"  {c}: {counts[c]}")
    if failed:
        print(f"  失敗: {len(failed)}")
        for f, why in failed:
            print(f"    {f}  ({why})")
    multi = {f: k for f, k in n_cut.items() if k > 1}
    if multi:
        print(f"  切了多個的圖: {len(multi)} 張")
        for f, k in multi.items():
            print(f"    {f}  {k} 個")


if __name__ == "__main__":
    main()
